"""The submission pipeline, shared by the API and test scripts.

Keeping this outside the API layer means tests exercise EXACTLY the production
code path, and every run (manual or scripted) lands in Logfire the same way.

Two flows live here:

- process_submission: the current one. One visitor's answers become THEIR OWN
  monster, expressed as four outputs (organ, silhouette, story, title) which
  the installation shows across separate screens. The governing rule from the
  directors' brief is that free text determines IDENTITY while the selected
  emotions determine EXPRESSION -- so the free-text answers are transposed into
  a visual identity (never naming a real person, place or event) and the
  emotions decide which body parts deform and how far.

- process_submission_collective: the earlier flow, where a single monster
  evolved all day by chained image edits. Kept for reference, unused.
"""

import concurrent.futures as futures

import logfire

from curator import (
    build_edit_plan,
    build_full_description,
    build_story_and_title,
    extract_identity,
    new_genome,
    rephrase_instruction,
    select_organs,
    update_genome,
)
from generator import (
    DEFAULT_THEME,
    ContentFlaggedError,
    edit_image,
    edit_image_kontext,
    edit_image_uncensored,
    fill_region,
    generate_image,
    generate_organ,
    generate_silhouette,
    match_palette,
    refresh_image,
    segment_region,
)
from storage import (
    get_state,
    save_generation,
    save_monster,
    save_submission,
    store_image,
    today,
    upsert_state,
)

# After this many chained Kontext edits, refresh the image (img2img reanchor)
# to undo the sharpness loss of iterative editing. Refreshes preserve the
# creature's identity, so they can be frequent. Collective flow only.
REANCHOR_EVERY = 3


def process_submission(sub: dict, theme: str | None = None) -> tuple[dict, str]:
    """Turn one visitor's answers into their monster and return (row, kind).

    kind is "monster" when at least one image was generated, "text" when both
    image calls failed and only the written outputs survived.

    theme is accepted and ignored: individual monsters have one fixed look.
    """
    with logfire.span("process submission", submission=sub) as span:
        monster, kind = _process_submission(sub)
        span.set_attribute("kind", kind)
        span.set_attribute("monster_id", monster.get("id"))
        span.set_attribute("number", monster.get("number"))
        return monster, kind


def _process_submission(sub: dict) -> tuple[dict, str]:
    submission = save_submission(sub)

    # Both are cheap, and together they feed the three generation calls below.
    identity = extract_identity(sub)
    organs = select_organs(sub)

    # The three outputs are independent, so the visitor waits for the slowest
    # one rather than for their sum.
    with futures.ThreadPoolExecutor(max_workers=3) as pool:
        organ_job = pool.submit(_organ_image, organs)
        silhouette_job = pool.submit(_silhouette_image, identity, organs)
        text_job = pool.submit(_story_and_title, sub, identity)

        organ_url = organ_job.result()
        silhouette_url = silhouette_job.result()
        text = text_job.result()

    monster = save_monster(
        identity=identity,
        organs=organs,
        story=text["story"],
        title=text["title"],
        organ_image_url=organ_url,
        silhouette_image_url=silhouette_url,
        submission_id=submission.get("id"),
    )
    return monster, ("monster" if (organ_url or silhouette_url) else "text")


# Each branch swallows its own failures: one output going missing must not cost
# the visitor the other three. Image calls get one retry, because fal.ai fails
# occasionally under concurrency and a lost image costs a whole screen.

def _retry(call, what: str):
    for attempt in (1, 2):
        try:
            return call()
        except Exception as exc:
            logfire.warn(f"{what} failed", error=str(exc), attempt=attempt)
    return None


def _organ_image(organs: list[dict]) -> str | None:
    if not organs:
        return None
    organ = organs[0]
    return _retry(
        lambda: store_image(generate_organ(organ["part"],
                                           organ["transformation"])),
        "organ generation")


def _silhouette_image(identity: dict, organs: list[dict]) -> str | None:
    return _retry(lambda: store_image(generate_silhouette(identity, organs)),
                  "silhouette generation")


def _story_and_title(sub: dict, identity: dict) -> dict:
    if not sub.get("encountered", True):
        return {"story": "", "title": ""}
    # An empty reply is a silent failure rather than an exception (the LLM
    # answered with something unparseable), and it costs the visitor two of
    # their four outputs, so it is worth one more attempt.
    for attempt in (1, 2):
        try:
            text = build_story_and_title(sub, identity)
            if text["story"] and text["title"]:
                return text
            logfire.warn("story generation empty", attempt=attempt)
        except Exception as exc:
            logfire.warn("story generation failed", error=str(exc),
                         attempt=attempt)
    return {"story": "", "title": ""}


# ---------------------------------------------------------------------------
# The earlier collective flow: one monster per day, evolved by chained edits.
# Unused while the installation runs on individual monsters.
# ---------------------------------------------------------------------------

def process_submission_collective(sub: dict, theme: str = DEFAULT_THEME) -> tuple[dict, str]:
    """Fold a submission into today's shared monster and return (saved, kind).

    The original collective flow, kept for reference while the installation
    moves to individual monsters (see process_submission below). Unused.

    kind is one of: "initial", "edit", "reanchor", "absorbed".
    """
    with logfire.span("process submission (collective)", submission=sub,
                      selected_theme=theme) as span:
        saved, kind = _process_submission_collective(sub, theme)
        span.set_attribute("kind", kind)
        span.set_attribute("result_image_url", saved.get("image_url"))
        return saved, kind


def _process_submission_collective(sub: dict, theme: str) -> tuple[dict, str]:
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
    current_theme = genome.get("theme", DEFAULT_THEME)

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

    # Primary path: Qwen Image Edit 2511. Fast (~5s), no prompt-level
    # censorship, and it preserves everything it was not asked to change,
    # so it needs neither masks nor palette correction.
    try:
        url = edit_image(state["image_url"], instruction, theme=current_theme)
        edit_path = "qwen"
    except Exception:
        url = None

    if url is None and plan["type"] == "local":
        # Fallback A: surgical inpainting inside a segmented mask.
        try:
            mask_url = segment_region(state["image_url"], plan["region"])
            url = fill_region(state["image_url"], mask_url, instruction,
                              theme=current_theme)
            edit_path = "fill"
            instruction = f"[{plan['region']}] {instruction}"
        except Exception:
            url = None

    if url is None:
        # Fallback B: Kontext chain with the censorship rescue
        # (pro -> rephrase + retry pro -> uncensorable dev).
        try:
            url = edit_image_kontext(state["image_url"], instruction,
                                     theme=current_theme)
            edit_path = "kontext"
        except ContentFlaggedError:
            rephrased = rephrase_instruction(instruction)
            if rephrased:
                try:
                    url = edit_image_kontext(state["image_url"], rephrased,
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
