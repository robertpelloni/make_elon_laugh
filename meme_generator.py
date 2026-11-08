"""
Meme and Infographic Visual Card Generator (meme_generator.py)

Generates clean, dark-themed visual cards containing jokes or astrophysics facts
using Pillow. These images can be attached to posts on Twitter/X or previewed
directly on the dashboard.
"""

import io
import textwrap
from PIL import Image, ImageDraw, ImageFont


THEME_PALETTES = {
    "dark": {
        "bg": (15, 20, 28),
        "container_fill": (26, 35, 50),
        "container_border": (46, 62, 86),
        "accent": (29, 155, 240),       # Electric space blue
        "divider": (46, 62, 86),
        "text": (247, 249, 249),
        "footer": (139, 152, 165)
    },
    "cyberpunk": {
        "bg": (10, 10, 16),
        "container_fill": (20, 16, 32),
        "container_border": (168, 85, 247),
        "accent": (236, 72, 153),       # Neon pink / magenta
        "divider": (139, 92, 246),
        "text": (250, 245, 255),
        "footer": (192, 132, 252)
    },
    "solar": {
        "bg": (20, 15, 10),
        "container_fill": (38, 26, 18),
        "container_border": (217, 119, 6),
        "accent": (245, 158, 11),       # Solar flare amber
        "divider": (180, 83, 9),
        "text": (254, 243, 199),
        "footer": (217, 119, 6)
    },
    "clean": {
        "bg": (241, 245, 249),
        "container_fill": (255, 255, 255),
        "container_border": (203, 213, 225),
        "accent": (14, 165, 233),       # Sky blue
        "divider": (226, 232, 240),
        "text": (15, 23, 42),
        "footer": (100, 116, 139)
    }
}


def create_meme_card(text, title="Emperor Musk Bot", theme="dark", subtitle=None):
    """
    Renders text onto a 600x340 space-themed card with customizable theme styling.
    Supported themes: 'dark', 'cyberpunk', 'solar', 'clean'.
    Returns the raw PNG image bytes.
    """
    if not isinstance(text, str) or not text.strip():
        text = "The universe is full of mysteries and wonder. 🌌"

    theme_key = (theme or "dark").lower().strip()
    palette = THEME_PALETTES.get(theme_key, THEME_PALETTES["dark"])

    card_width, card_height = 600, 340
    img = Image.new('RGB', (card_width, card_height), color=palette["bg"])
    draw = ImageDraw.Draw(img)

    # Card container
    draw.rounded_rectangle(
        [(15, 15), (card_width - 15, card_height - 15)],
        radius=16,
        outline=palette["container_border"],
        width=2,
        fill=palette["container_fill"]
    )

    # Accent top bar
    draw.rounded_rectangle(
        [(15, 15), (card_width - 15, 25)],
        radius=4,
        fill=palette["accent"]
    )

    # Header title
    font_default = ImageFont.load_default()
    draw.text((35, 45), f"🛸 {title}", fill=palette["accent"], font=font_default)

    # Subtext / Divider
    draw.line([(35, 75), (card_width - 35, 75)], fill=palette["divider"], width=1)

    # Body text wrapping
    wrapped_lines = textwrap.wrap(text, width=42)
    y_text = 110
    line_height = 22

    for line in wrapped_lines[:6]:
        draw.text((45, y_text), line, fill=palette["text"], font=font_default)
        y_text += line_height

    # Footer note
    footer_text = subtitle or "⚡ Tactful Autonomous Space & Engineering Humor Agent"
    draw.text(
        (35, card_height - 45),
        footer_text,
        fill=palette["footer"],
        font=font_default
    )

    # Export to bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
