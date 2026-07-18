import os
try:
    import tweepy
    from tweepy.asynchronous import AsyncClient
except ImportError:
    tweepy = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- X API CREDENTIALS ---
# Ensure your App has "Read and Write" permissions enabled in the X Developer Portal
API_KEY = os.environ.get("API_KEY", "YOUR_API_KEY")
API_SECRET = os.environ.get("API_SECRET", "YOUR_API_SECRET")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.environ.get("ACCESS_TOKEN_SECRET", "YOUR_ACCESS_TOKEN_SECRET")
BEARER_TOKEN = os.environ.get("BEARER_TOKEN", "YOUR_BEARER_TOKEN")


def validate_api_keys(bearer_token, api_key, api_secret, access_token, access_token_secret):
    """
    Validates that the API keys are strings, not empty, and not set to the default placeholder strings.
    Strips padding whitespace from valid keys.
    Raises TypeError or ValueError if any validation fails.
    Returns a dictionary of cleaned keys.
    """
    keys = {
        "BEARER_TOKEN": bearer_token,
        "API_KEY": api_key,
        "API_SECRET": api_secret,
        "ACCESS_TOKEN": access_token,
        "ACCESS_TOKEN_SECRET": access_token_secret
    }

    cleaned_keys = {}

    for key_name, value in keys.items():
        if value is None:
            raise ValueError(f"API key validation failed: {key_name} is empty.")
        if not isinstance(value, str):
            raise TypeError(f"API key validation failed: {key_name} must be a string.")

        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError(f"API key validation failed: {key_name} is empty.")
        if cleaned_value.startswith("YOUR_"):
            raise ValueError(
                f"API key validation failed: {key_name} is still set to the default placeholder '{value}'."
            )

        cleaned_keys[key_name] = cleaned_value

    return cleaned_keys


def get_twitter_client():
    if tweepy is None:
        raise ImportError("tweepy is not installed. Run 'pip install tweepy' to use actual API.")

    keys = validate_api_keys(BEARER_TOKEN, API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

    return AsyncClient(
        bearer_token=keys["BEARER_TOKEN"],
        consumer_key=keys["API_KEY"],
        consumer_secret=keys["API_SECRET"],
        access_token=keys["ACCESS_TOKEN"],
        access_token_secret=keys["ACCESS_TOKEN_SECRET"]
    )
