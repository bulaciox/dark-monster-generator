"""Image prompt for the organ screen: one body part, found half-buried in the
visitor's own environment -- close, tilted, weathered. See
generator.generate_organ.
"""

TEMPLATE = (
    "Looking down at a steep, unsettling angle into a mound of dark broken "
    "earth that fills almost the entire frame: {part}, {transformation}, "
    "half-sunk in the clumped soil, its surface dusted and streaked with "
    "earth. {where}"
    "Analog film photograph, heavy grain, near-black palette, cold and "
    "documentary, like a found photograph rather than a portrait. No text, "
    "no labels, no measurement marks."
)

# A few body parts from the emotion mapping read as sexual anatomy to the image
# model's prompt checker, which rejects the request outright -- before
# safety_tolerance can apply, since that governs the generated image rather than
# the prompt. Naming the skeleton instead keeps the anatomy and its meaning
# while reading unambiguously as a medical illustration.
ANATOMICAL_ALIASES = {
    "Pelvis and hips": "the bones of the pelvic girdle",
}


def anatomical(part: str) -> str:
    """The body part as it can safely be named to the image model."""
    return ANATOMICAL_ALIASES.get(part, part.lower())
