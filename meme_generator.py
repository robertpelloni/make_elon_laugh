"""
Meme and Infographic Visual Card Generator (meme_generator.py)

Generates clean, dark-themed visual cards containing jokes or astrophysics facts
using Pillow. These images can be attached to posts on Twitter/X or previewed
directly on the dashboard.
"""

import io
import logging
import textwrap
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


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


def recommend_infographic_layout(panels=None, content_text=None):
    """
    Analyzes panel count, average text length, character density, and complexity
    to recommend the optimal visual composite layout ('grid' vs 'side-by-side').
    Returns dict with:
      - 'layout': 'grid' | 'side-by-side'
      - 'rationale': String explanation for operator review
      - 'panel_count': Number of identified panels
      - 'avg_char_length': Average characters per panel
    """
    # Count panels or estimate from text
    normalized_count = 0
    total_chars = 0

    if panels and isinstance(panels, list) and len(panels) > 0:
        normalized_count = len(panels)
        for p in panels:
            if isinstance(p, dict):
                total_chars += len(str(p.get("text", "")))
            elif isinstance(p, str):
                total_chars += len(p)
    elif content_text and isinstance(content_text, str) and content_text.strip():
        # Heuristic: split by numbered points or line breaks
        lines = [ln.strip() for ln in content_text.strip().split("\n") if ln.strip()]
        normalized_count = max(len(lines), 1)
        total_chars = len(content_text)
    else:
        normalized_count = 4
        total_chars = 320

    avg_chars = total_chars // max(normalized_count, 1)

    # Decision logic:
    # If 2 panels or high text density (>120 chars/panel), side-by-side offers better vertical reading room.
    # If 3 or 4 panels with concise modular text (<=120 chars/panel), 2x2 quadrant grid offers optimal symmetry.
    if normalized_count == 2 or (avg_chars > 120 and normalized_count <= 2):
        layout = "side-by-side"
        rationale = (
            f"Side-by-side horizontal layout selected: {normalized_count} panel(s) with high character "
            f"density (~{avg_chars} chars/panel) benefit from wider text columns and extended vertical space."
        )
    elif normalized_count >= 3:
        layout = "grid"
        rationale = (
            f"2x2 quadrant grid layout selected: {normalized_count} modular panels with concise character "
            f"density (~{avg_chars} chars/panel) provide balanced multi-concept visual symmetry."
        )
    else:
        layout = "grid"
        rationale = (
            f"Standard 2x2 quadrant grid selected by default: {normalized_count} panel(s) (~{avg_chars} chars/panel)."
        )

    return {
        "layout": layout,
        "rationale": rationale,
        "panel_count": normalized_count,
        "avg_char_length": avg_chars
    }


