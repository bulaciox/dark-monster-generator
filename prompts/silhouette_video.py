"""Prompt for the monster screen's occasional "breathing" animation: subtle
ambient motion generated once from the silhouette image, never a redesign of
the figure. See generator.generate_silhouette_video.

Written generically since it has to work across every silhouette -- and not
just different materials, but different KINDS OF FORM: roughly two thirds of
monsters are a standing human figure, but a third are "environmental" (see
generator.FIGURE_TEMPLATES) -- a billowing mass of smoke, a fibrous tangle, a
shapeless swelling thing, with no chest, shoulders, limbs or any humanoid
structure at all. An earlier version of this prompt described the motion as
the figure's "chest and shoulders" rising and falling, which is meaningless
for a mass of smoke filling a corridor. The wording below only ever refers to
"its form" / "its mass" / "its outer surface", which reads sensibly for a
standing figure and a shapeless one alike.

CRITICAL: the silhouette's dark, featureless shadow IS the installation's
anonymity mechanism (see prompts/system.py) -- a visitor must never be
identifiable, on this screen least of all. An earlier version of this prompt,
tested on a human silhouette, caused the model to "light up" the dark mass
into a fully visible, exposed body partway through the clip -- exactly the
opposite of what this screen exists to protect. Both prompts below now say so
explicitly and forbid it outright, and additionally cap brightness at the
level of the source image's own first frame (never brighter), since the
directed light-dimming motion below still needs a hard ceiling.

Also observed across a small test batch: the model tends to drift into a slow
zoom/reframe over the clip even when told to stay "static" once, and telling
it to just "stay static" reads as inert rather than alive. So the motion is
directed explicitly at two things any of these forms can plausibly do without
moving position -- pulse/settle, and have its light flicker/dim -- rather
than leaving "ambient motion" underspecified, while still spelling out
"no zoom, no dolly, no pan, no crop change" as its own explicit line.
"""

TEMPLATE = (
    "Subtle ambient motion that makes the shape feel alive, as if breathing: "
    "its outer form swells and settles very slightly and slowly, as though "
    "expanding and contracting with a breath, its mass shifts almost "
    "imperceptibly, loose or wispy elements at its edges drift faintly. At "
    "some point the dim light behind it may fade down and then rise back up "
    "again, as if flickering or breathing itself -- but it must never become "
    "brighter than it is in the very first frame, only dimmer and back. The "
    "camera does not move at all: no zoom in or out, no dolly, no pan, no "
    "tilt, no reframing -- the frame and the shape's size and position stay "
    "pixel-for-pixel identical from the first frame to the last. The shape "
    "MUST remain a solid, dark, featureless silhouette throughout the entire "
    "clip -- never lit up, never revealed, never showing skin, flesh, a face "
    "or any anatomical or structural detail. It stays opaque black shadow "
    "from first frame to last, at most as bright as the source image, never "
    "brighter."
)

# If the richer prompt above is flagged, fall back to the plainest possible
# request for the same idea -- still with the darkness and no-camera-move
# requirements, since those are the non-negotiable parts.
FALLBACK = (
    "Very subtle motion: the shape pulses and settles almost imperceptibly, "
    "as if breathing, and the dim light behind it may fade down and back up "
    "once, never brighter than the start. No camera movement of any kind: no "
    "zoom, no pan, no reframing, the shot stays exactly the same size and "
    "position throughout. The shape stays a solid dark silhouette at all "
    "times, never lit up or revealed, no visible skin or anatomy."
)
