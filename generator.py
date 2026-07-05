"""Image generation logic backed by fal.ai.

This module is independent from the UI: it can be used from Streamlit, a script
or tests. The API key is read from the FAL_KEY environment variable (loaded from
a .env file).
"""

import fal_client
import logfire
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "fal-ai/flux/schnell"
KONTEXT_MODEL = "fal-ai/flux-pro/kontext"
# Open-weights Kontext: weaker at structural edits than pro, but fal exposes
# enable_safety_checker=False on it, so it can NEVER censor. Used as the last
# image-producing fallback when pro's server-side moderation blocks an edit.
KONTEXT_DEV_MODEL = "fal-ai/flux-kontext/dev"
# img2img at 40 steps: used for re-anchors, regenerating fine detail while
# preserving the creature's composition and identity (unlike a text-only
# regeneration, which invents a new creature every time).
REFRESH_MODEL = "fal-ai/flux/dev/image-to-image"

# All generation goes through PNG: each edit cycle re-saves the image, and
# JPEG recompression artifacts compound visibly after a few passes.
OUTPUT_FORMAT = "png"

# Fixed house style: every generation is forced into a medical-scan aesthetic
# regardless of what the user asks for. The user's input only supplies the
# subject; it is dropped into {subject} below. Two palettes ("themes"):
# - dark:  glowing white-blue anatomy on black radiographic film
# - light: dense black/charcoal anatomy on pale film, like a printed
#          coronary angiography sheet on a bright light box
#
# Written following FLUX prompting practice: natural language describing one
# coherent photographic scene (not keyword lists), light described as physical
# behaviour, explicit full-body framing, and only positive statements (FLUX
# has no negative prompt). Photographic-film vocabulary keeps the output
# looking like a real radiograph instead of a 3D render.
_TEMPLATE_COMMON_HEAD = (
    "{subject} "
    "This creature is shown as an authentic full-body medical radiograph: "
    "the entire creature is visible in the frame from the top of its head to "
    "the end of its limbs, centered, with empty space around the whole "
    "silhouette. "
)
_TEMPLATE_COMMON_TAIL = (
    "The mood is clinical and documentary, like a leaked hospital scan of "
    "something that should not exist."
)

STYLE_TEMPLATES = {
    "dark": (
        _TEMPLATE_COMMON_HEAD +
        "It looks like a real X-ray film exposure photographed on a clinical "
        "light box: bones and internal anatomy glow soft white-blue through "
        "semi-transparent tissue, blood vessels branch through the body like "
        "a coronary angiography, and the exposure blooms and scatters softly "
        "where the tissue is dense, with fine analog film grain across the "
        "whole image. "
        "The background is deep black radiographic film. Thin technical "
        "annotations, measurement markers, small data labels and faint "
        "crosshairs from a radiology workstation frame the figure. "
        "The palette is cold monochrome grayscale with one faint cyan or "
        "blood-red accent glowing inside the body. "
        + _TEMPLATE_COMMON_TAIL
    ),
    "light": (
        _TEMPLATE_COMMON_HEAD +
        "It looks like a real radiograph print viewed on a bright light box: "
        "the anatomy renders in dense black and soft charcoal grays against "
        "a pale gray-white film background, bones dark and sharply defined, "
        "blood vessels branching through the body as fine black threads like "
        "a printed coronary angiography, the exposure blooming softly where "
        "tissue is dense, with fine analog film grain and a subtle paper "
        "texture across the whole sheet. "
        "Thin dark technical annotations, measurement markers, small data "
        "labels and faint crosshairs from a radiology archive sheet frame "
        "the figure. "
        "The palette is cold monochrome grayscale with one faint blood-red "
        "or cyan accent inside the body. "
        + _TEMPLATE_COMMON_TAIL
    ),
}

DEFAULT_THEME = "light"

# Portrait framing fits a full standing figure far better than the default
# landscape and matches the reference board.
GENERATE_IMAGE_SIZE = "portrait_4_3"


class ContentFlaggedError(Exception):
    """Raised when fal.ai's safety filter flags the generated image."""


