import os
import unittest
from unittest.mock import patch
from bot import validate_api_keys, validate_tweet_content
from rate_limiter import call_api_with_backoff, RateLimitExceededException

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
        with self.assertRaisesRegex(ValueError, "API key validation failed: BEARER_TOKEN is still set to the default placeholder 'YOUR_BEARER_TOKEN'."):
            validate_api_keys(
                "YOUR_BEARER_TOKEN",
                "valid_key",
                "valid_secret",
                "valid_token",
                "valid_token_secret"
            )

    def test_validate_tweet_content_valid(self):
        # Should return True and not raise an exception
        self.assertTrue(validate_tweet_content("This is a valid tweet! 🚀"))

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
        self.assertTrue(validate_tweet_content(max_length_tweet))

class TestRateLimiter(unittest.TestCase):

    def test_successful_call_no_backoff(self):
        # A normal call shouldn't trigger any delays
        def success_api():
            return "success"

        result = call_api_with_backoff(success_api)
        self.assertEqual(result, "success")

    def test_backoff_and_eventual_success(self):
        # Should raise 429 twice, then succeed
        calls = {"count": 0}

        def mock_api_429():
            calls["count"] += 1
            if calls["count"] < 3:
                raise Exception("API error 429 Too Many Requests")
            return "eventual_success"

        # We speed up the backoff for testing by overriding defaults
        result = call_api_with_backoff(
            mock_api_429,
            max_retries=3,
            initial_backoff=0.01,
            backoff_factor=2,
            max_jitter=0
        )

        self.assertEqual(result, "eventual_success")
        self.assertEqual(calls["count"], 3)

    def test_backoff_exhausted(self):
        # Should exhaust all retries and throw RateLimitExceededException
        def mock_api_always_429():
            raise Exception("HTTP error 429")

        with self.assertRaises(RateLimitExceededException):
            call_api_with_backoff(
                mock_api_always_429,
                max_retries=2,
                initial_backoff=0.01,
                backoff_factor=1,
                max_jitter=0
            )

    def test_non_429_exception_raised_immediately(self):
        # Should immediately fail if it's not a rate limit error (e.g., 401 Unauthorized)
        calls = {"count": 0}

        def mock_api_401():
            calls["count"] += 1
            raise Exception("HTTP error 401 Unauthorized")

        with self.assertRaisesRegex(Exception, "HTTP error 401 Unauthorized"):
            call_api_with_backoff(mock_api_401)

        self.assertEqual(calls["count"], 1)

if __name__ == "__main__":
    unittest.main()
