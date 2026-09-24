"""Image prompt for the monster screen: the figure alone.

The organ is deliberately absent -- the organ screen already carries it.
See generator.generate_silhouette.

Design by the second wave of artists brought in after the original mapping
document -- replaces the earlier "charcoal shadow on empty ground" version
with a backlit warm-haze cutout. Unlike the old shared TEMPLATE, the two
monster_type variants below are no longer built from one generic wrapper:
their closing imagery differs on purpose (an oversized, sagging head for a
human monster; a self-coiling spiral for an environmental one), so each is
now a complete prompt in its own right. Only "environmental" places the
visitor's own object/traits/where material ({attributes}); the human
variant never did, by the artists' design, and always reads {form} only.
"""

# The two kinds of monster the test interviews produced. Roughly two thirds of
# respondents named a person, one third an event or a system -- and a war should
# never be handed an arbitrary human silhouette.
FIGURE_TEMPLATES = {
    "human": (
        "A pitch-black silhouette of a standing human figure against a warm "
        "glowing haze (#e3ae86), backlit, the whole body a flat featureless "
        "cut-out. {form} its head is huge and heavy -- a swollen, lumpen "
        "mass far too large for the small body, sagging sideways and "
        "slumping onto the shoulder under its own weight. Extra ear-like "
        "folds and bulging lobes swell from the head's black outline. "
        "Analog film studio photograph, warm near-black palette."
    ),
    "environmental": (
        "A pitch-black silhouette of a vast dark formation against a warm "
        "glowing haze (#e3ae86), backlit, its whole mass a flat featureless "
        "cut-out filling the frame. Not a creature and not a person: "
        "{form}. {attributes}The formation coils on itself in a slow "
        "spiral, the same heavy ridged structure nested ring inside ring, "
        "each turn larger than the last, winding toward an unlit core. "
        "Analog film studio photograph, warm near-black palette."
    ),
}
