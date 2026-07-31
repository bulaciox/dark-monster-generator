"""The full submission pipeline, shared by the Streamlit app and test scripts.

Keeping this outside app.py means tests exercise EXACTLY the production code
path, and every run (manual or scripted) lands in Logfire the same way.
"""

import logfire

from curator import (
    build_edit_plan,
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
    fill_region,
    generate_image,
    match_palette,
    refresh_image,
    segment_region,
)
from storage import (
    get_state,
    save_generation,
    save_submission,
    today,
    upsert_state,
)

# After this many chained Kontext edits, refresh the image (img2img reanchor)
# to undo the sharpness loss of iterative editing. Refreshes preserve the
# creature's identity, so they can be frequent.
REANCHOR_EVERY = 3


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
        # Re-anchor: img2img refresh of the CURRENT image with the genome
        # description. Repaints fine detail (undoing edit drift) while
        # keeping the creature recognisable. The image keeps its own theme;
        # a toggled theme only applies at the next true rebirth.
        description = build_full_description(genome)
        url = refresh_image(state["image_url"], description,
                            theme=current_theme)
        saved = save_generation(description, url, day=today(),
                                version=version, kind="reanchor",
                                iteration=iteration)
        upsert_state(genome, saved["image_url"], version, 0,
                     iteration=iteration)
        return saved, "reanchor"

    # The curator SEES the current image and classifies the change:
    # "local" (transform one existing region -> surgical SAM+Fill, zero
    # drift outside the mask) or "structural" (new structures / whole-body
    # -> Kontext chain).
    plan = build_edit_plan(genome, sub, image_url=state["image_url"])
    instruction = plan["instruction"]
    url = None
    edit_path = None

    if plan["type"] == "local":
        try:
            mask_url = segment_region(state["image_url"], plan["region"])
            url = fill_region(state["image_url"], mask_url, instruction,
                              theme=current_theme)
            edit_path = "fill"
            instruction = f"[{plan['region']}] {instruction}"
        except Exception:
            # Region not found / too broad / fill flagged: fall through to
            # the Kontext chain with the same instruction.
            url = None

    if url is None:
        # Structural plan, or the local path failed. Kontext chain with the
        # censorship rescue: pro -> rephrase + retry pro -> uncensorable dev.
        try:
            url = edit_image(state["image_url"], instruction,
                             theme=current_theme)
            edit_path = "kontext"
        except ContentFlaggedError:
            rephrased = rephrase_instruction(instruction)
            if rephrased:
                try:
                    url = edit_image(state["image_url"], rephrased,
                                     theme=current_theme)
                    instruction = rephrased
                    edit_path = "kontext"
                except ContentFlaggedError:
                    pass
            if url is None:
                try:
                    url = edit_image_uncensored(state["image_url"],
                                                instruction,
                                                theme=current_theme)
                    edit_path = "kontext"
                except Exception:
                    pass

    if url is None:
        # Nothing produced an image. The visitor's contribution still lives
        # in the genome and will surface in the next re-anchor regeneration.
        upsert_state(genome, state["image_url"], state["version"],
                     state["edits_since_anchor"], iteration=iteration)
        return state, "absorbed"

    if edit_path == "kontext":
        # Kontext repaints the whole frame and drifts the global palette;
        # pull the color statistics back toward the pre-edit image (partial
        # blend, so intentional accents survive).
        url = match_palette(url, state["image_url"])

    saved = save_generation(instruction, url, day=today(),
                            version=version, kind="edit", iteration=iteration)
    # Only Kontext edits degrade the whole frame; surgical fills never touch
    # pixels outside the mask, so they don't count toward the re-anchor.
    edits_increment = 1 if edit_path == "kontext" else 0
    upsert_state(genome, saved["image_url"], version,
                 state["edits_since_anchor"] + edits_increment,
                 iteration=iteration)
    return saved, "edit"
