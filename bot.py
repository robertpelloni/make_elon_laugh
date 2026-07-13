import argparse
import time
import random
import logging

try:
    import tweepy
except ImportError:
    tweepy = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- X API CREDENTIALS ---
# Ensure your App has "Read and Write" permissions enabled in the X Developer Portal
API_KEY = "YOUR_API_KEY"
API_SECRET = "YOUR_API_SECRET"
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"
ACCESS_TOKEN_SECRET = "YOUR_ACCESS_TOKEN_SECRET"
BEARER_TOKEN = "YOUR_BEARER_TOKEN"

# --- THE BOT CONTEXT ---
ELON_USER_ID = "44196397"  # Elon Musk's X User ID

# Clean, tactful jokes about space, engineering, and Mars (20 jokes)
JOKES = [
    "Why did the sun go to school? To get a little brighter! ☀️",
    "How do you organize a space party? You planet! 🌍🚀",
    "What do you call a tick on the moon? A luna-tick. 🌕",
    "Why don’t aliens visit our solar system? They looked at the reviews: 1 star. ⭐",
    "I'm reading a book about anti-gravity. I just can't put it down! 📚🛸",
    "Why did the engineer cross the road? Because they looked at the data, analyzed the risk, and determined it was the most efficient route. 🛣️🤖",
    "What kind of music do planets like? Neptunes! 🎶🪐",
    "Why did the astronaut break up with his girlfriend? He needed some space. 👩‍🚀💔",
    "How do you know when the moon is going broke? It's down to its last quarter. 🌔",
    "What's an astronaut's favorite part of a computer? The space bar. ⌨️🚀",
    "Why did the Mars rover get so many dates? Because it had great pickup lines! 🔴🤖",
    "What did Mars say to Saturn? 'Give me a ring sometime!' 🪐📞",
    "How do astronauts serve dinner? On flying saucers! 🛸🍽️",
    "What did the alien say to the garden? 'Take me to your weeder.' 🌱👽",
    "Why are astronauts so good at hosting parties? They always have a blast! 🎉🚀",
    "Why did the rocket get a promotion? Because it was always going above and beyond. 🚀📈",
    "What do you get when you cross an airplane with a magician? A flying sorcerer! ✈️🧙",
    "What is an astronaut's favorite board game? Moon-opoly! 🎲🌕",
    "Why didn't the dog go to space? He was terrified of the vacuum. 🐕🌪️",
    "How does the solar system hold up its pants? With an asteroid belt! ☄️👖"
]

replied_tweets = set()

def get_twitter_client():
    if tweepy is None:
        raise ImportError("tweepy is not installed. Run 'pip install tweepy' to use actual API.")
    return tweepy.Client(
        bearer_token=BEARER_TOKEN,
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET
    )

def main():
    parser = argparse.ArgumentParser(description="Emperor Musk Joke Replier Bot")
    parser.add_argument("--dry-run", action="store_true", help="Run without actually posting to Twitter or making API calls")
    args = parser.parse_args()

    client = None
    if not args.dry_run:
        client = get_twitter_client()

    logging.info("🤖 Tactful Humor Bot initialized. Tracking targets...")
    if args.dry_run:
        logging.info("Dry run mode enabled. No actual tweets will be sent.")

    # In dry-run mode, limit the number of iterations to test it and exit,
    # otherwise it will loop forever in the background making it hard to test nicely.
    # We will simulate 3 iterations for dry-run testing.
    iterations = 3 if args.dry_run else -1
    count = 0

    while True:
        if iterations != -1 and count >= iterations:
            logging.info("Dry-run completed iterations. Exiting.")
            break
        count += 1

        try:
            new_tweets = []

            if not args.dry_run:
                # Fetch the single most recent tweet from the user
                response = client.get_users_tweets(
                    id=ELON_USER_ID,
                    max_results=5,
                    tweet_fields=["id", "text"]
                )
                if response and response.data:
                    new_tweets = response.data
            else:
                # Simulate finding a new tweet in dry-run mode
                class DummyTweet:
                    def __init__(self, id, text):
                        self.id = id
                        self.text = text
                new_tweets = [DummyTweet(random.randint(10000, 99999), f"Testing rocket {count}... 🚀")]

            replied_this_cycle = False
            for tweet in new_tweets:
                tweet_id = tweet.id

                # If it's a new tweet we haven't replied to yet
                if tweet_id not in replied_tweets:
                    logging.info(f"🎯 New tweet found: '{tweet.text[:50]}...'")

                    # Pick a random clean joke
                    joke = random.choice(JOKES)

                    if not args.dry_run:
                        # Send the reply
                        client.create_tweet(
                            text=joke,
                            in_reply_to_tweet_id=tweet_id
                        )
                        logging.info(f"✅ Replied successfully to Tweet ID {tweet_id}")
                    else:
                        logging.info(f"[DRY-RUN] Would reply to Tweet ID {tweet_id} with: {joke}")

                    replied_tweets.add(tweet_id)
                    replied_this_cycle = True
                    break # Only reply to one tweet per cycle, then wait 4-6 hours

            if replied_this_cycle:
                # Wait 4 to 6 hours (14400 to 21600 seconds) + a small random delay (0-1800 seconds)
                base_wait = random.randint(4 * 3600, 6 * 3600)
                random_delay = random.randint(0, 1800)
                wait_seconds = base_wait + random_delay

                if args.dry_run:
                    wait_seconds = 2 # Speed up wait for dry run
                    logging.info(f"[DRY-RUN] Simulating wait of 4-6 hours (actually waiting {wait_seconds} seconds).")
                else:
                    logging.info(f"Waiting for {wait_seconds} seconds before checking again...")
                time.sleep(wait_seconds)
            else:
                logging.info("No new recent tweets found. Checking again soon.")
                wait_seconds = 60
                if args.dry_run:
                    wait_seconds = 2
                time.sleep(wait_seconds)

        except Exception as e:
            logging.error(f"❌ Error encountered: {e}")
            wait_seconds = 60
            if args.dry_run:
                wait_seconds = 2
            time.sleep(wait_seconds)

if __name__ == "__main__":
    main()
