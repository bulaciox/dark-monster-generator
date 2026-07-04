"""Image generation logic backed by fal.ai.

This module is independent from the UI: it can be used from Streamlit, a script
or tests. The API key is read from the FAL_KEY environment variable (loaded from
a .env file).
"""

import fal_client
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "fal-ai/flux/schnell"
KONTEXT_MODEL = "fal-ai/flux-pro/kontext"

# Fixed house style: every generation is forced into this dark biomechanical /
# medical-scan aesthetic regardless of what the user asks for. The user's
# input only supplies the subject; it is dropped into {subject} below.
STYLE_TEMPLATE = (
    "{subject}. "
    "Dark biomechanical creature design rendered as a medical X-ray / MRI scan, "
    "translucent skeletal anatomy with visible bones, spine, ribcage and vascular "
    "networks glowing faintly through semi-transparent flesh, exposed cybernetic "
    "implants and circuitry fused with organic tissue, bioluminescent nerve "
    "fibers. "
    "Monochrome grayscale and cold blue-white palette with sparse cyan or "
    "blood-red accent highlights, pure black background. "
    "Overlaid futuristic medical/sci-fi HUD interface: thin scan lines, small "
    "annotation labels, technical readouts, warning glyphs, crosshairs and "
    "diagnostic data panels framing the subject like a scanner readout. "
    "Volumetric light, cinematic film-still concept art, hyper-detailed, "
    "clinical and unsettling mood, 4k. "
    "No bright colors, no cartoon style, no daylight, no warm tones."
)


class ContentFlaggedError(Exception):
    """Raised when fal.ai's safety filter flags the generated image."""


def generate_image(prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Generate an image from a prompt, forced into the app's house style.

    The user-supplied prompt only describes the subject; it is always
    wrapped in STYLE_TEMPLATE so every generation keeps the same dark
    biomechanical X-ray / medical-HUD aesthetic.

    Args:
        prompt: Text description of the subject to generate.
        model: fal.ai model id to use.

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

    styled_prompt = STYLE_TEMPLATE.format(subject=prompt)

    # Safety checker disabled: descriptions distilled from visitors' intimate
    # or traumatic stories trip it with false positives, and a flagged birth
    # or re-anchor would discard their contributions. The fixed clinical
    # X-ray style template keeps outputs non-explicit by construction.
    result = fal_client.subscribe(
        model,
        arguments={"prompt": styled_prompt, "enable_safety_checker": False},
    )

    if any(result.get("has_nsfw_concepts", [])):
        raise ContentFlaggedError(
            "The prompt was flagged by the safety filter, so the image came back "
            "blank. Try rephrasing it."
        )

    return result["images"][0]["url"]


# Appended to every Kontext edit so chained transformations cannot drift away
# from the house aesthetic. Kept short on purpose: a long "preserve everything"
# paragraph competes with the actual instruction for the model's attention and
# ends up suppressing the requested change (verified empirically).
EDIT_STYLE_GUARD = "Keep the dark X-ray aesthetic and black background."

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
               guidance_scale: float = EDIT_GUIDANCE_SCALE) -> str:
    """Transform an existing image with an editing instruction (FLUX Kontext).

    Unlike generate_image, this preserves the creature and only applies the
    requested change, so the monster evolves instead of being replaced.

    Args:
        image_url: Public URL of the current image.
        instruction: Imperative editing instruction (what should change).
        model: fal.ai Kontext model id.
        guidance_scale: How strongly to follow the instruction (fal default
            3.5 is too weak for visible mutations; 5.0 works reliably).

    Returns:
        Direct URL to the edited image.

    Raises:
        ValueError: If the instruction is empty.
        ContentFlaggedError: If the safety filter flags the result.
    """
    instruction = instruction.strip()
    if not instruction:
        raise ValueError("The edit instruction cannot be empty.")

    result = fal_client.subscribe(
        model,
        arguments={"prompt": f"{instruction} {EDIT_STYLE_GUARD}",
                   "image_url": image_url,
                   "guidance_scale": guidance_scale,
                   "safety_tolerance": EDIT_SAFETY_TOLERANCE},
    )

    if any(result.get("has_nsfw_concepts", [])):
        raise ContentFlaggedError(
            "The edit was flagged by the safety filter. Try rephrasing it."
        )

    return result["images"][0]["url"]


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
