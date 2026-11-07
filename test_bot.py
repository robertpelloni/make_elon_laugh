import os
import sqlite3
import unittest
from unittest.mock import patch, MagicMock
from auth import validate_api_keys, get_twitter_client
import sys
from bot import validate_tweet_content, validate_api_tweets, main
from rate_limiter import async_call_api_with_backoff, RateLimitExceededException
import db
from analytics import AnalyticsTracker
import tweepy
from joke_generator import generate_joke
import joke_generator
import dashboard
import digest
import scheduler
import tray
import meme_generator
import webhook
import urllib.error


class TestBotValidation(unittest.TestCase):

    def test_validate_api_keys_valid(self):
        result = validate_api_keys(
            "valid_bearer",
            "valid_key",
            "valid_secret",
            "valid_token",
            "valid_token_secret"
        )
        self.assertTrue(result)

    def test_validate_api_keys_empty_value(self):
        with self.assertRaisesRegex(ValueError, "API key validation failed: API_KEY is empty."):
            validate_api_keys(
                "valid_bearer",
                "",
                "valid_secret",
                "valid_token",
                "valid_token_secret"
            )

    def test_validate_api_keys_none_value(self):
        with self.assertRaisesRegex(ValueError, "API key validation failed: ACCESS_TOKEN is empty."):
            validate_api_keys(
                "valid_bearer",
                "valid_key",
                "valid_secret",
                None,
                "valid_token_secret"
            )

    def test_validate_api_keys_default_placeholder(self):
        with self.assertRaisesRegex(
                ValueError,
                "API key validation failed: BEARER_TOKEN is still set to the default placeholder 'YOUR_BEARER_TOKEN'."
        ):
            validate_api_keys(
                "YOUR_BEARER_TOKEN",
                "valid_key",
                "valid_secret",
                "valid_token",
                "valid_token_secret"
            )

    def test_validate_api_keys_returns_stripped_values_for_padded_keys(self):
        cleaned_keys = validate_api_keys(
            " valid_bearer ",
            "valid_key",
            "valid_secret",
            "valid_token",
            "valid_token_secret"
        )
        self.assertEqual(cleaned_keys["BEARER_TOKEN"], "valid_bearer")

    def test_validate_api_keys_raises_type_error_for_non_string_inputs(self):
        with self.assertRaisesRegex(TypeError, "API key validation failed: API_SECRET must be a string."):
            validate_api_keys(
                "valid_bearer",
                "valid_key",
                12345,
                "valid_token",
                "valid_token_secret"
            )

    def test_validate_tweet_content_valid(self):
        self.assertEqual(validate_tweet_content("This is a valid tweet! 🚀"), "This is a valid tweet! 🚀")

    def test_validate_tweet_content_empty(self):
        with self.assertRaisesRegex(ValueError, "Tweet content validation failed: Content is empty."):
            validate_tweet_content("")

    def test_validate_tweet_content_whitespace(self):
        with self.assertRaisesRegex(ValueError, "Tweet content validation failed: Content is empty."):
            validate_tweet_content("   \n   ")

    def test_validate_tweet_content_too_long(self):
        long_tweet = "A" * 281
        with self.assertRaisesRegex(ValueError, "Tweet content validation failed: Content exceeds 280 characters"):
            validate_tweet_content(long_tweet)

    def test_validate_tweet_content_max_length(self):
        max_length_tweet = "A" * 280
        self.assertEqual(validate_tweet_content(max_length_tweet), max_length_tweet)

    def test_validate_tweet_content_strips_padding_before_length_check(self):
        max_length_tweet = "A" * 280
        padded_tweet = f" {max_length_tweet} \n"
        self.assertEqual(validate_tweet_content(padded_tweet), max_length_tweet)

    def test_validate_tweet_content_raises_type_error_for_non_string_inputs(self):
        with self.assertRaisesRegex(TypeError, "Tweet content validation failed: Content must be a string."):
            validate_tweet_content(12345)


class TestMalformedAPIResponseFallback(unittest.TestCase):

    class MockTweet:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    def test_validate_api_tweets_valid(self):
        tweets = [self.MockTweet(id=123, text="Hello"), self.MockTweet(id=456, text="World")]
        valid = validate_api_tweets(tweets)
        self.assertEqual(len(valid), 2)
        self.assertEqual(valid[0].id, 123)

    def test_validate_api_tweets_missing_id(self):
        tweets = [self.MockTweet(text="No ID"), self.MockTweet(id=456, text="World")]
        valid = validate_api_tweets(tweets)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0].id, 456)

    def test_validate_api_tweets_missing_text(self):
        tweets = [self.MockTweet(id=123), self.MockTweet(id=456, text="World")]
        valid = validate_api_tweets(tweets)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0].text, "World")

    def test_validate_api_tweets_not_iterable(self):
        self.assertEqual(validate_api_tweets(None), [])
        self.assertEqual(validate_api_tweets("Not a list"), [])

    def test_validate_api_tweets_boundary_empty_collection(self):
        self.assertEqual(validate_api_tweets([]), [])
        self.assertEqual(validate_api_tweets(tuple()), [])

    def test_validate_api_tweets_boundary_iterable_dictionary(self):
        mock_payload = {"error": "rate_limited", "status": 429}
        self.assertEqual(validate_api_tweets(mock_payload), [])

    def test_validate_api_tweets_boundary_falsy_id(self):
        tweets = [self.MockTweet(id=0, text="Valid zero ID")]
        valid = validate_api_tweets(tweets)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0].id, 0)
        self.assertEqual(valid[0].text, "Valid zero ID")

    def test_validate_api_tweets_boundary_empty_string_text(self):
        tweets = [self.MockTweet(id=789, text="")]
        valid = validate_api_tweets(tweets)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0].text, "")


class TestRateLimiterAsync(unittest.IsolatedAsyncioTestCase):

    async def test_successful_call_no_backoff(self):
        async def success_api():
            return "success"

        result = await async_call_api_with_backoff(success_api)
        self.assertEqual(result, "success")

    async def test_backoff_and_eventual_success(self):
        calls = {"count": 0}

        async def mock_api_429():
            calls["count"] += 1
            if calls["count"] < 3:
                raise Exception("API error 429 Too Many Requests")
            return "eventual_success"

        result = await async_call_api_with_backoff(
            mock_api_429,
            max_retries=3,
            initial_backoff=0.01,
            backoff_factor=2,
            max_jitter=0
        )

        self.assertEqual(result, "eventual_success")
        self.assertEqual(calls["count"], 3)

    async def test_backoff_exhausted(self):
        async def mock_api_always_429():
            raise Exception("HTTP error 429")

        with self.assertRaises(RateLimitExceededException):
            await async_call_api_with_backoff(
                mock_api_always_429,
                max_retries=2,
                initial_backoff=0.01,
                backoff_factor=1,
                max_jitter=0
            )

    async def test_backoff_and_eventual_success_on_network_latency(self):
        calls = {"count": 0}

        async def mock_api_timeout():
            calls["count"] += 1
            if calls["count"] < 3:
                raise TimeoutError("Simulated network timeout")
            return "eventual_success"

        result = await async_call_api_with_backoff(
            mock_api_timeout,
            max_retries=3,
            initial_backoff=0.01,
            backoff_factor=2,
            max_jitter=0
        )

        self.assertEqual(result, "eventual_success")
        self.assertEqual(calls["count"], 3)

    async def test_backoff_exhausted_on_connection_error(self):
        async def mock_api_always_connection_error():
            raise ConnectionError("Simulated connection dropped")

        with self.assertRaises(RateLimitExceededException):
            await async_call_api_with_backoff(
                mock_api_always_connection_error,
                max_retries=2,
                initial_backoff=0.01,
                backoff_factor=1,
                max_jitter=0
            )

    async def test_non_retryable_exception_raised_immediately(self):
        calls = {"count": 0}

        async def mock_api_401():
            calls["count"] += 1
            raise Exception("HTTP error 401 Unauthorized")

        with self.assertRaisesRegex(Exception, "HTTP error 401 Unauthorized"):
            await async_call_api_with_backoff(mock_api_401)

        self.assertEqual(calls["count"], 1)


