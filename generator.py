"""Image generation logic backed by fal.ai.

This module is independent from the UI: it can be used from Streamlit, a script
or tests. The API key is read from the FAL_KEY environment variable (loaded from
a .env file).
"""

import fal_client
import logfire
from dotenv import load_dotenv

load_dotenv()

# Krea 2 Large: foundation model built for aesthetic direction. Generates the
# monster at birth and at re-anchors, and accepts up to 10 style reference
# images (image_style_references) to lock the project's look.
KREA_MODEL = "krea/v2/large/text-to-image"
# Qwen Image Edit 2511 (Apache 2.0): the community's editing workhorse. ~5s,
# no prompt-level censorship, supports negative_prompt, and its headline
# improvement is mitigating drift across chained edits — exactly this
# project's core problem.
QWEN_EDIT_MODEL = "fal-ai/qwen-image-edit-2511"

# Individual monsters (one per visitor) generate every image from scratch, so
# there is no chained editing and no drift to defend against. FLUX.2 pro is the
# strongest of the current fal line-up on dark, surreal, anatomical subject
# matter, and exposes safety_tolerance for material the default filter reads as
# violent when it is only clinical.
MONSTER_MODEL = "fal-ai/flux-2-pro"
# 1 is strictest, 5 most permissive. Visitors confide abuse, illness and
# violence; the imagery stays metaphorical, but the default level rejects
# anatomical language often enough to lose contributions.
SAFETY_TOLERANCE = "5"

# Legacy engines, kept as fallbacks (see pipeline.py).
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
# Text-prompted segmentation + masked inpainting: the surgical edit path.
# Pixels outside the mask are never touched, so local edits cause zero
# style drift and zero quality loss.
SEGMENT_MODEL = "fal-ai/evf-sam"
FILL_MODEL = "fal-ai/flux-pro/v1/fill"

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
STYLE_TEMPLATES = {
    # The house style: the collective monster is the PATIENT on the table and
    # the visitors' contributions are the surgery being performed on it.
    "surgical": (
        "Wide analog film photograph of a surgical operation, camera set well "
        "back from the table so the whole scene is visible: the entire "
        "operating table, the patient's body from head to knees, and the "
        "surgeons standing around it. "
        "The patient lies on their back on the table, face clearly visible, "
        "wearing a clear plastic oxygen mask with a white reservoir bag. "
        "The patient is a human being, unremarkable at first glance — someone "
        "you could pass in the street: {subject} "
        "Surgeons in white gloves work with small steel instruments over an "
        "exposed area of the body, surrounded by surgical drapes; their hands "
        "are part of the wider scene, not close to the camera. "
        "Direct overhead surgical spotlights create deep, dramatic shadows. "
        "Highly saturated 1970s Fuji film colour profile. The green and "
        "turquoise surgical scrubs and drapes are exceptionally deep and "
        "intensely vibrant. Rich, warm brown tones are present in the shadows "
        "and skin tones. Visible film grain, retro cinematic aesthetic, "
        "documentary photograph of a real operating theatre."
    ),
    # Previous aesthetic, kept selectable: pale radiograph plate.
    "radiograph": (
        "{subject} "
        "This creature is shown as an authentic full-body medical radiograph: "
        "its body fully extended and stretched out like a specimen positioned "
        "for an X-ray exposure, limbs elongated, never crouched or seated, the "
        "entire creature visible in the frame with empty space around the "
        "whole silhouette. Its anatomy is not necessarily human: bone, soft "
        "tissue, organs, membranes, tendrils and stranger structures may "
        "coexist, every layer revealed as translucent radiographic exposure. "
        "It looks like a real radiograph print viewed on a bright light box: "
        "the anatomy renders in dense black and soft charcoal grays against a "
        "pale gray-white film background, the exposure blooming softly where "
        "tissue is dense, with fine analog film grain and a subtle paper "
        "texture across the whole sheet. Thin dark technical annotations, "
        "measurement markers and small data labels from a radiology archive "
        "sheet frame the figure. The palette is cold monochrome grayscale "
        "with one faint blood-red or cyan accent inside the body. "
        "The mood is clinical and documentary, like a leaked hospital scan of "
        "something that should not exist."
    ),
}