def generate_image(prompt: str, model: str = DEFAULT_MODEL,
                   theme: str = DEFAULT_THEME) -> str:
    """Generate an image from a prompt, forced into the app's house style.

    The user-supplied prompt only describes the subject; it is always
    wrapped in the theme's style template so every generation keeps the
    radiographic aesthetic.

    Args:
        prompt: Text description of the subject to generate.
        model: fal.ai model id to use.
        theme: "dark" (glowing anatomy on black film) or "light" (black
            anatomy on pale film).

    Returns:
        Direct URL to the generated image.

    Raises:
        ValueError: If the prompt is empty.
        ContentFlaggedError: If the safety filter flags the result (fal.ai
            returns a blank/black image in that case).
    """
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("The prompt cannot be empty.")

    template = STYLE_TEMPLATES.get(theme, STYLE_TEMPLATES[DEFAULT_THEME])
    styled_prompt = template.format(subject=prompt)

    # Safety checker disabled: descriptions distilled from visitors' intimate
    # or traumatic stories trip it with false positives, and a flagged birth
    # or re-anchor would discard their contributions. The fixed clinical
    # X-ray style template keeps outputs non-explicit by construction.
    with logfire.span("generate image", model=model, subject=prompt,
                      styled_prompt=styled_prompt) as span:
        result = fal_client.subscribe(
            model,
            arguments={"prompt": styled_prompt,
                       "image_size": GENERATE_IMAGE_SIZE,
                       "output_format": OUTPUT_FORMAT,
                       "enable_safety_checker": False},
        )

        if any(result.get("has_nsfw_concepts", [])):
            span.set_attribute("flagged", True)
            raise ContentFlaggedError(
                "The prompt was flagged by the safety filter, so the image came back "
                "blank. Try rephrasing it."
            )

        image_url = result["images"][0]["url"]
        span.set_attribute("image_url", image_url)
        return image_url


# Appended to every Kontext edit so chained transformations cannot drift away
# from the house aesthetic. Kept short on purpose: a long "preserve everything"
# paragraph competes with the actual instruction for the model's attention and
# ends up suppressing the requested change (verified empirically).
EDIT_STYLE_GUARDS = {
    "dark": ("Keep the dark X-ray film aesthetic: matte analog film grain, "
             "glowing anatomy on a black film background, never glossy 3D."),
    "light": ("Keep the pale radiograph film aesthetic: matte analog film "
              "grain, dark anatomy on a white-gray film background, never "
              "glossy 3D."),
}

# fal default is 3.5, which is tuned for subtle photo edits and is too
# conservative for the visible anatomical mutations this project needs.
EDIT_GUIDANCE_SCALE = 5.0

# fal default is "2" (very strict, scale 1-6). The questionnaire deliberately
# invites intimate and traumatic material (shame, bodies, abuse, grief), so
# curator instructions routinely mention sensitive anatomy and the strict
# filter produces false positives that silently discard a visitor's story.
# "6" is the most permissive; the clinical X-ray aesthetic plus the curator's
# "clinical, never graphic" rule keep outputs non-explicit by construction.
EDIT_SAFETY_TOLERANCE = "6"


def edit_image(image_url: str, instruction: str, model: str = KONTEXT_MODEL,
               guidance_scale: float = EDIT_GUIDANCE_SCALE,
               theme: str = DEFAULT_THEME) -> str:
    """Transform an existing image with an editing instruction (FLUX Kontext).

    Unlike generate_image, this preserves the creature and only applies the
    requested change, so the monster evolves instead of being replaced.

    Args:
        image_url: Public URL of the current image.
        instruction: Imperative editing instruction (what should change).
        model: fal.ai Kontext model id.
        guidance_scale: How strongly to follow the instruction (fal default
            3.5 is too weak for visible mutations; 5.0 works reliably).
        theme: Palette of the CURRENT image ("dark"/"light"), so the style
            guard defends the right one.

    Returns:
        Direct URL to the edited image.

    Raises:
        ValueError: If the instruction is empty.
        ContentFlaggedError: If the safety filter flags the result.
    """
    instruction = instruction.strip()
    if not instruction:
        raise ValueError("The edit instruction cannot be empty.")

    guard = EDIT_STYLE_GUARDS.get(theme, EDIT_STYLE_GUARDS[DEFAULT_THEME])
    with logfire.span("edit image", model=model, instruction=instruction,
                      full_prompt=f"{instruction} {guard}",
                      source_image_url=image_url,
                      guidance_scale=guidance_scale,
                      safety_tolerance=EDIT_SAFETY_TOLERANCE) as span:
        result = fal_client.subscribe(
            model,
            arguments={"prompt": f"{instruction} {guard}",
                       "image_url": image_url,
                       "guidance_scale": guidance_scale,
                       "output_format": OUTPUT_FORMAT,
                       "safety_tolerance": EDIT_SAFETY_TOLERANCE},
        )

        if any(result.get("has_nsfw_concepts", [])):
            span.set_attribute("flagged", True)
            raise ContentFlaggedError(
                "The edit was flagged by the safety filter. Try rephrasing it."
            )

        edited_url = result["images"][0]["url"]
        span.set_attribute("image_url", edited_url)
        return edited_url


