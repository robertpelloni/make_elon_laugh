import os
import sqlite3
import unittest
from unittest.mock import patch
from auth import validate_api_keys, get_twitter_client
import sys
from bot import validate_tweet_content, validate_api_tweets, main
from rate_limiter import async_call_api_with_backoff, RateLimitExceededException
import db
from analytics import AnalyticsTracker
import tweepy
from joke_generator import generate_joke


class TestBotValidation(unittest.TestCase):

    def test_validate_api_keys_valid(self):
        # Should return True and not raise an exception
        result = validate_api_keys(
            "valid_bearer",
            "valid_key",
            "valid_secret",
            "valid_token",
            "valid_token_secret"
        )
        self.assertTrue(result)

    def test_validate_api_keys_empty_value(self):
        # Should raise ValueError because one value is empty
        with self.assertRaisesRegex(ValueError, "API key validation failed: API_KEY is empty."):
            validate_api_keys(
                "valid_bearer",
                "",
                "valid_secret",
                "valid_token",
                "valid_token_secret"
            )

    def test_validate_api_keys_none_value(self):
        # Should raise ValueError because one value is None
        with self.assertRaisesRegex(ValueError, "API key validation failed: ACCESS_TOKEN is empty."):
            validate_api_keys(
                "valid_bearer",
                "valid_key",
                "valid_secret",
                None,
                "valid_token_secret"
            )

    def test_validate_api_keys_default_placeholder(self):
        # Should raise ValueError because a value still has the YOUR_ prefix
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
        # Edge Case 1: Extra whitespace in env vars shouldn't crash auth
        cleaned_keys = validate_api_keys(
            " valid_bearer ",
            "valid_key",
            "valid_secret",
            "valid_token",
            "valid_token_secret"
        )
        self.assertEqual(cleaned_keys["BEARER_TOKEN"], "valid_bearer")

    def test_validate_api_keys_raises_type_error_for_non_string_inputs(self):
        # Edge Case 3: Integer passed instead of string (e.g., raw env var misread)
        with self.assertRaisesRegex(TypeError, "API key validation failed: API_SECRET must be a string."):
            validate_api_keys(
                "valid_bearer",
                "valid_key",
                12345,
                "valid_token",
                "valid_token_secret"
            )

    def test_validate_tweet_content_valid(self):
        # Should return the cleaned string
        self.assertEqual(validate_tweet_content("This is a valid tweet! 🚀"), "This is a valid tweet! 🚀")

    def test_validate_tweet_content_empty(self):
        # Should raise ValueError if tweet is empty
        with self.assertRaisesRegex(ValueError, "Tweet content validation failed: Content is empty."):
            validate_tweet_content("")

    def test_validate_tweet_content_whitespace(self):
        # Should raise ValueError if tweet is just whitespace
        with self.assertRaisesRegex(ValueError, "Tweet content validation failed: Content is empty."):
            validate_tweet_content("   \n   ")

    def test_validate_tweet_content_too_long(self):
        # Should raise ValueError if tweet exceeds 280 characters
        long_tweet = "A" * 281
        with self.assertRaisesRegex(ValueError, "Tweet content validation failed: Content exceeds 280 characters"):
            validate_tweet_content(long_tweet)

    def test_validate_tweet_content_max_length(self):
        # Should not raise exception if tweet is exactly 280 characters
        max_length_tweet = "A" * 280
        self.assertEqual(validate_tweet_content(max_length_tweet), max_length_tweet)

    def test_validate_tweet_content_strips_padding_before_length_check(self):
        # Edge Case 2: Whitespace pushing a 280 char tweet to 281 chars shouldn't fail
        max_length_tweet = "A" * 280
        padded_tweet = f" {max_length_tweet} \n"
        # Should succeed because stripped length is 280
        self.assertEqual(validate_tweet_content(padded_tweet), max_length_tweet)

    def test_validate_tweet_content_raises_type_error_for_non_string_inputs(self):
        # Edge Case 3: Non-string tweet content
        with self.assertRaisesRegex(TypeError, "Tweet content validation failed: Content must be a string."):
            validate_tweet_content(12345)


class TestMalformedAPIResponseFallback(unittest.TestCase):

    class MockTweet:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    def test_validate_api_tweets_valid(self):
        # Should return list of valid tweets
        tweets = [self.MockTweet(id=123, text="Hello"), self.MockTweet(id=456, text="World")]
        valid = validate_api_tweets(tweets)
        self.assertEqual(len(valid), 2)
        self.assertEqual(valid[0].id, 123)

    def test_validate_api_tweets_missing_id(self):
        # Should filter out tweets without an ID
        tweets = [self.MockTweet(text="No ID"), self.MockTweet(id=456, text="World")]
        valid = validate_api_tweets(tweets)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0].id, 456)

    def test_validate_api_tweets_missing_text(self):
        # Should filter out tweets without text
        tweets = [self.MockTweet(id=123), self.MockTweet(id=456, text="World")]
        valid = validate_api_tweets(tweets)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0].text, "World")

    def test_validate_api_tweets_not_iterable(self):
        # Should return empty list if API returns a string or None instead of a list
        self.assertEqual(validate_api_tweets(None), [])
        self.assertEqual(validate_api_tweets("Not a list"), [])

    def test_validate_api_tweets_boundary_empty_collection(self):
        # GAP REPORT 1: Should cleanly handle an explicitly empty collection
        self.assertEqual(validate_api_tweets([]), [])
        self.assertEqual(validate_api_tweets(tuple()), [])

    def test_validate_api_tweets_boundary_iterable_dictionary(self):
        # GAP REPORT 2: Should safely skip over dictionary keys which are iterable but missing attributes
        mock_payload = {"error": "rate_limited", "status": 429}
        self.assertEqual(validate_api_tweets(mock_payload), [])

    def test_validate_api_tweets_boundary_falsy_id(self):
        # GAP REPORT 3: Should accept a valid tweet with a falsy integer ID of 0
        tweets = [self.MockTweet(id=0, text="Valid zero ID")]
        valid = validate_api_tweets(tweets)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0].id, 0)
        self.assertEqual(valid[0].text, "Valid zero ID")

    def test_validate_api_tweets_boundary_empty_string_text(self):
        # GAP REPORT 4: Should accept a valid tweet even if the text string is empty
        # (Though our outbound validation would block sending an empty string, the parser should accept incoming)
        tweets = [self.MockTweet(id=789, text="")]
        valid = validate_api_tweets(tweets)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0].text, "")


