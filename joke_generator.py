import random
import os
import logging

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

# Clean, tactful jokes about space, engineering, and Mars (20 jokes)
STATIC_JOKES = [
    "Why did the sun go to school? To get a little brighter! ☀️",
    "How do you organize a space party? You planet! 🌍🚀",
    "What do you call a tick on the moon? A luna-tick. 🌕",
    "Why don’t aliens visit our solar system? They looked at the reviews: 1 star. ⭐",
    "I'm reading a book about anti-gravity. I just can't put it down! 📚🛸",
    "Why did the engineer cross the road? Because they looked at the data, analyzed the risk, "
    "and determined it was the most efficient route. 🛣️🤖",
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


def fetch_llm_joke(context_tweet_text):
    """
    Fetches a dynamic joke from an LLM given the context tweet text.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    if not OPENAI_AVAILABLE:
        logger.warning("OPENAI_API_KEY is set, but openai package is not installed.")
        return None

    try:
        client = openai.OpenAI(api_key=api_key)

        prompt = (
            "You are a helpful, tactful, and clean bot that responds to Elon Musk's tweets "
            "with relevant, short space or engineering-themed jokes.\n"
            f"Context tweet: \"{context_tweet_text}\"\n"
            "First, analyze the sentiment and tone of the context tweet. If the tweet is highly serious, "
            "tragic, or explicitly discusses a sensitive negative event, respond with ONLY the word 'SKIP'.\n"
            "Otherwise, generate one short, very funny joke in response to the context. "
            "Keep it under 200 characters and include exactly one relevant emoji."
        )

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a witty, clean comedian specializing in space and engineering."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=60,
            temperature=0.8
        )

        joke = response.choices[0].message.content.strip()
        if joke.upper() == "SKIP":
            logger.info("LLM determined the context tweet is too serious for a joke.")
            return None
        if joke:
            return joke

    except Exception as e:
        logger.error(f"Error fetching joke from LLM: {e}")

    return None


def generate_joke(context_tweet_text=None):
    """
    Generates a space or engineering-themed joke.
    Calls an LLM API based on the `context_tweet_text` if configured.
    Falls back to a random joke from the static curated list.
    """
    if context_tweet_text:
        dynamic_joke = fetch_llm_joke(context_tweet_text)
        if dynamic_joke:
            return dynamic_joke

    # Fallback to static list
    return random.choice(STATIC_JOKES)