class TestDatabaseStorage(unittest.TestCase):

    def setUp(self):
        self.test_db = "test_bot_data.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        db.init_db(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_database_initialization(self):
        self.assertTrue(os.path.exists(self.test_db))

    def test_record_and_check_reply(self):
        self.assertFalse(db.has_replied("12345", self.test_db))
        db.record_reply("12345", self.test_db)
        self.assertTrue(db.has_replied("12345", self.test_db))

    def test_record_duplicate_reply_safe(self):
        db.record_reply("999", self.test_db)
        db.record_reply("999", self.test_db)
        self.assertTrue(db.has_replied("999", self.test_db))

    def test_update_and_retrieve_engagement(self):
        db.record_reply("888", self.test_db)
        from dashboard import get_db_stats
        with patch('dashboard.db.DB_PATH', self.test_db):
            stats = get_db_stats()
            self.assertEqual(stats["total_likes"], 0)
            self.assertEqual(stats["total_retweets"], 0)

        db.update_engagement("888", 10, 5, self.test_db)

        with patch('dashboard.db.DB_PATH', self.test_db):
            stats = get_db_stats()
            self.assertEqual(stats["total_likes"], 10)
            self.assertEqual(stats["total_retweets"], 5)
            recent = stats["recent_replies"][0]
            self.assertEqual(recent["tweet_id"], "888")
            self.assertEqual(recent["likes"], 10)
            self.assertEqual(recent["retweets"], 5)

    def test_get_tweets_for_engagement_polling(self):
        db.record_reply("111", self.test_db)
        db.record_reply("222", self.test_db)

        tweets = db.get_tweets_for_engagement_polling(limit=5, db_path=self.test_db)
        self.assertIn("111", tweets)
        self.assertIn("222", tweets)
        self.assertEqual(len(tweets), 2)

    def test_joke_ratings_storage(self):
        # Test recording ratings
        success_up = db.record_joke_rating("Hilarious joke!", 1, "great timing", self.test_db)
        self.assertTrue(success_up)
        success_down = db.record_joke_rating("Lame pun", -1, None, self.test_db)
        self.assertTrue(success_down)

        ratings = db.get_joke_ratings(limit=5, db_path=self.test_db)
        self.assertEqual(len(ratings), 2)
        self.assertEqual(ratings[0]["content"], "Lame pun")
        self.assertEqual(ratings[0]["rating"], -1)
        self.assertEqual(ratings[1]["content"], "Hilarious joke!")
        self.assertEqual(ratings[1]["rating"], 1)

    def test_scheduled_tweets_storage(self):
        # Schedule tweet
        tid = db.schedule_tweet("Starship launch tomorrow!", "2026-12-01 10:00:00", "tactful_engineer", self.test_db)
        self.assertIsNotNone(tid)

        pending = db.get_scheduled_tweets(status="pending", limit=5, db_path=self.test_db)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["content"], "Starship launch tomorrow!")
        self.assertEqual(pending[0]["status"], "pending")

        # Update status
        updated = db.update_scheduled_tweet_status(tid, "sent", self.test_db)
        self.assertTrue(updated)
        sent = db.get_scheduled_tweets(status="sent", limit=5, db_path=self.test_db)
        self.assertEqual(len(sent), 1)

    @patch('db.get_db_connection')
    def test_db_exceptions_handled_gracefully(self, mock_get_db):
        mock_get_db.side_effect = sqlite3.Error("Simulated DB error")
        self.assertFalse(db.has_replied("123", self.test_db))
        try:
            db.record_reply("123", self.test_db)
        except Exception:
            self.fail("record_reply raised an exception instead of catching it.")

        with self.assertRaises(sqlite3.Error):
            db.init_db(self.test_db)


class TestAnalyticsTracker(unittest.TestCase):
    def test_tracker_increments(self):
        tracker = AnalyticsTracker()
        self.assertEqual(tracker.tweets_found, 0)

        tracker.record_found()
        tracker.record_reply()
        tracker.record_malformed()
        tracker.record_validation_error()

        self.assertEqual(tracker.tweets_found, 1)
        self.assertEqual(tracker.tweets_replied, 1)
        self.assertEqual(tracker.malformed_tweets_skipped, 1)
        self.assertEqual(tracker.validation_errors, 1)

    @patch('analytics.logger.info')
    def test_tracker_print_summary(self, mock_logger):
        tracker = AnalyticsTracker()
        tracker.print_summary()
        self.assertTrue(mock_logger.called)


class TestAuthModule(unittest.TestCase):
    def test_get_twitter_client_success(self):
        with patch('auth.BEARER_TOKEN', 'valid_token'), \
             patch('auth.API_KEY', 'valid_key'), \
             patch('auth.API_SECRET', 'valid_secret'), \
             patch('auth.ACCESS_TOKEN', 'valid_access'), \
             patch('auth.ACCESS_TOKEN_SECRET', 'valid_access_secret'):

            client = get_twitter_client()
            self.assertIsInstance(client, tweepy.asynchronous.AsyncClient)


