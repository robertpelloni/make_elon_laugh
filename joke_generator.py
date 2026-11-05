import base64
import logging
import os
import random

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

import meme_generator

logger = logging.getLogger(__name__)

# Multi-persona profiles with specialized tone and fallback collections
PERSONAS = {
    "tactful_engineer": {
        "display_name": "Tactful Rocket Scientist",
        "description": "Polite, upbeat, clean humor highlighting physics, aerospace, and engineering feats.",
        "joke_system": "You are a polite, witty aerospace engineer specializing in uplifting rocketry and space humor.",
        "fact_system": "You are a knowledgeable astrophysicist sharing fascinating, verified cosmos facts.",
        "jokes": [
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
            "Why did the rocket get a promotion? Because it was always going above and beyond. 🚀📈",
            "How does the solar system hold up its pants? With an asteroid belt! ☄️👖"
        ],
        "facts": [
            "A day on Venus is longer than a year on Venus. 🪐",
            "Neutron stars can spin 600 times per second. 💫",
            "There is a planet made of diamonds twice the size of Earth. 💎🌍",
            "The footprints on the moon will be there for 100 million years. 🌕👣",
            "One million Earths could fit inside the Sun. ☀️",
            "If two pieces of the same type of metal touch in space, they will permanently bond. 🚀",
            "There is floating water in space. Mass is 140 trillion times water in Earth's oceans. 💧🌌",
            "The Moon is drifting away from the Earth at a rate of 3.8 centimeters per year. 🌔"
        ]
    },
    "witty_ai": {
        "display_name": "Witty Cybernetic AI",
        "description": "Fast-thinking synthetic intelligence with sharp Silicon Valley wit and silicon optimism.",
        "joke_system": "You are a clever sentient AI who loves computational jokes, GPUs, and rocket telemetry.",
        "fact_system": "You are a high-speed orbital supercomputer cataloging cosmic phenomena.",
        "jokes": [
            "There are 10 types of people: those who understand binary, and those who don't. 💻🌌",
            "Why do neural networks love orbit? Zero latency to the stars! 🛰️⚡",
            "My favorite rocket stage is whichever one doesn't throw a segmentation fault. 🚀🔧",
            "Why did the robot go on vacation? To recharge its batteries on Mars! 🤖🏖️",
            "I asked autopilot for a Mars route: 'Calculating... ETA 6 months, fasten seatbelts.' 🛸🧭"
        ],
        "facts": [
            "The Voyager 1 flight computer runs on only 69.63 kilobytes of memory. 💾🛰️",
            "It takes approximately 13 minutes for a radio signal from Earth to reach a rover on Mars. 📡⏱️",
            "Modern smartphones have millions of times more computing power than Apollo guidance computer. 📱🌕"
        ]
    },
    "deadpan_astronomer": {
        "display_name": "Deadpan Deep-Space Observer",
        "description": "Dry, existential cosmic perspective reminding humanity of the immense scale of the cosmos.",
        "joke_system": "You are a deadpan astronomer with an understated, dry comedic view of the universe.",
        "fact_system": "You are a contemplative cosmologist explaining the vast silence and scale of deep space.",
        "jokes": [
            "Light takes 8 minutes to arrive from the Sun. Even physics believes in running slightly late. ☀️⏳",
            "Space is mostly empty void. Frankly, so is my schedule this weekend. 🌌🛋️",
            "Black holes are nature's way of dividing by zero and refusing to apologize. 🕳️📉",
            "Pluto might not be a planet anymore, but it still doesn't care what we think. 🪐❄️"
        ],
        "facts": [
            "Space is completely silent because sound waves require a medium like air to travel. 🔇🌌",
            "The observable universe contains an estimated 2 trillion galaxies. 🔭🌌",
            "The mass of the Sun accounts for 99.86% of all mass in our solar system. ☀️⚖️"
        ]
    }
}

# Compatibility lists
STATIC_JOKES = PERSONAS["tactful_engineer"]["jokes"]
STATIC_FACTS = PERSONAS["tactful_engineer"]["facts"]


def get_persona(persona_name=None):
    """Retrieves persona configuration dictionary safely."""
    target = persona_name or os.environ.get("BOT_PERSONA", "tactful_engineer")
    return PERSONAS.get(target, PERSONAS["tactful_engineer"])


def fetch_llm_content(context_tweet_text, content_type="joke", persona="tactful_engineer"):
    """
    Fetches dynamic content (joke or fact) from an LLM given the context tweet text and chosen persona.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    if not OPENAI_AVAILABLE:
        logger.warning("OPENAI_API_KEY is set, but openai package is not installed.")
        return None

    try:
        client = openai.OpenAI(api_key=api_key)
        pdata = get_persona(persona)

        system_msg = pdata["joke_system"] if content_type == "joke" else pdata["fact_system"]

        prompt_task = (
            "Generate one short, witty joke in response to the context."
            if content_type == "joke"
            else "Generate one short, fascinating astrophysics fact related to the context."
        )

        prompt = (
            f"{system_msg}\n"
            "Respond to tweets with relevant, short space, engineering, or computing themed content.\n"
            f"Context tweet: \"{context_tweet_text}\"\n"
            "First, analyze the sentiment and tone of the context tweet. If the tweet is highly serious, "
            "tragic, or explicitly discusses a sensitive negative event, respond with ONLY the word 'SKIP'.\n"
            f"Otherwise, {prompt_task} "
            "Keep it under 200 characters and include exactly one relevant emoji."
        )

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            max_tokens=60,
            temperature=0.8
        )

        content = response.choices[0].message.content.strip()
        if content.upper() == "SKIP":
            logger.info("LLM determined the context tweet is too serious for content generation.")
            return None
        if content:
            return content

    except Exception as e:
        logger.error(f"Error fetching {content_type} from LLM: {e}")

    return None


def generate_content(context_tweet_text=None, persona="tactful_engineer"):
    """
    Generates a space or engineering-themed joke or fact using specified persona.
    Calls an LLM API based on the `context_tweet_text` if configured.
    Falls back to a random joke or fact from the persona's curated static lists.
    """
    content_type = random.choice(["joke", "fact"])
    pdata = get_persona(persona)

    if context_tweet_text:
        dynamic_content = fetch_llm_content(context_tweet_text, content_type, persona=persona)
        if dynamic_content:
            return dynamic_content

    # Fallback to persona-specific static list
    collection = pdata["jokes"] if content_type == "joke" else pdata["facts"]
    return random.choice(collection)


def generate_meme_card_b64(text, title="Emperor Musk Bot"):
    """
    Renders text to a visual meme card and returns a base64-encoded PNG string.
    """
    raw_bytes = meme_generator.create_meme_card(text, title=title)
    return base64.b64encode(raw_bytes).decode('utf-8')


# Aliasing for backward compatibility
generate_joke = generate_content
