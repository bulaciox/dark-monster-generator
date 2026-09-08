"""Image prompt for the monster screen: a full figure with its organ(s)
burning inside it. See generator.generate_silhouette.
"""

from prompts.organ import anatomical

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

TEMPLATE = (
    "{figure} "
    "{attributes}"
    "Deep inside it, {organs} — luminous deep red, burning through the "
    "darkness as the only clear element in the image. "
    "Analog film photograph, heavy grain, near-black palette with a single red "
    "accent, cold and documentary. No text, no lettering, no faces in focus."
)


def organ_phrase(organs: list[dict]) -> str:
    """The organs as they should read inside the silhouette."""
    if not organs:
        return "a single anatomical form"
    pieces = [f"{anatomical(o['part'])}, {o['transformation']}"
              for o in organs]
    return " and ".join(pieces)