def create_composite_infographic(panels=None, title="Cosmic Infographic Dispatch",
                                 theme="dark", layout="grid", subtitle=None,
                                 rephrase_panels=False, persona="tactful_engineer",
                                 tone_style="witty"):
    """
    Renders multi-image composite layout for visual infographics and educational briefs.
    Supported layouts:
      - 'side-by-side': 2 panels positioned horizontally (800x420)
      - 'grid': 4 quadrant panels arranged in a 2x2 grid (800x620)
      - 'auto': Automatically select layout using recommend_infographic_layout()
    Each item in `panels` can be a string or a dict with {'title': ..., 'text': ...}.
    If `rephrase_panels` is True, panels will be passed through `joke_generator.rephrase_infographic_panels()`.
    Returns the raw PNG image bytes.
    """
    theme_key = (theme or "dark").lower().strip()
    palette = THEME_PALETTES.get(theme_key, THEME_PALETTES["dark"])
    layout_mode = (layout or "grid").lower().strip()

    if layout_mode == "auto":
        recommendation = recommend_infographic_layout(panels)
        layout_mode = recommendation["layout"]

    if layout_mode not in ("side-by-side", "grid"):
        layout_mode = "grid"

    default_panels = [
        {
            "title": "Orbital Dynamics",
            "text": "Low Earth orbit satellites experience slight atmospheric drag and require orbital boosts."
        },
        {
            "title": "Relativistic Time",
            "text": "GPS clocks run faster by ~38 microseconds daily due to combined general and special relativity."
        },
        {
            "title": "Vacuum Propulsion",
            "text": "Rocket engines achieve higher specific impulse in vacuum than inside Earth's thick atmosphere."
        },
        {
            "title": "Cosmic Ray Shielding",
            "text": "Interplanetary missions require hydrogen-rich water or polyethylene shields for cosmic rays."
        }
    ]

    # Normalize panel items
    normalized_panels = []
    if panels and isinstance(panels, list) and len(panels) > 0:
        for p in panels:
            if isinstance(p, dict):
                p_title = str(p.get("title") or "Observation").strip()
                p_text = str(p.get("text") or "").strip()
                normalized_panels.append({"title": p_title, "text": p_text})
            elif isinstance(p, str) and p.strip():
                normalized_panels.append({"title": "Observation", "text": p.strip()})

    if not normalized_panels:
        normalized_panels = default_panels

    if rephrase_panels:
        try:
            import joke_generator
            normalized_panels = joke_generator.rephrase_infographic_panels(
                normalized_panels,
                persona=persona,
                tone_style=tone_style
            )
        except Exception as e:
            logger.warning(f"Failed to rephrase infographic panels: {e}")

    # Calculate dimensions
    if layout_mode == "side-by-side":
        canvas_width, canvas_height = 800, 420
        target_count = 2
    else:  # grid
        canvas_width, canvas_height = 800, 620
        target_count = 4

    # Pad if fewer panels provided
    while len(normalized_panels) < target_count:
        idx = len(normalized_panels) % len(default_panels)
        normalized_panels.append(default_panels[idx])

    img = Image.new('RGB', (canvas_width, canvas_height), color=palette["bg"])
    draw = ImageDraw.Draw(img)
    font_default = ImageFont.load_default()

    # Outer master border
    draw.rounded_rectangle(
        [(15, 15), (canvas_width - 15, canvas_height - 15)],
        radius=16,
        outline=palette["container_border"],
        width=2,
        fill=palette["container_fill"]
    )

    # Master top accent banner
    draw.rounded_rectangle(
        [(15, 15), (canvas_width - 15, 25)],
        radius=4,
        fill=palette["accent"]
    )

    # Master title header
    draw.text((35, 38), f"🌌 {title}", fill=palette["accent"], font=font_default)
    draw.line([(35, 62), (canvas_width - 35, 62)], fill=palette["divider"], width=1)

    # Compute panel positions
    header_offset = 75
    footer_height = 45
    usable_width = canvas_width - 70
    usable_height = canvas_height - header_offset - footer_height

    if layout_mode == "side-by-side":
        gap = 16
        panel_w = (usable_width - gap) // 2
        panel_h = usable_height
        panel_rects = [
            [(35, header_offset), (35 + panel_w, header_offset + panel_h)],
            [(35 + panel_w + gap, header_offset), (35 + 2 * panel_w + gap, header_offset + panel_h)]
        ]
    else:  # grid 2x2
        gap = 14
        panel_w = (usable_width - gap) // 2
        panel_h = (usable_height - gap) // 2
        panel_rects = [
            [(35, header_offset), (35 + panel_w, header_offset + panel_h)],
            [(35 + panel_w + gap, header_offset), (35 + 2 * panel_w + gap, header_offset + panel_h)],
            [(35, header_offset + panel_h + gap), (35 + panel_w, header_offset + 2 * panel_h + gap)],
            [(35 + panel_w + gap, header_offset + panel_h + gap),
             (35 + 2 * panel_w + gap, header_offset + 2 * panel_h + gap)]
        ]

    # Render each panel
    for i, rect in enumerate(panel_rects[:target_count]):
        p_data = normalized_panels[i]
        x0, y0 = rect[0]
        x1, y1 = rect[1]

        # Individual panel card background
        draw.rounded_rectangle(
            [rect[0], rect[1]],
            radius=10,
            outline=palette["divider"],
            width=1,
            fill=palette["bg"]
        )

        # Panel accent top indicator
        draw.line([(x0 + 10, y0 + 26), (x1 - 10, y0 + 26)], fill=palette["divider"], width=1)
        draw.text((x0 + 12, y0 + 10), f"⚡ {p_data['title']}", fill=palette["accent"], font=font_default)

        # Wrap text inside panel
        char_wrap = 38 if layout_mode == "side-by-side" else 36
        wrapped = textwrap.wrap(p_data["text"], width=char_wrap)
        max_lines = 10 if layout_mode == "side-by-side" else 6
        text_y = y0 + 36
        for line in wrapped[:max_lines]:
            draw.text((x0 + 14, text_y), line, fill=palette["text"], font=font_default)
            text_y += 20

    # Master Footer
    footer_text = subtitle or f"⚡ Tactful Autonomous Composite Infographics [{layout_mode.upper()} LAYOUT]"
    draw.text((35, canvas_height - 35), footer_text, fill=palette["footer"], font=font_default)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_composite_infographic_b64(panels=None, title="Cosmic Infographic Dispatch",
                                       theme="dark", layout="grid", subtitle=None,
                                       rephrase_panels=False, persona="tactful_engineer",
                                       tone_style="witty"):
    """
    Helper function generating base64 encoded composite infographic for web preview.
    """
    import base64
    raw_bytes = create_composite_infographic(
        panels=panels,
        title=title,
        theme=theme,
        layout=layout,
        subtitle=subtitle,
        rephrase_panels=rephrase_panels,
        persona=persona,
        tone_style=tone_style
    )
    return base64.b64encode(raw_bytes).decode('utf-8')
