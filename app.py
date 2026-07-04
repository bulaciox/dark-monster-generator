"""Streamlit app for the Street Monster installation (Golden Days CPH).

Presentation layer only: the genome logic lives in curator.py, image
generation/editing in generator.py and persistence in storage.py.
Run with: uv run streamlit run app.py
"""

import streamlit as st

from curator import (
    ABILITY_GROUPS,
    EMOTION_MAP,
    HAPPENED_EFFECTS,
    IMPORTANCE_MULT,
    build_edit_instruction,
    build_full_description,
    genome_summary,
    new_genome,
    update_genome,
)
from generator import ContentFlaggedError, edit_image, generate_image
from storage import (
    get_state,
    list_generations,
    list_submissions,
    reset_day,
    save_generation,
    save_submission,
    today,
    upsert_state,
)

# After this many chained Kontext edits, regenerate from the genome instead of
# editing again (iterative editing degrades quality after ~5 passes).
REANCHOR_EVERY = 4

EMOTIONS = list(EMOTION_MAP.keys())
BODY_PARTS = ["Eyes", "Mouth", "Teeth", "Tongue", "Ears", "Face", "Hair",
              "Neck", "Shoulders", "Arms", "Hands", "Fingers", "Chest",
              "Heart", "Stomach", "Back", "Legs", "Feet", "Skin", "Bones",
              "Blood", "Brain", "Genitals"]
ABILITIES = [a for group in ABILITY_GROUPS.values() for a in sorted(group)]
MONSTER_TYPES = ["A real person", "A group of people",
                 "An institution or system", "A situation in my life",
                 "A memory from the past", "A fear or anxiety",
                 "A part of myself", "Something supernatural or imaginary"]
SOCIAL_FORCES = ["Family", "School", "Work", "Religion", "Politics",
                 "Gender expectations", "Social class", "Race or ethnicity",
                 "Social media"]
SIZES = ["Tiny (fits in a pocket)", "Child-sized", "Human-sized",
         "Larger than a person", "House-sized", "City-sized",
         "Impossible to measure"]
SHAPES = ["Human", "Animal", "Human-animal hybrid", "Machine", "Shadow",
          "Changes shape", "Object", "Impossible to describe"]
SCALE = {"Very weak": 1, "Weak": 2, "Moderate": 3, "Strong": 4,
         "Overwhelming": 5}

