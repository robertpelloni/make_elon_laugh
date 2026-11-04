import logging

logger = logging.getLogger(__name__)


class AnalyticsTracker:
    """Tracks basic metrics for the bot session."""

    def __init__(self):
        self.tweets_found = 0
        self.tweets_replied = 0
        self.malformed_tweets_skipped = 0
        self.validation_errors = 0

    def record_found(self):
        self.tweets_found += 1

    def record_reply(self):
        self.tweets_replied += 1

    def record_malformed(self):
        self.malformed_tweets_skipped += 1

    def record_validation_error(self):
        self.validation_errors += 1

    def print_summary(self):
        """Outputs a summary of the session to the logs."""
        logger.info("📊 --- Session Analytics Summary ---")
        logger.info(f"Total Tweets Processed:   {self.tweets_found}")
        logger.info(f"Successful Replies:       {self.tweets_replied}")
        logger.info(f"Malformed Skips:          {self.malformed_tweets_skipped}")
        logger.info(f"Validation Errors:        {self.validation_errors}")
        logger.info("-----------------------------------")
