import random
import os
import logging

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

# Clean, tactful jokes about space, engineering, and Mars
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

# Dynamic tone variation styles with prompt guidelines and offline heuristics
TONE_STYLES = {
    "witty": {
        "display_name": "Witty & Sharp",
        "description": "Clever, punchy humor with high comedic timing.",
        "instruction": "Rephrase to make it punchy, witty, and clever while preserving core space/physics meaning.",
        "prefix": "Telemetry update: ",
        "suffix": " 🚀✨"
    },
    "concise": {
        "display_name": "Concise & Direct",
        "description": "Ultra-short, crisp, direct phrasing stripped of filler words.",
        "instruction": "Make the content extremely concise, punchy, and direct in under 120 characters.",
        "prefix": "",
        "suffix": " 🛰️"
    },
    "enthusiastic": {
        "display_name": "Enthusiastic & Hype",
        "description": "Upbeat rocketry excitement with vibrant energy and cosmic wonder.",
        "instruction": "Rephrase with infectious enthusiasm, rocketry excitement, and energetic flair.",
        "prefix": "Incredible milestone: ",
        "suffix": " 🔥🚀"
    },
    "academic": {
        "display_name": "Academic & Scholarly",
        "description": "Formal, rigorous, scientifically nuanced astrophysical tone.",
        "instruction": "Rephrase using formal, scholarly astrophysical prose and precise terminology.",
        "prefix": "Empirical observation: ",
        "suffix": " 🌌🔭"
    }
}

# Compatibility lists
STATIC_JOKES = PERSONAS["tactful_engineer"]["jokes"]
STATIC_FACTS = PERSONAS["tactful_engineer"]["facts"]


def fetch_llm_content(context_tweet_text, content_type="joke"):
    """
    Fetches dynamic content (joke or fact) from an LLM given the context tweet text.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    if not OPENAI_AVAILABLE:
        logger.warning("OPENAI_API_KEY is set, but openai package is not installed.")
        return None

    try:
        client = openai.OpenAI(api_key=api_key)

        system_msg = (
            "You are a witty, clean comedian specializing in space and engineering."
            if content_type == "joke"
            else "You are a brilliant astrophysicist who loves sharing short, interesting facts about space."
        )

        prompt_task = (
            "Generate one short, very funny joke in response to the context."
            if content_type == "joke"
            else "Generate one short, fascinating astrophysics fact related to the context."
        )

        prompt = (
            "You are a helpful, tactful, and clean bot that responds to tweets "
            "with relevant, short space or engineering-themed content.\n"
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


def generate_content(context_tweet_text=None):
    """
    Generates a space or engineering-themed joke or fact.
    Calls an LLM API based on the `context_tweet_text` if configured.
    Falls back to a random joke or fact from the static curated lists.
    """
    content_type = random.choice(["joke", "fact"])

    if context_tweet_text:
        dynamic_content = fetch_llm_content(context_tweet_text, content_type)
        if dynamic_content:
            return dynamic_content

    # Fallback to persona-specific static list
    collection = pdata["jokes"] if content_type == "joke" else pdata["facts"]
    return random.choice(collection)


def rephrase_content(content, persona="tactful_engineer", tone_style="witty"):
    """
    Rephrases a given joke, tweet, or fact according to a persona and tone style.
    Leverages OpenAI GPT completions if available; otherwise falls back to deterministic
    stylistic transformations.
    """
    clean_text = (content or "").strip()
    if not clean_text:
        return ""

    tone_info = TONE_STYLES.get(tone_style, TONE_STYLES["witty"])
    pdata = get_persona(persona)

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key and OPENAI_AVAILABLE:
        try:
            client = openai.OpenAI(api_key=api_key)
            system_msg = f"{pdata['joke_system']} You excel at tone-shifting and editing space/astrophysics content."
            prompt = (
                f"Original text: \"{clean_text}\"\n"
                f"Target tone: {tone_info['display_name']} ({tone_info['instruction']})\n"
                f"Persona: {pdata['display_name']}\n"
                "Rephrase the original text while preserving its factual accuracy and humor/spirit. "
                "Output ONLY the rephrased text. Keep it under 260 characters and retain an emoji."
            )
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=80,
                temperature=0.7
            )
            rephrased = response.choices[0].message.content.strip().strip('"')
            if rephrased and len(rephrased) <= 280:
                return rephrased
        except Exception as e:
            logger.warning(f"OpenAI rephrase failed, falling back to heuristics: {e}")

    # Offline heuristic fallback
    # Apply tone-specific stylistic prefix/suffix and minor transformation
    base = clean_text.rstrip(".! ")
    if tone_style == "concise":
        # Remove common filler words and shorten
        words = [w for w in base.split() if w.lower() not in {"because", "that", "really", "very", "actually"}]
        shortened = " ".join(words[:18])
        return f"{shortened}{tone_info['suffix']}"

    rephrased_candidate = f"{tone_info['prefix']}{base}{tone_info['suffix']}"
    if len(rephrased_candidate) > 280:
        return rephrased_candidate[:277] + "..."
    return rephrased_candidate


def generate_meme_card_b64(text, title="Emperor Musk Bot", theme="dark"):
    """
    Renders text to a visual meme card and returns a base64-encoded PNG string.
    """
    raw_bytes = meme_generator.create_meme_card(text, title=title, theme=theme)
    return base64.b64encode(raw_bytes).decode('utf-8')


# Aliasing for backward compatibility
generate_joke = generate_content
