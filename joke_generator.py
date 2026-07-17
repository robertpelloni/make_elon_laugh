import random

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


def generate_joke(context_tweet_text=None):
    """
    Generates a space or engineering-themed joke.
    Currently returns a random joke from the static curated list.
    Designed to be extended in the future to call an LLM API
    based on the `context_tweet_text`.
    """

    # In the future:
    # if LLM_API_KEY is configured:
    #     return fetch_llm_joke(context_tweet_text)

    # Fallback to static list
    return random.choice(STATIC_JOKES)