class TestJokeGenerator(unittest.TestCase):
    def test_generate_joke_returns_string(self):
        joke = generate_joke()
        self.assertIsInstance(joke, str)
        self.assertTrue(len(joke) > 0)
        self.assertLessEqual(len(joke), 280)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake_key"})
    @patch('joke_generator.openai.OpenAI')
    def test_generate_joke_llm_success(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Dynamic AI Joke 🤖"))]
        mock_client.chat.completions.create.return_value = mock_response

        joke = generate_joke("Test context")
        self.assertEqual(joke, "Dynamic AI Joke 🤖")
        mock_client.chat.completions.create.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake_key"})
    @patch('joke_generator.openai.OpenAI')
    def test_generate_joke_llm_sentiment_skip(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="SKIP"))]
        mock_client.chat.completions.create.return_value = mock_response

        joke = generate_joke("Very serious context tweet")
        self.assertIsInstance(joke, str)
        self.assertTrue(joke in joke_generator.STATIC_JOKES or joke in joke_generator.STATIC_FACTS)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake_key"})
    @patch('joke_generator.openai.OpenAI')
    def test_generate_joke_llm_failure_fallback(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Down")

        joke = generate_joke("Test context")
        self.assertIsInstance(joke, str)
        self.assertTrue(joke in joke_generator.STATIC_JOKES or joke in joke_generator.STATIC_FACTS)


class TestMemeGenerator(unittest.TestCase):

    def test_create_meme_card_valid(self):
        # Must return valid PNG bytes
        img_bytes = meme_generator.create_meme_card("This is a test joke card! 🚀")
        self.assertIsInstance(img_bytes, bytes)
        self.assertTrue(len(img_bytes) > 0)
        # PNG signature check: \x89PNG\r\n\x1a\n
        self.assertTrue(img_bytes.startswith(b'\x89PNG\r\n\x1a\n'))

    def test_create_meme_card_empty_or_invalid(self):
        # Empty string or non-string should fall back cleanly
        img_bytes = meme_generator.create_meme_card("")
        self.assertTrue(img_bytes.startswith(b'\x89PNG\r\n\x1a\n'))
        img_bytes_none = meme_generator.create_meme_card(None)
        self.assertTrue(img_bytes_none.startswith(b'\x89PNG\r\n\x1a\n'))


class TestDashboardAndEndpoints(unittest.TestCase):

    def setUp(self):
        db.init_db()
        dashboard.app.config['TESTING'] = True
        self.client = dashboard.app.test_client()

    def test_index_route(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Emperor Musk Bot", response.data)
        self.assertIn(b"Command Center", response.data)

    def test_api_stats_route(self):
        response = self.client.get('/api/stats')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("total_replies", data)
        self.assertIn("total_likes", data)
        self.assertIn("total_retweets", data)

    def test_api_logs_route(self):
        response = self.client.get('/api/logs')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("logs", data)
        self.assertIsInstance(data["logs"], list)

    def test_api_test_generate_joke(self):
        response = self.client.post(
            '/api/test-generate',
            json={"type": "joke"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("content", data)
        self.assertEqual(data["content_type"], "joke")

    def test_api_test_generate_fact(self):
        response = self.client.post(
            '/api/test-generate',
            json={"type": "fact"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("content", data)
        self.assertEqual(data["content_type"], "fact")

    def test_api_test_generate_auto(self):
        response = self.client.post(
            '/api/test-generate',
            json={"type": "auto"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("content", data)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake_key"})
    @patch('joke_generator.openai.OpenAI')
    def test_api_test_generate_sentiment_skip(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="SKIP"))]
        mock_client.chat.completions.create.return_value = mock_response

        response = self.client.post(
            '/api/test-generate',
            json={"context_tweet": "Tragic event occurred", "type": "joke"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("skipped"))

    def test_api_test_generate_meme_endpoint(self):
        response = self.client.post(
            '/api/test-generate-meme',
            json={"text": "Custom test joke 🛸"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["text"], "Custom test joke 🛸")
        self.assertIn("image_b64", data)
        self.assertTrue(len(data["image_b64"]) > 0)

    def test_api_config_get_and_post(self):
        get_res = self.client.get('/api/config')
        self.assertEqual(get_res.status_code, 200)
        self.assertIn("target_user_ids", get_res.get_json())

        # Update targets
        post_res = self.client.post(
            '/api/config',
            json={"target_user_ids": "12345, 67890"}
        )
        self.assertEqual(post_res.status_code, 200)
        self.assertEqual(post_res.get_json()["target_user_ids"], "12345,67890")

        # Invalid post
        err_res = self.client.post('/api/config', json={"target_user_ids": "   "})
        self.assertEqual(err_res.status_code, 400)

    @patch('db.init_db')
    @patch('db.record_reply')
    @patch('db.update_engagement')
    def test_api_run_check_success(self, mock_update, mock_record, mock_init):
        response = self.client.post('/api/run-check')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("tweet_id", data)

    @patch('db.init_db')
    def test_api_run_check_failure(self, mock_init):
        mock_init.side_effect = Exception("DB Init Error")
        response = self.client.post('/api/run-check')
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.get_json()["success"])

    @patch('threading.Thread')
    def test_api_shutdown(self, mock_thread):
        response = self.client.post('/api/shutdown')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertTrue(mock_thread.called)

    def test_api_theme_get_and_post(self):
        # GET default
        get_res = self.client.get('/api/theme')
        self.assertEqual(get_res.status_code, 200)
        self.assertIn("theme", get_res.get_json())

        # POST valid theme: light
        post_res = self.client.post('/api/theme', json={"theme": "light"})
        self.assertEqual(post_res.status_code, 200)
        self.assertTrue(post_res.get_json()["success"])
        self.assertEqual(post_res.get_json()["theme"], "light")

        # POST valid theme: dark
        post_res = self.client.post('/api/theme', json={"theme": "dark"})
        self.assertEqual(post_res.status_code, 200)
        self.assertTrue(post_res.get_json()["success"])
        self.assertEqual(post_res.get_json()["theme"], "dark")

        # POST invalid theme
        bad_res = self.client.post('/api/theme', json={"theme": "neon-rainbow"})
        self.assertEqual(bad_res.status_code, 400)
        self.assertFalse(bad_res.get_json()["success"])

    def test_api_persona_get_and_post(self):
        # GET current persona
        get_res = self.client.get('/api/persona')
        self.assertEqual(get_res.status_code, 200)
        data = get_res.get_json()
        self.assertIn("current_persona", data)
        self.assertIn("personas", data)

        # POST valid persona
        post_res = self.client.post('/api/persona', json={"persona": "witty_ai"})
        self.assertEqual(post_res.status_code, 200)
        self.assertTrue(post_res.get_json()["success"])
        self.assertEqual(post_res.get_json()["persona"], "witty_ai")

        # POST invalid persona
        bad_res = self.client.post('/api/persona', json={"persona": "non_existent_persona"})
        self.assertEqual(bad_res.status_code, 400)
        self.assertFalse(bad_res.get_json()["success"])

    def test_api_ratings_endpoints(self):
        # GET ratings
        get_res = self.client.get('/api/ratings')
        self.assertEqual(get_res.status_code, 200)
        self.assertIn("ratings", get_res.get_json())

        # POST valid rating
        post_res = self.client.post('/api/ratings', json={"content": "Rocket test", "rating": 1})
        self.assertEqual(post_res.status_code, 200)
        self.assertTrue(post_res.get_json()["success"])

        # POST missing content
        bad_res1 = self.client.post('/api/ratings', json={"rating": 1})
        self.assertEqual(bad_res1.status_code, 400)

        # POST invalid rating value
        bad_res2 = self.client.post('/api/ratings', json={"content": "Rocket", "rating": 5})
        self.assertEqual(bad_res2.status_code, 400)

    def test_api_schedule_endpoints(self):
        # GET schedule
        get_res = self.client.get('/api/schedule')
        self.assertEqual(get_res.status_code, 200)
        data = get_res.get_json()
        self.assertIn("scheduled_tweets", data)
        self.assertIn("weekly_calendar", data)
        self.assertIn("metrics", data)
        self.assertIn("pending", data["metrics"])
        self.assertIn("sent", data["metrics"])
        self.assertIn("cancelled", data["metrics"])

        # POST valid schedule
        post_res = self.client.post('/api/schedule', json={
            "content": "Scheduled falcon flight test",
            "scheduled_time": "2026-11-10 14:00:00",
            "persona": "witty_ai"
        })
        self.assertEqual(post_res.status_code, 200)
        tid = post_res.get_json()["id"]

        # Verify weekly_calendar reflects the newly scheduled pending tweet
        get_res_after = self.client.get('/api/schedule')
        calendar_after = get_res_after.get_json()["weekly_calendar"]
        # 2026-11-10 is a Tuesday
        self.assertGreaterEqual(calendar_after.get("Tue", 0), 1)

        # POST missing fields
        bad_post = self.client.post('/api/schedule', json={"content": ""})
        self.assertEqual(bad_post.status_code, 400)

        # DELETE (cancel) schedule
        del_res = self.client.delete('/api/schedule', json={"id": tid})
        self.assertEqual(del_res.status_code, 200)

        # DELETE non-existent schedule
        bad_del = self.client.delete('/api/schedule', json={"id": 999999})
        self.assertEqual(bad_del.status_code, 404)

    def test_joke_generator_personas(self):
        # Verify all persona structures and content generation
        for pkey in ["tactful_engineer", "witty_ai", "deadpan_astronomer"]:
            content = joke_generator.generate_content(persona=pkey)
            self.assertIsInstance(content, str)
            self.assertTrue(len(content) > 0)


class TestSchedulerModule(unittest.TestCase):

    def setUp(self):
        self.test_db = "test_sched_data.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        db.init_db(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_enqueue_and_process_due_tweets(self):
        # Empty content should raise ValueError
        with self.assertRaises(ValueError):
            scheduler.enqueue_scheduled_tweet("", "2026-01-01 00:00:00", db_path=self.test_db)

        # Enqueue past due tweet
        tid = scheduler.enqueue_scheduled_tweet(
            "Due scheduled joke!",
            "2020-01-01 00:00:00",
            persona="tactful_engineer",
            db_path=self.test_db
        )
        self.assertIsNotNone(tid)

        due = scheduler.get_pending_due_tweets(db_path=self.test_db)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["content"], "Due scheduled joke!")

        # Process due tweets
        processed = scheduler.process_due_tweets(dry_run=True, db_path=self.test_db)
        self.assertEqual(processed, 1)

        # Pending should now be 0
        due_after = scheduler.get_pending_due_tweets(db_path=self.test_db)
        self.assertEqual(len(due_after), 0)


class TestTrayCompanion(unittest.TestCase):

    def test_generate_tray_icon_image(self):
        img = tray.generate_tray_icon_image()
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (64, 64))

    @patch('webbrowser.open')
    def test_open_dashboard(self, mock_browser):
        tray.open_dashboard()
        mock_browser.assert_called_with("http://localhost:5000")

    @patch('urllib.request.urlopen')
    def test_trigger_check(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"success": true}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        tray.trigger_check()
        self.assertTrue(mock_urlopen.called)

    @patch('tray.TRAY_AVAILABLE', False)
    def test_run_tray_unavailable(self):
        result = tray.run_tray()
        self.assertFalse(result)

    @patch('tray.TRAY_AVAILABLE', True)
    @patch.dict(os.environ, {}, clear=True)
    def test_run_tray_headless_linux(self):
        with patch('sys.platform', 'linux'):
            result = tray.run_tray()
            self.assertFalse(result)


class TestPerformanceDigest(unittest.TestCase):
    def setUp(self):
        self.test_db = "test_digest_data.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        db.init_db(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_digest_calculation_empty_db(self):
        res = digest.generate_performance_digest(db_path=self.test_db, days=7)
        self.assertEqual(res["replies"]["total_replies"], 0)
        self.assertEqual(res["replies"]["total_likes"], 0)
        self.assertEqual(res["queue"]["total_scheduled"], 0)
        self.assertEqual(res["ratings"]["total_ratings"], 0)
        self.assertEqual(res["ratings"]["approval_rate"], 0.0)

    def test_digest_weekly_aggregation(self):
        # Insert simulated reply with likes & retweets
        db.record_reply("1001", db_path=self.test_db)
        db.update_engagement("1001", likes=15, retweets=4, db_path=self.test_db)

        # Insert scheduled tweet
        db.schedule_tweet("Test joke", "2026-11-15 12:00:00", persona="witty_ai", db_path=self.test_db)

        # Insert ratings (+1 and -1)
        db.record_joke_rating("Hilarious space joke", 1, notes="Super funny", db_path=self.test_db)
        db.record_joke_rating("Boring pun", -1, notes="Not funny", db_path=self.test_db)

        res = digest.generate_performance_digest(db_path=self.test_db, days=7)
        self.assertEqual(res["replies"]["total_replies"], 1)
        self.assertEqual(res["replies"]["total_likes"], 15)
        self.assertEqual(res["replies"]["total_retweets"], 4)
        self.assertEqual(res["replies"]["avg_likes_per_reply"], 15.0)

        self.assertEqual(res["queue"]["total_scheduled"], 1)
        self.assertEqual(res["queue"]["pending"], 1)
        self.assertEqual(res["queue"]["persona_distribution"].get("witty_ai"), 1)

        self.assertEqual(res["ratings"]["total_ratings"], 2)
        self.assertEqual(res["ratings"]["upvotes"], 1)
        self.assertEqual(res["ratings"]["downvotes"], 1)
        self.assertEqual(res["ratings"]["approval_rate"], 50.0)
        self.assertEqual(len(res["ratings"]["top_humor"]), 1)
        self.assertEqual(res["ratings"]["top_humor"][0]["content"], "Hilarious space joke")

    def test_digest_markdown_export(self):
        res = digest.generate_performance_digest(db_path=self.test_db, days=7)
        md = digest.export_digest_markdown(res)
        self.assertIn("Tactful Humor Bot — Weekly Performance Digest", md)
        self.assertIn("Total Replies Dispatched", md)
        self.assertIn("Humor Approval Rate", md)

    def test_api_digest_endpoint(self):
        client = dashboard.app.test_client()

        # Test default JSON format
        res = client.get('/api/digest?days=7')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["format"], "json")
        self.assertIn("replies", data["digest"])

        # Test Markdown format
        res_md = client.get('/api/digest?days=7&format=markdown')
        self.assertEqual(res_md.status_code, 200)
        data_md = res_md.get_json()
        self.assertTrue(data_md["success"])
        self.assertEqual(data_md["format"], "markdown")
        self.assertIn("Weekly Performance Digest", data_md["markdown"])


class TestWebhookDispatcher(unittest.TestCase):
    def setUp(self):
        webhook.DEFAULT_WEBHOOK_URL = ""
        webhook.DEFAULT_ADAPTER = "generic"

    def test_webhook_payload_formatting_slack(self):
        sample = {
            "window_days": 7,
            "replies": {"total_replies": 8, "total_likes": 32, "total_retweets": 12},
            "ratings": {"approval_rate": 88.5, "top_humor": [{"content": "Quantum humor"}]},
            "queue": {"sent": 4, "pending": 2}
        }
        payload = webhook.format_slack_payload(sample)
        self.assertEqual(payload["text"], "Weekly Performance Digest")
        self.assertGreater(len(payload["blocks"]), 1)
        self.assertIn("Tactful Humor Bot", payload["blocks"][0]["text"]["text"])

    def test_webhook_payload_formatting_discord(self):
        sample = {
            "window_days": 7,
            "replies": {"total_replies": 5, "total_likes": 15, "total_retweets": 3},
            "ratings": {"approval_rate": 100.0, "top_humor": []},
            "queue": {"sent": 2, "pending": 1}
        }
        payload = webhook.format_discord_payload(sample)
        self.assertIn("embeds", payload)
        self.assertEqual(len(payload["embeds"]), 1)
        self.assertIn("Tactful Humor Bot", payload["embeds"][0]["title"])

    @patch('urllib.request.urlopen')
    def test_webhook_dispatch_success_and_retry(self, mock_urlopen):
        # Test success on first try
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        ok, status = webhook.dispatch_webhook("https://example.com/webhook", {"test": 123})
        self.assertTrue(ok)
        self.assertEqual(status, 200)

        # Test retry failure
        mock_urlopen.side_effect = urllib.error.URLError("Network down")
        ok_fail, err = webhook.dispatch_webhook("https://example.com/webhook", {"test": 123}, max_retries=2)
        self.assertFalse(ok_fail)
        self.assertIn("Network down", err)

    @patch('urllib.request.urlopen')
    def test_api_webhook_endpoint(self, mock_urlopen):
        client = dashboard.app.test_client()

        # GET initially empty
        res = client.get('/api/webhook')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["configured"])

        # POST update URL and adapter
        res_post = client.post('/api/webhook', json={
            "webhook_url": "https://hooks.slack.com/services/T00/B00/XXXX",
            "adapter": "slack"
        })
        self.assertEqual(res_post.status_code, 200)
        self.assertTrue(res_post.get_json()["success"])

        # GET should now report configured
        res_after = client.get('/api/webhook')
        data_after = res_after.get_json()
        self.assertTrue(data_after["configured"])
        self.assertEqual(data_after["adapter"], "slack")

        # POST test dispatch with mock urlopen
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        res_dispatch = client.post('/api/webhook', json={"dispatch_now": True})
        self.assertEqual(res_dispatch.status_code, 200)
        self.assertTrue(res_dispatch.get_json()["success"])

        # POST update auto_dispatch and interval
        res_sched = client.post('/api/webhook', json={
            "auto_dispatch": True,
            "interval_hours": 24
        })
        self.assertEqual(res_sched.status_code, 200)
        data_sched = res_sched.get_json()
        self.assertTrue(data_sched["auto_dispatch"])
        self.assertEqual(data_sched["interval_hours"], 24)

    def test_check_and_dispatch_recurring_digest_disabled(self):
        webhook.AUTO_DISPATCH_ENABLED = False
        dispatched, msg = webhook.check_and_dispatch_recurring_digest()
        self.assertFalse(dispatched)
        self.assertIn("Auto-dispatch disabled", msg)

    def test_check_and_dispatch_recurring_digest_no_url(self):
        webhook.AUTO_DISPATCH_ENABLED = True
        webhook.DEFAULT_WEBHOOK_URL = ""
        dispatched, msg = webhook.check_and_dispatch_recurring_digest()
        self.assertFalse(dispatched)
        self.assertIn("No webhook URL", msg)

    @patch('webhook.dispatch_webhook')
    def test_check_and_dispatch_recurring_digest_due_and_throttle(self, mock_dispatch):
        webhook.AUTO_DISPATCH_ENABLED = True
        webhook.DEFAULT_WEBHOOK_URL = "https://example.com/digest"
        webhook.DISPATCH_INTERVAL_HOURS = 24
        webhook.LAST_DISPATCH_TIMESTAMP = 0.0

        mock_dispatch.return_value = (True, 200)

        # First run (not dispatched before)
        now = 1000000.0
        dispatched, msg = webhook.check_and_dispatch_recurring_digest(dry_run=False, current_time=now)
        self.assertTrue(dispatched)
        self.assertEqual(webhook.LAST_DISPATCH_TIMESTAMP, now)

        # Second run immediately after (should throttle)
        dispatched_second, msg_second = webhook.check_and_dispatch_recurring_digest(
            dry_run=False, current_time=now + 3600
        )
        self.assertFalse(dispatched_second)
        self.assertIn("not due yet", msg_second)

        # Run after 25 hours (should dispatch again)
        dispatched_third, msg_third = webhook.check_and_dispatch_recurring_digest(
            dry_run=False, current_time=now + (25 * 3600)
        )
        self.assertTrue(dispatched_third)


class TestDigestCLIAndDownload(unittest.TestCase):
    def setUp(self):
        self.app = dashboard.app.test_client()
        self.app.testing = True

    @patch('digest.generate_performance_digest')
    def test_digest_download_markdown(self, mock_gen):
        mock_gen.return_value = {
            "window_days": 7,
            "generated_at": "2026-11-06T00:00:00Z",
            "replies": {
                "total": 5,
                "engagement": {"total_likes": 10, "avg_likes": 2.0, "total_retweets": 4, "avg_retweets": 0.8}
            },
            "scheduled": {"total": 2, "pending": 1, "sent": 1, "cancelled": 0, "personas": {"witty_ai": 2}},
            "humor_ratings": {
                "total_reviews": 5, "approval_rate_percent": 100.0, "upvotes": 5, "downvotes": 0, "top_rated": []
            }
        }
        res = self.app.get('/api/digest/download?format=markdown')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'text/markdown')
        self.assertIn('attachment;', res.headers.get('Content-Disposition', ''))
        self.assertIn('.md', res.headers.get('Content-Disposition', ''))
        self.assertIn('# 🚀 Tactful Humor Bot', res.data.decode('utf-8'))

    @patch('digest.generate_performance_digest')
    def test_digest_download_json(self, mock_gen):
        import json as json_mod
        mock_gen.return_value = {"window_days": 7, "replies": {"total": 0}}
        res = self.app.get('/api/digest/download?format=json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'application/json')
        self.assertIn('attachment;', res.headers.get('Content-Disposition', ''))
        self.assertIn('.json', res.headers.get('Content-Disposition', ''))
        data = json_mod.loads(res.data.decode('utf-8'))
        self.assertEqual(data["window_days"], 7)

    @patch('generate_digest.generate_performance_digest')
    def test_generate_digest_cli_save_files(self, mock_gen):
        import generate_digest
        import json as json_mod
        import tempfile
        import shutil

        mock_gen.return_value = {
            "window_days": 7,
            "generated_at": "2026-11-06T00:00:00Z",
            "replies": {
                "total": 1,
                "engagement": {"total_likes": 0, "avg_likes": 0, "total_retweets": 0, "avg_retweets": 0}
            },
            "scheduled": {"total": 0, "pending": 0, "sent": 0, "cancelled": 0, "personas": {}},
            "humor_ratings": {
                "total_reviews": 0, "approval_rate_percent": 0.0, "upvotes": 0, "downvotes": 0, "top_rated": []
            }
        }

        temp_dir = tempfile.mkdtemp()
        try:
            saved = generate_digest.save_digest_files(mock_gen.return_value, out_dir=temp_dir, export_format="both")
            self.assertIn("markdown", saved)
            self.assertIn("json", saved)
            self.assertTrue(os.path.exists(saved["markdown"]))
            self.assertTrue(os.path.exists(saved["json"]))

            with open(saved["markdown"], "r", encoding="utf-8") as f:
                md_text = f.read()
                self.assertIn("# 🚀 Tactful Humor Bot", md_text)

            with open(saved["json"], "r", encoding="utf-8") as f:
                json_data = json_mod.load(f)
                self.assertEqual(json_data["window_days"], 7)

            # Test export_format="all" including HTML
            saved_all = generate_digest.save_digest_files(mock_gen.return_value, out_dir=temp_dir, export_format="all")
            self.assertIn("markdown", saved_all)
            self.assertIn("html", saved_all)
            self.assertIn("json", saved_all)
            self.assertTrue(os.path.exists(saved_all["html"]))
            with open(saved_all["html"], "r", encoding="utf-8") as f:
                html_text = f.read()
                self.assertIn("<!DOCTYPE html>", html_text)
        finally:
            shutil.rmtree(temp_dir)


class TestEnrichedPerformanceDigest(unittest.TestCase):
    """Validates multi-window delta comparisons and operational health scorecard generation."""

    def setUp(self):
        self.test_db = "test_enriched_digest.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        db.init_db(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_compute_delta_helper(self):
        """Tests delta math and percentage calculations across boundary values."""
        # 50% increase
        d1 = digest._compute_delta(15, 10)
        self.assertEqual(d1["diff"], 5)
        self.assertEqual(d1["pct"], 50.0)

        # 50% decrease
        d2 = digest._compute_delta(5, 10)
        self.assertEqual(d2["diff"], -5)
        self.assertEqual(d2["pct"], -50.0)

        # Growth from zero base
        d3 = digest._compute_delta(10, 0)
        self.assertEqual(d3["diff"], 10)
        self.assertEqual(d3["pct"], 100.0)

        # Zero to zero
        d4 = digest._compute_delta(0, 0)
        self.assertEqual(d4["diff"], 0)
        self.assertEqual(d4["pct"], 0.0)

    def test_multi_window_deltas_and_scorecard(self):
        """Verifies multi-window query aggregation, deltas, and health scorecard states."""
        # Insert previous period reply (8 days ago)
        with db.get_db_connection(self.test_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO replied_tweets (tweet_id, replied_at, likes, retweets)
                VALUES (101, datetime('now', '-8 days'), 20, 5)
                """
            )
            # Insert current period reply (2 days ago)
            cursor.execute(
                """
                INSERT INTO replied_tweets (tweet_id, replied_at, likes, retweets)
                VALUES (102, datetime('now', '-2 days'), 50, 15)
                """
            )
            # Insert previous period scheduled tweet (sent 10 days ago)
            cursor.execute(
                """
                INSERT INTO scheduled_tweets
                (content, scheduled_time, persona, status, created_at)
                VALUES ('Old joke', datetime('now', '-10 days'), 'tactful_engineer',
                        'sent', datetime('now', '-10 days'))
                """
            )
            # Insert current period scheduled tweet (sent 1 day ago)
            cursor.execute(
                """
                INSERT INTO scheduled_tweets
                (content, scheduled_time, persona, status, created_at)
                VALUES ('New joke', datetime('now', '-1 day'), 'tactful_engineer',
                        'sent', datetime('now', '-1 day'))
                """
            )
            # Insert ratings (positive sentiment)
            cursor.execute(
                """
                INSERT INTO joke_ratings (content, rating, notes, created_at)
                VALUES ('Great joke!', 1, 'Operator approved', datetime('now', '-1 day'))
                """
            )
            conn.commit()

        d = digest.generate_performance_digest(db_path=self.test_db, days=7)

        # Replies deltas: cur=1, prev=1 -> diff=0, pct=0.0
        self.assertEqual(d["deltas"]["replies"]["current"], 1)
        self.assertEqual(d["deltas"]["replies"]["previous"], 1)
        self.assertEqual(d["deltas"]["replies"]["diff"], 0)

        # Likes deltas: cur=50, prev=20 -> diff=30, pct=150.0
        self.assertEqual(d["deltas"]["likes"]["current"], 50)
        self.assertEqual(d["deltas"]["likes"]["previous"], 20)
        self.assertEqual(d["deltas"]["likes"]["diff"], 30)
        self.assertEqual(d["deltas"]["likes"]["pct"], 150.0)

        # Retweets deltas: cur=15, prev=5 -> diff=10, pct=200.0
        self.assertEqual(d["deltas"]["retweets"]["current"], 15)
        self.assertEqual(d["deltas"]["retweets"]["previous"], 5)
        self.assertEqual(d["deltas"]["retweets"]["diff"], 10)
        self.assertEqual(d["deltas"]["retweets"]["pct"], 200.0)

        # Queue sent deltas: cur=1, prev=1
        self.assertEqual(d["deltas"]["queue_sent"]["current"], 1)
        self.assertEqual(d["deltas"]["queue_sent"]["previous"], 1)

        # Health scorecard
        sc = d["health_scorecard"]
        self.assertTrue(sc["db_connected"])
        self.assertEqual(sc["queue_backlog"], 0)
        self.assertEqual(sc["sentiment_status"], "Positive")
        self.assertEqual(sc["overall_health"], "Healthy")

        # Verify markdown export format includes scorecard and deltas
        md = digest.export_digest_markdown(d)
        self.assertIn("## 🩺 System Operational Health Scorecard", md)
        self.assertIn("- **Overall Status:** Healthy", md)
        self.assertIn("+30 (+150.0%) vs prior 7d", md)

    def test_scorecard_sentiment_thresholds(self):
        """Verifies neutral, moderate, and needs review sentiment thresholds in scorecard."""
        # Empty DB (no ratings)
        d_empty = digest.generate_performance_digest(db_path=self.test_db, days=7)
        self.assertEqual(d_empty["health_scorecard"]["sentiment_status"], "Neutral (No Data)")

        # Negative ratings (low approval)
        with db.get_db_connection(self.test_db) as conn:
            cursor = conn.cursor()
            for _ in range(5):
                cursor.execute(
                    "INSERT INTO joke_ratings (content, rating, created_at) VALUES ('Bad', -1, datetime('now'))"
                )
            conn.commit()

        d_neg = digest.generate_performance_digest(db_path=self.test_db, days=7)
        self.assertEqual(d_neg["health_scorecard"]["sentiment_status"], "Needs Review")

    def test_html_export_and_threshold_alerts(self):
        """Verifies HTML report formatting and threshold-based performance alerts."""
        # Test alert trigger when backlog is high and ratings are low
        d = digest.generate_performance_digest(db_path=self.test_db, days=7)
        d["queue"]["pending"] = 60  # > 50 threshold
        d["ratings"]["total_ratings"] = 10
        d["ratings"]["approval_rate"] = 30.0  # < 40% threshold

        alerts = digest.evaluate_performance_alerts(d)
        self.assertEqual(len(alerts), 2)
        alert_types = [a["type"] for a in alerts]
        self.assertIn("queue_backlog_high", alert_types)
        self.assertIn("low_humor_approval", alert_types)

        # Attach evaluated alerts to digest dictionary
        d["alerts"] = alerts

        # Verify export_digest_html output
        html = digest.export_digest_html(d)
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("Tactful Humor Bot — Performance Digest", html)
        self.assertIn("Active System Anomaly Alerts (2)", html)
        self.assertIn("<h2>🩺 System Operational Health</h2>", html)
        self.assertIn("<h2>📈 Public Replies &amp; Engagement Deltas</h2>", html)
        self.assertIn("<h2>🌐 Social Federation Reach</h2>", html)

    def test_top_reply_extraction_and_report_rendering(self):
        """Verifies top-performing reply extraction and presentation in HTML/MD reports."""
        with db.get_db_connection(self.test_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO replied_tweets (tweet_id, replied_at, likes, retweets)
                VALUES (501, datetime('now', '-2 days'), 10, 2),
                       (502, datetime('now', '-1 day'), 45, 12)
                """
            )
            conn.commit()

        d = digest.generate_performance_digest(db_path=self.test_db, days=7)
        self.assertIsNotNone(d["replies"]["top_reply"])
        self.assertEqual(d["replies"]["top_reply"]["tweet_id"], "502")
        self.assertEqual(d["replies"]["top_reply"]["likes"], 45)
        self.assertEqual(d["replies"]["top_reply"]["retweets"], 12)

        # Verify Markdown rendering
        md = digest.export_digest_markdown(d)
        self.assertIn("Top Performing Reply", md)
        self.assertIn("502", md)
        self.assertIn("45 likes", md)

        # Verify HTML rendering
        html = digest.export_digest_html(d)
        self.assertIn("Top Performing Reply", html)
        self.assertIn("502", html)
        self.assertIn("45 likes", html)

        # Verify Webhook formatting
        import webhook
        slack_p = webhook.format_slack_payload(d)
        self.assertTrue(any("Top Reply" in b.get("text", {}).get("text", "") for b in slack_p.get("blocks", [])))

        discord_p = webhook.format_discord_payload(d)
        fields = discord_p.get("embeds", [{}])[0].get("fields", [])
        self.assertTrue(any(f.get("name") == "Top Performing Reply" for f in fields))

    def test_download_html_digest_endpoint(self):
        """Verifies /api/digest/download returns styled HTML attachment when format=html."""
        import dashboard
        client = dashboard.app.test_client()
        res = client.get('/api/digest/download?format=html')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'text/html')
        self.assertIn('.html', res.headers.get('Content-Disposition', ''))
        self.assertIn(b'<!DOCTYPE html>', res.data)


class TestAsyncMainLoop(unittest.IsolatedAsyncioTestCase):
    @patch('bot.db.init_db')
    @patch('bot.get_twitter_client')
    async def test_main_loop_dry_run_exit_condition(self, mock_get_client, mock_init_db):
        with patch.object(sys, 'argv', ['bot.py', '--dry-run']):
            await main()
        self.assertTrue(mock_init_db.called)


class TestSyndication(unittest.TestCase):
    """Unit tests for multi-platform federation syndication (Mastodon and Bluesky)."""

    def setUp(self):
        import syndication
        # Save module state
        self.orig_mastodon_enabled = syndication.MASTODON_ENABLED
        self.orig_mastodon_instance = syndication.MASTODON_INSTANCE_URL
        self.orig_mastodon_token = syndication.MASTODON_ACCESS_TOKEN
        self.orig_bluesky_enabled = syndication.BLUESKY_ENABLED
        self.orig_bluesky_handle = syndication.BLUESKY_HANDLE
        self.orig_bluesky_password = syndication.BLUESKY_APP_PASSWORD

    def tearDown(self):
        import syndication
        syndication.MASTODON_ENABLED = self.orig_mastodon_enabled
        syndication.MASTODON_INSTANCE_URL = self.orig_mastodon_instance
        syndication.MASTODON_ACCESS_TOKEN = self.orig_mastodon_token
        syndication.BLUESKY_ENABLED = self.orig_bluesky_enabled
        syndication.BLUESKY_HANDLE = self.orig_bluesky_handle
        syndication.BLUESKY_APP_PASSWORD = self.orig_bluesky_password

    def test_format_payloads(self):
        import syndication
        m_payload = syndication.format_mastodon_payload("Hello Fediverse!")
        self.assertEqual(m_payload["status"], "Hello Fediverse!")
        self.assertEqual(m_payload["visibility"], "public")

        b_payload = syndication.format_bluesky_payload("Hello Bluesky!")
        self.assertEqual(b_payload["text"], "Hello Bluesky!")
        self.assertIn("createdAt", b_payload)
        self.assertEqual(b_payload["$type"], "app.bsky.feed.post")

    def test_dispatch_mastodon_dry_run(self):
        import syndication
        success, status = syndication.dispatch_mastodon("Dry run status", dry_run=True)
        self.assertTrue(success)
        self.assertEqual(status, "200 OK (Dry Run)")

    def test_dispatch_bluesky_dry_run(self):
        import syndication
        success, status = syndication.dispatch_bluesky("Dry run status", dry_run=True)
        self.assertTrue(success)
        self.assertEqual(status, "200 OK (Dry Run)")

    def test_dispatch_not_configured(self):
        import syndication
        syndication.MASTODON_ACCESS_TOKEN = ""
        success, err = syndication.dispatch_mastodon("Live text", dry_run=False)
        self.assertFalse(success)
        self.assertIn("not configured", err)

        syndication.BLUESKY_HANDLE = ""
        success_b, err_b = syndication.dispatch_bluesky("Live text", dry_run=False)
        self.assertFalse(success_b)
        self.assertIn("not configured", err_b)

    @patch('urllib.request.urlopen')
    def test_dispatch_mastodon_live(self, mock_urlopen):
        import syndication
        syndication.MASTODON_INSTANCE_URL = "https://mastodon.social"
        syndication.MASTODON_ACCESS_TOKEN = "secret_token_123"

        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        success, status = syndication.dispatch_mastodon(
            "Live status test",
            dry_run=False
        )
        self.assertTrue(success)
        self.assertEqual(status, "200")

    def test_dispatch_syndicated_post_multi(self):
        import syndication
        syndication.MASTODON_ENABLED = True
        syndication.BLUESKY_ENABLED = True

        results = syndication.dispatch_syndicated_post("Federated greeting", dry_run=True)
        self.assertIn("mastodon", results)
        self.assertIn("bluesky", results)
        self.assertTrue(results["mastodon"]["success"])
        self.assertEqual(results["mastodon"]["status"], "200 OK (Dry Run)")
        self.assertTrue(results["bluesky"]["success"])
        self.assertEqual(results["bluesky"]["status"], "200 OK (Dry Run)")

    def test_dashboard_syndication_endpoints(self):
        import dashboard
        import syndication
        client = dashboard.app.test_client()

        # GET syndication settings
        get_res = client.get('/api/syndication')
        self.assertEqual(get_res.status_code, 200)
        data = get_res.get_json()
        self.assertIn("mastodon", data)
        self.assertIn("bluesky", data)

        # POST update syndication settings
        update_res = client.post('/api/syndication', json={
            "mastodon_enabled": True,
            "mastodon_instance_url": "https://mastodon.social",
            "mastodon_access_token": "test_token_12345",
            "bluesky_enabled": True,
            "bluesky_handle": "muskbot.bsky.social",
            "bluesky_app_password": "test-password-abcd"
        })
        self.assertEqual(update_res.status_code, 200)
        up_data = update_res.get_json()
        self.assertTrue(up_data["success"])
        self.assertTrue(syndication.MASTODON_ENABLED)
        self.assertEqual(syndication.MASTODON_ACCESS_TOKEN, "test_token_12345")
        self.assertTrue(syndication.BLUESKY_ENABLED)
        self.assertEqual(syndication.BLUESKY_HANDLE, "muskbot.bsky.social")

        # GET to verify masked credentials
        check_res = client.get('/api/syndication')
        check_data = check_res.get_json()
        self.assertTrue(check_data["mastodon"]["token_configured"])
        self.assertEqual(check_data["mastodon"]["masked_token"], "test...2345")
        self.assertTrue(check_data["bluesky"]["password_configured"])

        # POST dry-run broadcast
        bcast_res = client.post('/api/syndication', json={
            "broadcast_now": True,
            "text": "Live syndication endpoint test"
        })
        self.assertEqual(bcast_res.status_code, 200)
        b_data = bcast_res.get_json()
        self.assertTrue(b_data["success"])
        self.assertIn("results", b_data)
        self.assertIn("mastodon", b_data["results"])
        self.assertIn("bluesky", b_data["results"])

    def test_federation_engagement_polling_and_metrics(self):
        import db
        import syndication
        import digest
        import dashboard

        test_db = "test_fed_metrics.db"
        try:
            db.init_db(test_db)

            # Record syndicated posts
            m_id = db.record_syndicated_post(
                "mastodon", "Test Mastodon post", remote_id="m_1001", status="sent", db_path=test_db
            )
            b_id = db.record_syndicated_post(
                "bluesky", "Test Bluesky post", remote_id="b_1001", status="sent", db_path=test_db
            )
            self.assertIsNotNone(m_id)
            self.assertIsNotNone(b_id)

            # Update metrics manually
            self.assertTrue(db.update_syndication_metrics(m_id, likes=12, shares=3, db_path=test_db))
            self.assertTrue(db.update_syndication_metrics(b_id, likes=25, shares=7, db_path=test_db))

            # Fetch polling list
            to_poll = db.get_syndicated_posts_for_metrics_polling(limit=10, db_path=test_db)
            self.assertEqual(len(to_poll), 2)

            # Summary metrics
            summary = db.get_syndication_summary_metrics(db_path=test_db)
            self.assertEqual(summary["total_posts"], 2)
            self.assertEqual(summary["platforms"]["mastodon"]["likes"], 12)
            self.assertEqual(summary["platforms"]["bluesky"]["shares"], 7)

            # Polling engine
            poll_result = syndication.poll_all_syndicated_metrics(limit=10, dry_run=True, db_path=test_db)
            self.assertEqual(poll_result["updated_posts"], 2)
            self.assertGreater(poll_result["likes_polled"], 0)

            # Digest incorporation
            d = digest.generate_performance_digest(db_path=test_db)
            self.assertIn("syndication", d)
            self.assertEqual(d["syndication"]["total_posts"], 2)
            md = digest.export_digest_markdown(d)
            self.assertIn("Social Federation Multi-Platform Reach", md)

            # Dashboard API routes
            client = dashboard.app.test_client()
            res_metrics = client.get('/api/syndication/metrics')
            self.assertEqual(res_metrics.status_code, 200)
            data_m = res_metrics.get_json()
            self.assertTrue(data_m["success"])
            self.assertIn("summary", data_m)

            res_poll = client.post('/api/syndication/poll')
            self.assertEqual(res_poll.status_code, 200)
            data_p = res_poll.get_json()
            self.assertTrue(data_p["success"])
            self.assertIn("poll_results", data_p)

        finally:
            if os.path.exists(test_db):
                os.remove(test_db)

    def test_cli_digest_generator_and_custom_options(self):
        """Tests generate_digest CLI utility with prefix, quiet mode, and formats."""
        import generate_digest
        import json
        import shutil
        import tempfile

        test_dir = tempfile.mkdtemp()
        test_db = os.path.join(test_dir, "test_cli.db")

        try:
            db.init_db(test_db)
            db.record_reply(55501, db_path=test_db)
            db.update_engagement(55501, likes=10, retweets=2, db_path=test_db)

            # Test main invocation with --prefix, --quiet, and all formats
            exit_code = generate_digest.main([
                "--days", "14",
                "--db-path", test_db,
                "--out-dir", test_dir,
                "--prefix", "weekly_report",
                "--format", "all",
                "--quiet",
                "--json-indent", "4"
            ])
            self.assertEqual(exit_code, 0)

            # Verify files were created with prefix
            files = os.listdir(test_dir)
            md_files = [f for f in files if f.startswith("weekly_report_") and f.endswith(".md")]
            html_files = [f for f in files if f.startswith("weekly_report_") and f.endswith(".html")]
            json_files = [f for f in files if f.startswith("weekly_report_") and f.endswith(".json")]

            self.assertEqual(len(md_files), 1)
            self.assertEqual(len(html_files), 1)
            self.assertEqual(len(json_files), 1)

            # Verify contents
            with open(os.path.join(test_dir, json_files[0]), "r", encoding="utf-8") as jf:
                data = json.load(jf)
                self.assertEqual(data["window_days"], 14)
                self.assertEqual(data["replies"]["total_replies"], 1)

            # Test stdout format
            stdout_code = generate_digest.main([
                "--db-path", test_db,
                "--format", "stdout",
                "--quiet"
            ])
            self.assertEqual(stdout_code, 0)

            # Test dashboard download with custom prefix and days bound check
            client = dashboard.app.test_client()
            res_dl = client.get('/api/digest/download?days=30&prefix=custom_audit&format=html')
            self.assertEqual(res_dl.status_code, 200)
            self.assertIn("custom_audit_", res_dl.headers.get("Content-Disposition", ""))

        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_content_splitter_and_syndication_chunking(self):
        """Tests text splitting into threads for Twitter, Bluesky, Mastodon, and /api/split-preview."""
        import splitter
        import syndication

        # 1. Short text (no splitting needed)
        short_text = "Standard short humor tweet."
        chunks_tw = splitter.split_for_platform(short_text, "twitter")
        self.assertEqual(len(chunks_tw), 1)
        self.assertEqual(chunks_tw[0], short_text)

        # 2. Long text exceeding Twitter (280) and Bluesky (300) limits
        long_text = "Falcon Heavy launch test: " + ("orbital telemetry data validation check " * 12)
        self.assertGreater(len(long_text), 300)

        chunks_tw = splitter.split_for_platform(long_text, "twitter")
        self.assertGreaterEqual(len(chunks_tw), 2)
        for chunk in chunks_tw:
            self.assertLessEqual(len(chunk), 280)
            self.assertTrue("[" in chunk and "]" in chunk)

        chunks_bsky = splitter.split_for_platform(long_text, "bluesky")
        for chunk in chunks_bsky:
            self.assertLessEqual(len(chunk), 300)

        # 3. Test syndication dispatch with auto_split enabled
        res = syndication.dispatch_syndicated_post(
            long_text,
            platforms=["mastodon", "bluesky"],
            dry_run=True,
            auto_split=True
        )
        self.assertIn("mastodon", res)
        self.assertIn("bluesky", res)
        self.assertTrue(res["mastodon"]["success"])
        self.assertTrue(res["bluesky"]["success"])
        self.assertGreaterEqual(res["bluesky"]["parts"], 2)

        # 4. Test /api/split-preview endpoint
        client = dashboard.app.test_client()
        res_prev = client.post('/api/split-preview', json={"text": long_text})
        self.assertEqual(res_prev.status_code, 200)
        pdata = res_prev.get_json()
        self.assertIn("twitter", pdata)
        self.assertIn("bluesky", pdata)
        self.assertIn("mastodon", pdata)
        self.assertEqual(pdata["twitter"]["limit"], 280)
        self.assertEqual(pdata["bluesky"]["limit"], 300)
        self.assertEqual(pdata["mastodon"]["limit"], 500)
        self.assertGreaterEqual(len(pdata["twitter"]["chunks"]), 2)

        # Error handling on invalid payload
        res_bad = client.post('/api/split-preview', json={"text": 12345})
        self.assertEqual(res_bad.status_code, 400)


if __name__ == "__main__":
    unittest.main()