class TestRateLimiterAsync(unittest.IsolatedAsyncioTestCase):

    async def test_successful_call_no_backoff(self):
        # A normal call shouldn't trigger any delays
        async def success_api():
            return "success"

        result = await async_call_api_with_backoff(success_api)
        self.assertEqual(result, "success")

    async def test_backoff_and_eventual_success(self):
        # Should raise 429 twice, then succeed
        calls = {"count": 0}

        async def mock_api_429():
            calls["count"] += 1
            if calls["count"] < 3:
                raise Exception("API error 429 Too Many Requests")
            return "eventual_success"

        # We speed up the backoff for testing by overriding defaults
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
        # Should exhaust all retries and throw RateLimitExceededException
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
        # Should raise TimeoutError twice, then succeed
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
        # Should exhaust all retries on ConnectionError and throw RateLimitExceededException
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
        # Should immediately fail if it's not a rate limit or latency error (e.g., 401 Unauthorized)
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
        # Ensure fresh DB for each test
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        db.init_db(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_database_initialization(self):
        self.assertTrue(os.path.exists(self.test_db))

    def test_record_and_check_reply(self):
        # Should return False initially
        self.assertFalse(db.has_replied("12345", self.test_db))

        # Record it
        db.record_reply("12345", self.test_db)

        # Should now return True
        self.assertTrue(db.has_replied("12345", self.test_db))

    def test_record_duplicate_reply_safe(self):
        # Recording the same ID twice shouldn't crash (INSERT OR IGNORE)
        db.record_reply("999", self.test_db)
        db.record_reply("999", self.test_db)
        self.assertTrue(db.has_replied("999", self.test_db))

    def test_update_and_retrieve_engagement(self):
        db.record_reply("888", self.test_db)
        # Verify initial state is 0
        from dashboard import get_db_stats
        with patch('dashboard.db.DB_PATH', self.test_db):
            stats = get_db_stats()
            self.assertEqual(stats["total_likes"], 0)
            self.assertEqual(stats["total_retweets"], 0)

        # Update engagement
        db.update_engagement("888", 10, 5, self.test_db)

        # Verify updated state
        with patch('dashboard.db.DB_PATH', self.test_db):
            stats = get_db_stats()
            self.assertEqual(stats["total_likes"], 10)
            self.assertEqual(stats["total_retweets"], 5)

            # Check the recent replies array contains the data
            recent = stats["recent_replies"][0]
            self.assertEqual(recent["tweet_id"], "888")
            self.assertEqual(recent["likes"], 10)
            self.assertEqual(recent["retweets"], 5)

    def test_get_tweets_for_engagement_polling(self):
        db.record_reply("111", self.test_db)
        db.record_reply("222", self.test_db)

        # Should return the IDs
        tweets = db.get_tweets_for_engagement_polling(limit=5, db_path=self.test_db)
        self.assertIn("111", tweets)
        self.assertIn("222", tweets)
        self.assertEqual(len(tweets), 2)

    @patch('db.get_db_connection')
    def test_db_exceptions_handled_gracefully(self, mock_get_db):
        # Simulate an SQLite error to ensure the fail-safe works
        mock_get_db.side_effect = sqlite3.Error("Simulated DB error")

        # has_replied should return False on error to prevent crashing the loop
        self.assertFalse(db.has_replied("123", self.test_db))

        # record_reply should catch the error and not crash
        try:
            db.record_reply("123", self.test_db)
        except Exception:
            self.fail("record_reply raised an exception instead of catching it.")

        # init_db should raise the error so we know it failed at boot
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
        # Ensure the logger was called to print the summary
        self.assertTrue(mock_logger.called)


class TestAuthModule(unittest.TestCase):
    def test_get_twitter_client_success(self):
        # We must mock the constants imported in auth.py directly
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


class TestAsyncMainLoop(unittest.IsolatedAsyncioTestCase):
    @patch('bot.db.init_db')
    @patch('bot.get_twitter_client')
    async def test_main_loop_dry_run_exit_condition(self, mock_get_client, mock_init_db):
        # Edge Case: Verify the async main loop correctly exits when iterations are exhausted in dry-run
        # We need to patch sys.argv so argparse sees --dry-run
        with patch.object(sys, 'argv', ['bot.py', '--dry-run']):
            # This should complete without hanging infinitely
            await main()

        # Verify db was initialized
        self.assertTrue(mock_init_db.called)


if __name__ == "__main__":
    unittest.main()
