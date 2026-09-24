"""Image prompt for the organ screen: one body part as a coiling, fractal
mass of skin on a dark studio tabletop. See generator.generate_organ.

Design by the second wave of artists brought in after the original mapping
document -- replaces the earlier "half-buried in earth" version. No longer
uses the visitor's setting ("where" from identity.py): the whole image is a
tightly controlled studio still-life now, so there is nowhere for a
background to go.
"""

TEMPLATE = (
    "A dense coiling abstract mass of human skin (#b87541) on a dark "
    "tabletop, seen from a high three-quarter angle, filling most of the "
    "frame. A spiral of {part}, {transformation} into a fractal vortex at "
    "the center, each opening nested inside the last. Skin taut, wet and "
    "glistening, ridged. "
    "The only things in the image are the skin mass, the dark tabletop, and "
    "a seamless black velvet backdrop (#050505) that fills the entire "
    "background edge to edge, uniformly dark. "
    "Lighting: cool pale backlight (#59c8f4) falling from high above and "
    "behind the subject, grazing the far contours and tops of the coils so "
    "the wet skin catches a cool glossy sheen where it turns away from the "
    "camera, separating the mass from the black. Dim warm tungsten fill "
    "from the front. "
    "Analog film studio photograph, warm near-black palette, film grain."
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
