import unittest
from bot import validate_api_keys, validate_tweet_content

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

if __name__ == "__main__":
    unittest.main()
