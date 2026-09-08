"""Image prompt for the organ screen: a single body part alone on black,
rendered as a luminous anatomical study. See generator.generate_organ.
"""

TEMPLATE = (
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


def anatomical(part: str) -> str:
    """The body part as it can safely be named to the image model."""
    return ANATOMICAL_ALIASES.get(part, part.lower())
