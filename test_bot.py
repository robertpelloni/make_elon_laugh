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


class TestAsyncMainLoop(unittest.IsolatedAsyncioTestCase):
    @patch('bot.db.init_db')
    @patch('bot.get_twitter_client')
    async def test_main_loop_dry_run_exit_condition(self, mock_get_client, mock_init_db):
        with patch.object(sys, 'argv', ['bot.py', '--dry-run']):
            await main()
        self.assertTrue(mock_init_db.called)


if __name__ == "__main__":
    unittest.main()