def edit_image_uncensored(image_url: str, instruction: str,
                          theme: str = DEFAULT_THEME) -> str:
    """Edit with the open-weights Kontext dev model, safety checker OFF.

    Fallback for when flux-pro/kontext's server-side moderation censors an
    edit (it returns a black image). Dev applies structural changes more
    weakly than pro, but it always returns a real image, so a visitor's
    contribution is never silently discarded.
    """
    instruction = instruction.strip()
    if not instruction:
        raise ValueError("The edit instruction cannot be empty.")

    guard = EDIT_STYLE_GUARDS.get(theme, EDIT_STYLE_GUARDS[DEFAULT_THEME])
    with logfire.span("edit image (uncensored dev fallback)",
                      model=KONTEXT_DEV_MODEL, instruction=instruction,
                      source_image_url=image_url) as span:
        result = fal_client.subscribe(
            KONTEXT_DEV_MODEL,
            arguments={"prompt": f"{instruction} {guard}",
                       "image_url": image_url,
                       "guidance_scale": EDIT_GUIDANCE_SCALE,
                       "output_format": OUTPUT_FORMAT,
                       "enable_safety_checker": False},
        )
        edited_url = result["images"][0]["url"]
        span.set_attribute("image_url", edited_url)
        return edited_url


# Fraction of the denoising schedule applied in a refresh: high enough to
# regenerate crisp fine detail, low enough to preserve the creature's
# composition and identity. Calibrated empirically on degraded edits:
# 0.4 barely repaints, 0.55-0.7 restores detail keeping identity, 0.85
# already changes palette and materials.
REFRESH_STRENGTH = 0.6


def refresh_image(image_url: str, description: str,
                  theme: str = DEFAULT_THEME,
                  strength: float = REFRESH_STRENGTH) -> str:
    """Re-anchor: regenerate the CURRENT image with fresh detail (img2img).

    Chained Kontext edits progressively lose sharpness (high-frequency
    detail loss + reprocessing artifacts). This runs the current image
    through flux/dev image-to-image at 40 steps with the genome description:
    the composition and identity survive, the fine detail is repainted
    cleanly. Much better than the old text-only re-anchor, which invented a
    brand-new creature every time.

    Args:
        image_url: Public URL of the current (degraded) image.
        description: Full creature description from the genome.
        theme: Palette theme, applied via the style template.
        strength: 0-1; how much of the image is re-diffused. Lower keeps
            more of the original, higher repaints more aggressively.

    Returns:
        Direct URL to the refreshed image.
    """
    template = STYLE_TEMPLATES.get(theme, STYLE_TEMPLATES[DEFAULT_THEME])
    styled_prompt = template.format(subject=description.strip())

    with logfire.span("refresh image (img2img reanchor)", model=REFRESH_MODEL,
                      description=description, strength=strength,
                      source_image_url=image_url) as span:
        result = fal_client.subscribe(
            REFRESH_MODEL,
            arguments={"prompt": styled_prompt,
                       "image_url": image_url,
                       "strength": strength,
                       "image_size": GENERATE_IMAGE_SIZE,
                       "num_inference_steps": 40,
                       "output_format": OUTPUT_FORMAT,
                       "enable_safety_checker": False},
        )
        refreshed_url = result["images"][0]["url"]
        span.set_attribute("image_url", refreshed_url)
        return refreshed_url


def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe audio bytes to text using fal.ai Whisper.

    Args:
        audio_bytes: Raw audio data (wav, mp3, webm, etc.).

    Returns:
        Transcribed text.
    """
    audio_url = fal_client.upload(audio_bytes, "audio/wav")
    result = fal_client.subscribe("fal-ai/whisper", arguments={"audio_url": audio_url})
    return result["text"].strip()


if __name__ == "__main__":
    url = generate_image("a dark monster in a foggy forest")
    print(url)