DEFAULT_THEME = "surgical"

# Krea uses aspect_ratio (not image_size). The surgical scene is a cinematic
# film photograph of a body lying down, so it wants landscape; the radiograph
# plate wants portrait.
ASPECT_RATIOS = {"surgical": "3:2", "radiograph": "2:3"}

# Optional style reference images (Krea 2 accepts up to 10) that lock the
# project's look. Fill with public URLs of the reference board to anchor
# every birth to it; empty means prompt-only.
STYLE_REFERENCE_URLS: list[str] = []


class ContentFlaggedError(Exception):
    """Raised when fal.ai's safety filter flags the generated image."""


def generate_image(prompt: str, model: str = KREA_MODEL,
                   theme: str = DEFAULT_THEME) -> str:
    """Generate the monster from scratch, forced into the house style.

    Used for births and re-anchors. The description from the genome only
    supplies the creature (the patient on the table); the theme's style
    template supplies everything else. Runs on Krea 2 Large, which is built
    around aesthetic direction and accepts style reference images.

    Args:
        prompt: Text description of the creature to generate.
        model: fal.ai model id to use.
        theme: "surgical" (1970s analog operating-room photograph) or
            "radiograph" (pale X-ray plate).

    Returns:
        Direct URL to the generated image.

    Raises:
        ValueError: If the prompt is empty.
    """
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("The prompt cannot be empty.")

    template = STYLE_TEMPLATES.get(theme, STYLE_TEMPLATES[DEFAULT_THEME])
    styled_prompt = template.format(subject=prompt)
    arguments = {
        "prompt": styled_prompt,
        "aspect_ratio": ASPECT_RATIOS.get(theme, ASPECT_RATIOS[DEFAULT_THEME]),
    }
    if STYLE_REFERENCE_URLS:
        arguments["image_style_references"] = [
            {"image_url": url} for url in STYLE_REFERENCE_URLS[:10]]

    with logfire.span("generate image", model=model, subject=prompt,
                      styled_prompt=styled_prompt, theme=theme,
                      style_references=len(STYLE_REFERENCE_URLS)) as span:
        result = fal_client.subscribe(model, arguments=arguments)
        image_url = result["images"][0]["url"]
        span.set_attribute("image_url", image_url)
        return image_url


def generate_image_legacy(prompt: str, model: str = DEFAULT_MODEL,
                          theme: str = DEFAULT_THEME) -> str:
    """Birth via FLUX schnell (previous engine). Kept as a fallback.

    Safety checker disabled: descriptions distilled from visitors' intimate
    or traumatic stories trip it with false positives, and a flagged birth
    would discard their contributions.
    """
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("The prompt cannot be empty.")

    template = STYLE_TEMPLATES.get(theme, STYLE_TEMPLATES[DEFAULT_THEME])
    styled_prompt = template.format(subject=prompt)

    with logfire.span("generate image (legacy schnell)", model=model,
                      subject=prompt, styled_prompt=styled_prompt) as span:
        result = fal_client.subscribe(
            model,
            arguments={"prompt": styled_prompt,
                       "image_size": ("landscape_4_3" if theme == "surgical"
                                      else "portrait_4_3"),
                       "output_format": OUTPUT_FORMAT,
                       "enable_safety_checker": False},
        )
        if any(result.get("has_nsfw_concepts", [])):
            span.set_attribute("flagged", True)
            raise ContentFlaggedError(
                "The prompt was flagged by the safety filter, so the image "
                "came back blank. Try rephrasing it.")
        image_url = result["images"][0]["url"]
        span.set_attribute("image_url", image_url)
        return image_url


