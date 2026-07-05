"""The full submission pipeline, shared by the Streamlit app and test scripts.

Keeping this outside app.py means tests exercise EXACTLY the production code
path, and every run (manual or scripted) lands in Logfire the same way.
"""

import logfire

from curator import (
    build_edit_instruction,
    build_full_description,
    new_genome,
    rephrase_instruction,
    update_genome,
)
from generator import (
    DEFAULT_THEME,
    ContentFlaggedError,
    edit_image,
    edit_image_uncensored,
    generate_image,
)
from storage import (
    get_state,
    save_generation,
    save_submission,
    today,
    upsert_state,
)

# After this many chained Kontext edits, regenerate from the genome instead of
# editing again (iterative editing degrades quality after ~5 passes).
REANCHOR_EVERY = 4


def process_submission(sub: dict, theme: str = DEFAULT_THEME) -> tuple[dict, str]:
    """Fold a submission into today's monster and return (saved row, kind).

    kind is one of: "initial", "edit", "reanchor", "absorbed".
    """
    with logfire.span("process submission", submission=sub,
                      selected_theme=theme) as span:
        saved, kind = _process_submission(sub, theme)
        span.set_attribute("kind", kind)
        span.set_attribute("result_image_url", saved.get("image_url"))
        return saved, kind


def _process_submission(sub: dict, theme: str) -> tuple[dict, str]:
    save_submission(sub)

    state = get_state()
    iteration = (state.get("iteration") or 1) if state else 1

    if state is None or not state.get("image_url"):
        # First contribution of the day (or after a reset) births the monster.
        genome = state["genome"] if state and state.get("genome") else new_genome()
        genome = update_genome(genome, sub)
        genome["theme"] = theme
        description = build_full_description(genome)
        url = generate_image(description, theme=theme)
        saved = save_generation(description, url, day=today(),
                                version=1, kind="initial", iteration=iteration)
        upsert_state(genome, saved["image_url"], 1, 0, iteration=iteration)
        return saved, "initial"

    genome = update_genome(state["genome"], sub)
    version = state["version"] + 1
    # Theme the current image actually has; edits must defend that one.
    current_theme = genome.get("theme", "dark")

    if state["edits_since_anchor"] >= REANCHOR_EVERY:
        # Re-anchor: fresh generation from the whole genome to undo edit
        # drift. This is also where a toggled theme takes effect.
        genome["theme"] = theme
        description = build_full_description(genome)
        url = generate_image(description, theme=theme)
        saved = save_generation(description, url, day=today(),
                                version=version, kind="reanchor",
                                iteration=iteration)
        upsert_state(genome, saved["image_url"], version, 0,
                     iteration=iteration)
        return saved, "reanchor"

    # The curator SEES the current image, so its instruction only references
    # anatomy that actually exists.
    instruction = build_edit_instruction(genome, sub,
                                         image_url=state["image_url"])
    url = None
    try:
        url = edit_image(state["image_url"], instruction, theme=current_theme)
    except ContentFlaggedError:
        # flux-pro's server-side moderation censored the edit (deterministic
        # false positives on phrasings like "fractures across the neck").
        # Rescue chain: rephrase + retry pro, then the uncensorable open
        # model, and only then give up on changing the image.
        rephrased = rephrase_instruction(instruction)
        if rephrased:
            try:
                url = edit_image(state["image_url"], rephrased,
                                 theme=current_theme)
                instruction = rephrased
            except ContentFlaggedError:
                pass
        if url is None:
            try:
                url = edit_image_uncensored(state["image_url"], instruction,
                                            theme=current_theme)
            except Exception:
                pass
    if url is None:
        # Nothing produced an image. The visitor's contribution still lives
        # in the genome and will surface in the next re-anchor regeneration.
        upsert_state(genome, state["image_url"], state["version"],
                     state["edits_since_anchor"], iteration=iteration)
        return state, "absorbed"
    saved = save_generation(instruction, url, day=today(),
                            version=version, kind="edit", iteration=iteration)
    upsert_state(genome, saved["image_url"], version,
                 state["edits_since_anchor"] + 1, iteration=iteration)
    return saved, "edit"
