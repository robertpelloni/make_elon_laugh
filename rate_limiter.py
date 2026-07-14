import time
import random
import logging

try:
    import tweepy
except ImportError:
    tweepy = None

logger = logging.getLogger(__name__)


class RateLimitExceededException(Exception):
    """Raised when maximum retries for rate limits are exhausted."""
    pass


def call_api_with_backoff(api_func, max_retries=5, initial_backoff=60, backoff_factor=2.0, max_jitter=30):
    """
    Executes a Twitter API function with exponential backoff and jitter.

    Args:
        api_func (callable): The API function to execute.
        max_retries (int): Maximum number of retry attempts for 429 errors.
        initial_backoff (int): Initial wait time in seconds.
        backoff_factor (float): Multiplier for the backoff time on subsequent retries.
        max_jitter (int): Maximum random seconds to add to the backoff to prevent thundering herd.

    Returns:
        The result of the api_func call.

    Raises:
        RateLimitExceededException: If max_retries is reached.
        Exception: Any other exception raised by the API function that is not a rate limit.
    """
    retries = 0
    current_backoff = initial_backoff

    while retries <= max_retries:
        try:
            return api_func()
        except Exception as e:
            # Check if this is a Tweepy exception related to Rate Limiting (HTTP 429) or Network Latency
            should_retry = False
            retry_reason = "Unknown Error"

            if tweepy and isinstance(e, tweepy.TooManyRequests):
                should_retry = True
                retry_reason = "HTTP 429 Too Many Requests"
            elif hasattr(e, 'response') and e.response is not None and e.response.status_code == 429:
                should_retry = True
                retry_reason = "HTTP 429 Too Many Requests"
            elif "429" in str(e):  # Fallback check for mocked tests or generic error messages
                should_retry = True
                retry_reason = "HTTP 429 Too Many Requests"
            elif isinstance(e, (TimeoutError, ConnectionError)):
                should_retry = True
                retry_reason = f"Network Latency/Connection Error ({type(e).__name__})"

            if should_retry:
                if retries == max_retries:
                    logger.error(f"Retries exhausted after {max_retries} attempts.")
                    raise RateLimitExceededException(
                        f"Failed after {max_retries} retries. Last error: {retry_reason}"
                    ) from e

                # Calculate jitter: random value between 0 and max_jitter
                jitter = random.uniform(0, max_jitter)
                sleep_time = current_backoff + jitter

                logger.warning(
                    f"API call failed: {retry_reason}. Retrying in {sleep_time:.2f} seconds "
                    f"(Attempt {retries + 1}/{max_retries})..."
                )
                time.sleep(sleep_time)

                # Exponential backoff for next retry
                current_backoff *= backoff_factor
                retries += 1
            else:
                # If it's a different error, raise it immediately
                raise