st.markdown("""
<style>
.block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

st.title("Street Monster")

page = st.sidebar.pills("Navigation",
                        ["Contribute", "Monster", "Gallery", "Data"],
                        default="Contribute")


def process_submission(sub: dict) -> tuple[dict, str]:
    """Fold a submission into today's monster and return (saved row, kind)."""
    save_submission(sub)

    state = get_state()
    iteration = (state.get("iteration") or 1) if state else 1

    if state is None or not state.get("image_url"):
        # First contribution of the day (or after a reset) births the monster.
        genome = state["genome"] if state and state.get("genome") else new_genome()
        genome = update_genome(genome, sub)
        description = build_full_description(genome)
        url = generate_image(description)
        saved = save_generation(description, url, day=today(),
                                version=1, kind="initial", iteration=iteration)
        upsert_state(genome, saved["image_url"], 1, 0, iteration=iteration)
        return saved, "initial"

    genome = update_genome(state["genome"], sub)
    version = state["version"] + 1

    if state["edits_since_anchor"] >= REANCHOR_EVERY:
        # Re-anchor: fresh generation from the whole genome to undo edit drift.
        description = build_full_description(genome)
        url = generate_image(description)
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
    try:
        url = edit_image(state["image_url"], instruction)
    except ContentFlaggedError:
        # The safety filter blocked this transformation. Don't lose the
        # visitor's contribution: it stays in the genome and will surface
        # in the next re-anchor regeneration.
        upsert_state(genome, state["image_url"], state["version"],
                     state["edits_since_anchor"], iteration=iteration)
        return state, "absorbed"
    saved = save_generation(instruction, url, day=today(),
                            version=version, kind="edit", iteration=iteration)
    upsert_state(genome, saved["image_url"], version,
                 state["edits_since_anchor"] + 1, iteration=iteration)
    return saved, "edit"


if page == "Contribute":
    st.caption("Think of a person, force, experience, fear, memory, "
               "institution or situation in your life that feels monstrous. "
               "Your answers will merge with everyone else's into today's "
               "collective Street Monster.")

    with st.form("questionnaire"):
        st.subheader("1 · Identifying the monster")
        monster_what = st.text_input("What is your monster? (one sentence)")
        monster_role = st.text_input("What role does it play in your life?")
        power = st.pills("How powerful is it today?",
                         list(SCALE.keys()), default="Moderate")
        commonality = st.pills(
            "How common is this monster in society?",
            ["Only affects me", "Affects a few people",
             "Affects many people", "Affects most people",
             "Affects almost everyone"], default="Affects many people")
        control = st.pills(
            "How much control do you have over it?",
            ["None", "Very little", "Some", "A lot", "Complete control"],
            default="Some")
        emotions = st.pills("Which emotions do you associate with it? "
                            "(up to 3)", EMOTIONS, selection_mode="multi")
        if len(emotions) > 3:
            st.caption(":orange[Only the first 3 will be used.]")

        st.subheader("2 · Real or imagined")
        monster_type = st.pills("What kind of monster is this?",
                                MONSTER_TYPES)
        social_force = st.pills("What social force most shaped it?",
                                SOCIAL_FORCES)

        st.subheader("3 · Embodied monster")
        body_part = st.pills("Which body part do you associate with it?",
                             BODY_PARTS)
        body_part_happened = st.pills(
            "What has happened to this body part?",
            list(HAPPENED_EFFECTS.keys()))
        body_part_importance = st.pills(
            "How important is this body part to the monster?",
            list(IMPORTANCE_MULT.keys()),
            default="It is one important feature")
        body_part_why = st.text_input(
            "Why this body part? (one sentence)")

        st.subheader("4 · Faculties and abilities")
        abilities = st.pills("Select up to 5 abilities", ABILITIES,
                             selection_mode="multi")
        if len(abilities) > 5:
            st.caption(":orange[Only the first 5 will be used.]")
        dangerous_ability = st.text_input(
            "Which ability makes it most dangerous?")

        st.subheader("5 · Physical description")
        size = st.pills("How large is it?", SIZES)
        shape = st.pills("What shape best describes it?", SHAPES)
        materials = st.text_input(
            "What is its body made of? (three words)")
        movement = st.text_input("How does it move? (a few words)")
        frightening_feature = st.text_input(
            "What physical feature makes it frightening?")
        artist_description = st.text_area(
            "Describe your monster as if an artist had to draw it "
            "(3-5 sentences)")

        consent = st.checkbox(
            "I understand my anonymous answers may be used to generate and "
            "continuously update the collective Street Monster.")

        submitted = st.form_submit_button("Feed the monster",
                                          use_container_width=True)

    if submitted:
        if not consent:
            st.warning("Please accept the consent checkbox first.")
        elif not (monster_what.strip() or emotions or body_part):
            st.warning("Tell us at least what your monster is, an emotion "
                       "or a body part.")
        else:
            sub = {
                "monster_what": monster_what,
                "monster_role": monster_role,
                "power": SCALE[power],
                "commonality": ["Only affects me", "Affects a few people",
                                "Affects many people", "Affects most people",
                                "Affects almost everyone"].index(commonality) + 1,
                "control": ["None", "Very little", "Some", "A lot",
                            "Complete control"].index(control) + 1,
                "emotions": emotions[:3],
                "monster_type": monster_type,
                "social_force": social_force,
                "body_part": body_part,
                "body_part_happened": body_part_happened,
                "body_part_importance": body_part_importance,
                "body_part_why": body_part_why,
                "abilities": abilities[:5],
                "dangerous_ability": dangerous_ability,
                "size": size,
                "shape": shape,
                "materials": materials,
                "movement": movement,
                "frightening_feature": frightening_feature,
                "artist_description": artist_description,
            }
            try:
                previous = get_state()
                with st.spinner("The monster is absorbing your answers..."):
                    saved, kind = process_submission(sub)
                if kind == "initial":
                    st.success("Your contribution gave birth to today's monster.")
                    st.image(saved["image_url"])
                elif kind == "absorbed":
                    st.info("The monster absorbed your answers, but resisted "
                            "changing its body this time. Your contribution "
                            "will surface in its next rebirth.")
                    st.image(saved["image_url"])
                else:
                    st.success("The monster has changed because of you "
                               f"({'fresh regeneration' if kind == 'reanchor' else 'transformation'}).")
                    col_before, col_after = st.columns(2)
                    with col_before:
                        st.caption("Before")
                        st.image(previous["image_url"])
                    with col_after:
                        st.caption("After")
                        st.image(saved["image_url"])
            except (ValueError, ContentFlaggedError) as e:
                st.warning(str(e))
            except Exception as e:
                st.error(f"Something went wrong: {e}")

elif page == "Monster":
    state = get_state()
    if not state or not state.get("image_url"):
        st.info("Today's monster has not been born yet. "
                "Be the first to contribute.")
    else:
        st.image(state["image_url"])
        genome = state["genome"]
        iteration = state.get("iteration") or 1
        st.caption(f"Iteration {iteration} · Version {state['version']} · "
                   f"{genome.get('submission_count', 0)} contributions")
        versions = [g for g in list_generations(day=today())
                    if (g.get("iteration") or 1) == iteration]
        if len(versions) > 1:
            st.subheader("Evolution")
            cols = st.columns(4)
            for i, item in enumerate(versions):
                with cols[i % 4]:
                    st.image(item["image_url"],
                             caption=f"v{item.get('version') or '?'} · "
                                     f"{item.get('kind', '')}")

elif page == "Gallery":
    generations = list_generations()
    if not generations:
        st.info("No monsters yet.")
    else:
        groups: dict[tuple, list[dict]] = {}
        for item in generations:
            key = (item.get("day") or "unknown", item.get("iteration") or 1)
            groups.setdefault(key, []).append(item)
        for (day, iteration), items in groups.items():
            st.subheader(f"{day} · Iteration {iteration}")
            st.image(items[0]["image_url"],
                     caption=f"Final form · {len(items)} versions")
            with st.expander(f"All {len(items)} versions"):
                cols = st.columns(4)
                for i, item in enumerate(items):
                    with cols[i % 4]:
                        st.image(item["image_url"],
                                 caption=f"v{item.get('version') or '?'} · "
                                         f"{item.get('kind', '')}")

elif page == "Data":
    st.caption("Analysis view: raw visitor inputs and the collective genome, "
               "for testing and curation.")

    state = get_state()
    st.subheader("Today's genome")
    if not state:
        st.info("No state for today yet.")
    else:
        genome = state.get("genome") or {}
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Iteration", state.get("iteration") or 1)
        col2.metric("Version", state.get("version") or 0)
        col3.metric("Submissions", genome.get("submission_count", 0))
        col4.metric("Edits since anchor", state.get("edits_since_anchor") or 0)
        if genome:
            st.text(genome_summary(genome))
            with st.expander("Raw genome (JSON)"):
                st.json(genome)

    st.subheader("Submissions today")
    submissions = list_submissions(day=today())
    if not submissions:
        st.info("No submissions today yet.")
    else:
        rows = []
        for s in submissions:
            data = s.get("data") or {}
            flat = {"time": (s.get("created_at") or "")[11:19]}
            for key, value in data.items():
                flat[key] = (", ".join(value) if isinstance(value, list)
                             else value)
            rows.append(flat)
        st.dataframe(rows, use_container_width=True)
        with st.expander("Raw submissions (JSON)"):
            st.json(submissions)

    st.subheader("Reset day")
    st.warning("This archives the current monster as "
               f"Iteration {(state.get('iteration') or 1) if state else 1} "
               "and starts a fresh one with the next contribution. "
               "Past versions stay in the Gallery.")
    if "reset_done" in st.session_state:
        st.success(f"Done. Next contribution will birth Iteration "
                   f"{st.session_state.pop('reset_done')}.")
    confirm = st.checkbox("I understand: start a new iteration for today")
    if st.button("Reset today's monster", disabled=not confirm):
        st.session_state["reset_done"] = reset_day()
        st.rerun()