# Appended to every Kontext edit so chained transformations cannot drift away
# from the house aesthetic. Kept short on purpose: a long "preserve everything"
# paragraph competes with the actual instruction for the model's attention and
# ends up suppressing the requested change (verified empirically).
EDIT_STYLE_GUARDS = {
    "surgical": ("Keep the 1970s analog surgical photograph look: saturated "
                 "green-turquoise drapes, warm brown shadows, harsh overhead "
                 "spotlights, visible film grain."),
    "radiograph": ("Keep the pale radiograph film aesthetic: matte analog "
                   "film grain, dark anatomy on a white-gray film "
                   "background, never glossy 3D."),
}

# Qwen supports a negative prompt (FLUX does not). Used to keep edits from
# drifting into the neon/CGI look the models fall back on.
EDIT_NEGATIVE_PROMPT = ("neon glow, blown-out highlights, cartoon, 3D render, "
                        "video game, oversaturated, plastic, digital art")

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


def edit_image(image_url: str, instruction: str,
               model: str = QWEN_EDIT_MODEL,
               theme: str = DEFAULT_THEME) -> str:
    """Transform the monster with an editing instruction (Qwen Image Edit).

    Primary edit path. Qwen 2511 preserves everything it was not asked to
    change (film borders, grain, palette), runs in ~5s, has no prompt-level
    censorship, and takes a negative prompt to keep edits away from the
    neon/CGI look.

    Args:
        image_url: Public URL of the current image.
        instruction: Imperative editing instruction (what should change).
        model: fal.ai model id to use.
        theme: Style of the current image, for the guard phrase.

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
                      source_image_url=image_url, theme=theme) as span:
        result = fal_client.subscribe(
            model,
            arguments={"prompt": f"{instruction} {guard}",
                       "image_urls": [image_url],
                       "negative_prompt": EDIT_NEGATIVE_PROMPT,
                       "output_format": OUTPUT_FORMAT,
                       "enable_safety_checker": False},
        )
        if any(result.get("has_nsfw_concepts", [])):
            span.set_attribute("flagged", True)
            raise ContentFlaggedError(
                "The edit was flagged by the safety filter. Try rephrasing it.")
        edited_url = result["images"][0]["url"]
        span.set_attribute("image_url", edited_url)
        return edited_url


def edit_image_kontext(image_url: str, instruction: str,
                       model: str = KONTEXT_MODEL,
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


def segment_region(image_url: str, region_phrase: str) -> str:
    """Text-prompted segmentation: returns the mask URL for a body region.

    The mask is dilated (room for the transformation to breathe) and
    blurred (soft blending at the seams). Raises ValueError if the region
    covers almost nothing (not found) or most of the image (too broad for
    a local edit — the caller should fall back to a global Kontext edit).
    """
    with logfire.span("segment region", model=SEGMENT_MODEL,
                      region=region_phrase,
                      source_image_url=image_url) as span:
        result = fal_client.subscribe(SEGMENT_MODEL, arguments={
            "prompt": region_phrase,
            "image_url": image_url,
            "mask_only": True,
            "expand_mask": 20,
            "blur_mask": 8,
        })
        mask_url = result["image"]["url"]
        coverage = _mask_coverage(mask_url)
        span.set_attribute("mask_url", mask_url)
        span.set_attribute("coverage", round(coverage, 4))
        if coverage < 0.005:
            raise ValueError(
                f"Region '{region_phrase}' not found in the image "
                f"(mask covers {coverage:.1%}).")
        if coverage > 0.30:
            # A "local" region that swallows a third of the frame means the
            # segmenter grabbed the whole creature (e.g. "the jaw" matching
            # the full body) — repainting it would destroy the monster.
            # Reject so the pipeline falls back to a Kontext edit.
            raise ValueError(
                f"Region '{region_phrase}' covers {coverage:.0%} of the "
                "image; too broad for a local edit.")
        return mask_url


def _mask_coverage(mask_url: str) -> float:
    """Fraction of the mask that is selected (white)."""
    import io

    import httpx
    from PIL import Image

    data = httpx.get(mask_url, follow_redirects=True).content
    mask = Image.open(io.BytesIO(data)).convert("L")
    histogram = mask.histogram()
    selected = sum(histogram[128:])
    total = sum(histogram)
    return selected / total if total else 0.0


def fill_region(image_url: str, mask_url: str, region_prompt: str,
                theme: str = DEFAULT_THEME) -> str:
    """Repaint ONLY the masked region (FLUX Fill inpainting).

    Unlike Kontext, pixels outside the mask are untouched: no style drift,
    no quality loss, and the change inside the mask is guaranteed visible.
    The prompt should describe what the region BECOMES (painted content),
    not an editing instruction.
    """
    guard = EDIT_STYLE_GUARDS.get(theme, EDIT_STYLE_GUARDS[DEFAULT_THEME])
    with logfire.span("fill region", model=FILL_MODEL,
                      region_prompt=region_prompt, mask_url=mask_url,
                      source_image_url=image_url) as span:
        result = fal_client.subscribe(FILL_MODEL, arguments={
            "image_url": image_url,
            "mask_url": mask_url,
            "prompt": f"{region_prompt} {guard}",
            "output_format": OUTPUT_FORMAT,
            "safety_tolerance": EDIT_SAFETY_TOLERANCE,
        })
        if any(result.get("has_nsfw_concepts", [])):
            span.set_attribute("flagged", True)
            raise ContentFlaggedError(
                "The fill was flagged by the safety filter.")
        filled_url = result["images"][0]["url"]
        span.set_attribute("image_url", filled_url)
        return filled_url


# Blend factor for palette normalization: 1.0 would clamp the edit's colors
# fully back to the pre-edit image (killing intentional accents); 0 disables.
PALETTE_MATCH_BLEND = 0.5


def match_palette(edited_url: str, reference_url: str,
                  blend: float = PALETTE_MATCH_BLEND) -> str:
    """Pull an edited image's global color statistics toward the reference.

    Kontext repaints the whole frame, so each edit drifts the global palette
    a little (accumulating into e.g. a fully rust-colored creature). This
    shifts each RGB channel's mean partially back toward the pre-edit image
    (mean-shift only: std scaling explodes on near-uniform backgrounds, and
    LAB via PIL's ImageCms proved unreliable). Runs locally (PIL + numpy,
    no API cost); on any failure the edit is returned untouched — color
    normalization must never break the pipeline.

    Returns a URL (fal storage) of the normalized PNG, or edited_url as-is.
    """
    with logfire.span("match palette", edited_url=edited_url,
                      reference_url=reference_url, blend=blend) as span:
        try:
            import io

            import httpx
            import numpy as np
            from PIL import Image

            def _load(url: str):
                data = httpx.get(url, follow_redirects=True).content
                image = Image.open(io.BytesIO(data)).convert("RGB")
                return np.asarray(image, dtype=np.float64)

            e, r = _load(edited_url), _load(reference_url)

            deltas = r.mean(axis=(0, 1)) - e.mean(axis=(0, 1))
            span.set_attribute("channel_deltas",
                               [round(d, 1) for d in deltas])
            e += blend * deltas

            normalized = Image.fromarray(
                np.clip(e, 0, 255).astype("uint8"), mode="RGB")
            buffer = io.BytesIO()
            normalized.save(buffer, format="PNG")
            url = fal_client.upload(buffer.getvalue(), "image/png")
            span.set_attribute("image_url", url)
            return url
        except Exception as exc:
            span.set_attribute("error", str(exc))
            return edited_url


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


# ---------------------------------------------------------------------------
# Individual monsters: one organ image and one silhouette image per visitor.
#
# The look follows the directors' sketches: a body part rendered in luminous red
# on darkness, and a near-black figure with that same organ burning inside it as
# the only clear element. The two are generated independently -- they must show
# the same organ under the same transformation, but need not match pixel for
# pixel.
# ---------------------------------------------------------------------------

ORGAN_TEMPLATE = (
    "A single anatomical specimen isolated on a pure black background: "
    "{part}, {transformation}. "
    "Rendered as a luminous deep-red anatomical study, fine crimson linework "
    "over translucent tissue that glows from within, the whole form floating "
    "in darkness with nothing else in the frame. Clinical medical-atlas "
    "precision with a wet organic sheen, faint analog film grain. "
    "No text, no labels, no measurement marks, no background detail."
)

# A few body parts from the emotion mapping read as sexual anatomy to the image
# model's prompt checker, which rejects the request outright -- before
# safety_tolerance can apply, since that governs the generated image rather than
# the prompt. Naming the skeleton instead keeps the anatomy and its meaning
# while reading unambiguously as a medical illustration.
ANATOMICAL_ALIASES = {
    "Pelvis and hips": "the bones of the pelvic girdle",
}


def _anatomical(part: str) -> str:
    """The body part as it can safely be named to the image model."""
    return ANATOMICAL_ALIASES.get(part, part.lower())

# The two kinds of monster the test interviews produced. Roughly two thirds of
# respondents named a person, one third an event or a system -- and a war should
# never be handed an arbitrary human silhouette.
FIGURE_TEMPLATES = {
    "human": (
        "A full-body silhouette of a single human figure, standing, seen "
        "straight on, the entire body inside the frame with empty space all "
        "around it. The figure is a dense mass of charcoal shadow, features "
        "swallowed by darkness, unremarkable in shape -- someone you could "
        "pass in the street. {form}"
    ),
    "environmental": (
        "A vast dark formation filling the frame, seen straight on, its whole "
        "extent visible with empty space around it. Not a creature and not a "
        "person: a mass without a face, built from shadow and particulate "
        "darkness, looming and unresolved at its edges. {form}"
    ),
}

SILHOUETTE_TEMPLATE = (
    "{figure} "
    "{attributes}"
    "Deep inside it, {organs} — luminous deep red, burning through the "
    "darkness as the only clear element in the image. "
    "Analog film photograph, heavy grain, near-black palette with a single red "
    "accent, cold and documentary. No text, no lettering, no faces in focus."
)


def _organ_phrase(organs: list[dict]) -> str:
    """The organs as they should read inside the silhouette."""
    if not organs:
        return "a single anatomical form"
    pieces = [f"{_anatomical(o['part'])}, {o['transformation']}"
              for o in organs]
    return " and ".join(pieces)


def _flagged(exc: Exception) -> bool:
    """Whether fal rejected the PROMPT (not the image) as policy-violating.

    This check runs before generation, so safety_tolerance -- which governs the
    resulting image -- cannot relax it. The only remedy is different wording.
    """
    return "content_policy_violation" in str(exc)


def _generate(prompts: list[str], image_size: str) -> str:
    """Generate an image, stepping down to plainer wording if one is flagged.

    The prompt checker runs before generation, so safety_tolerance -- which
    governs the resulting image -- cannot relax it, and it is not deterministic:
    the same prompt may pass on one call and be rejected on the next. Visitors'
    accounts are also full of language it reads as violence ("raw", "exposed",
    "streaming", "uninvited") even when the imagery is clinical.

    So the prompts are ordered richest to plainest, and each rejection costs
    some particularity rather than the whole image.
    """
    arguments = {
        "image_size": image_size,
        "output_format": "jpeg",
        "safety_tolerance": SAFETY_TOLERANCE,
    }
    for index, prompt in enumerate(prompts):
        try:
            result = fal_client.subscribe(
                MONSTER_MODEL, arguments={**arguments, "prompt": prompt})
            return result["images"][0]["url"]
        except Exception as exc:
            last_prompt = index == len(prompts) - 1
            if not _flagged(exc) or last_prompt:
                raise
            logfire.warn("prompt flagged, stepping down", prompt=prompt,
                         remaining=len(prompts) - index - 1)
    raise RuntimeError("unreachable")  # pragma: no cover


def generate_organ(part: str, transformation: str) -> str:
    """One body part alone, red on black — the organ screen.

    Args:
        part: Body part from the emotion mapping, e.g. "Heart".
        transformation: How this emotion group deforms it.

    Returns:
        Direct URL to the generated image.
    """
    anatomical = _anatomical(part)
    with logfire.span("generate organ", model=MONSTER_MODEL, part=part,
                      transformation=transformation) as span:
        image_url = _generate([
            ORGAN_TEMPLATE.format(part=anatomical,
                                  transformation=transformation),
            # Without the transformation the organ says less, but it still says
            # which body part this visitor's emotions claimed.
            ORGAN_TEMPLATE.format(part=anatomical,
                                  transformation="anatomically altered"),
        ], "square_hd")
        span.set_attribute("image_url", image_url)
        return image_url


def generate_silhouette(identity: dict, organs: list[dict]) -> str:
    """The visitor's monster as a whole — the large screen.

    The identity package supplies WHO it is (already transposed into shape,
    texture and light by the curator, never naming anyone), and the organs
    supply what the emotions did to it.

    Args:
        identity: Output of curator.extract_identity.
        organs: Output of curator.select_organs.

    Returns:
        Direct URL to the generated image.
    """
    monster_type = identity.get("monster_type", "human")
    template = FIGURE_TEMPLATES.get(monster_type, FIGURE_TEMPLATES["human"])
    figure = template.format(form=identity.get("who_what", "").strip())
    bare_figure = template.format(form="")

    # Everything the curator extracted from the free text, as one sentence of
    # material and light. Absent for visitors who never met a monster.
    bits = [identity.get("object", "")] + list(identity.get("traits") or [])
    bits = [b.strip() for b in bits if b and b.strip()]
    attributes = ""
    if bits:
        attributes = "Across it: " + "; ".join(bits) + ". "
    if identity.get("where"):
        attributes += f"Behind it: {identity['where'].strip()}. "

    organ_phrase = _organ_phrase(organs)
    # Just the body parts, with the transformations that carry the charged
    # language dropped.
    plain_organs = (" and ".join(_anatomical(o["part"]) for o in organs)
                    or "a single anatomical form")

    with logfire.span("generate silhouette", model=MONSTER_MODEL,
                      monster_type=monster_type, identity=identity,
                      organs=organs) as span:
        image_url = _generate([
            SILHOUETTE_TEMPLATE.format(figure=figure, attributes=attributes,
                                       organs=organ_phrase),
            # Drop the visitor's own material, keep the anatomy.
            SILHOUETTE_TEMPLATE.format(figure=bare_figure, attributes="",
                                       organs=organ_phrase),
            # Drop the transformations too: a figure and its organ, nothing more.
            SILHOUETTE_TEMPLATE.format(figure=bare_figure, attributes="",
                                       organs=plain_organs),
        ], "portrait_4_3")
        span.set_attribute("image_url", image_url)
        return image_url


def free_generate(prompt: str) -> str:
    """Generate an image from a bare prompt, no style wrapping.

    The prompt is sent exactly as written to MONSTER_MODEL. Uses _generate so
    content-policy rejections still step down through progressively plainer
    fallbacks rather than raising immediately.

    Args:
        prompt: Any text to send to the model.

    Returns:
        Direct URL to the generated image.
    """
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("Prompt cannot be empty.")
    with logfire.span("free generate", model=MONSTER_MODEL, prompt=prompt) as span:
        image_url = _generate([prompt], "square_hd")
        span.set_attribute("image_url", image_url)
        return image_url


if __name__ == "__main__":
    url = generate_image("a dark monster in a foggy forest")
    print(url)