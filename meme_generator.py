"""
Meme and Infographic Visual Card Generator (meme_generator.py)

Generates clean, dark-themed visual cards containing jokes or astrophysics facts
using Pillow. These images can be attached to posts on Twitter/X or previewed
directly on the dashboard.
"""

import io
import textwrap
from PIL import Image, ImageDraw, ImageFont


def create_meme_card(text, title="Emperor Musk Bot"):
    """
    Renders text onto a 600x340 space-themed dark card with accent borders.
    Returns the raw PNG image bytes.
    """
    if not isinstance(text, str) or not text.strip():
        text = "The universe is full of mysteries and wonder. 🌌"

    card_width, card_height = 600, 340
    # Create dark slate background
    img = Image.new('RGB', (card_width, card_height), color=(15, 20, 28))
    draw = ImageDraw.Draw(img)

    # Gradient border / card container
    draw.rounded_rectangle(
        [(15, 15), (card_width - 15, card_height - 15)],
        radius=16,
        outline=(46, 62, 86),
        width=2,
        fill=(26, 35, 50)
    )

    # Accent top bar
    draw.rounded_rectangle(
        [(15, 15), (card_width - 15, 25)],
        radius=4,
        fill=(29, 155, 240)
    )

    # Header title
    font_default = ImageFont.load_default()
    draw.text((35, 45), f"🛸 {title}", fill=(29, 155, 240), font=font_default)

    # Subtext / Divider
    draw.line([(35, 75), (card_width - 35, 75)], fill=(46, 62, 86), width=1)

    # Body text wrapping
    wrapped_lines = textwrap.wrap(text, width=42)
    y_text = 110
    line_height = 22

    for line in wrapped_lines[:6]:
        draw.text((45, y_text), line, fill=(247, 249, 249), font=font_default)
        y_text += line_height

    # Footer note
    draw.text(
        (35, card_height - 45),
        "⚡ Tactful Autonomous Space & Engineering Humor Agent",
        fill=(139, 152, 165),
        font=font_default
    )

    # Export to bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()
