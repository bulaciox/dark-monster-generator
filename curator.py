"""Curator: turns questionnaire submissions into the monster's evolving genome.

The genome is a plain dict (stored as jsonb in Supabase) that accumulates every
submission of the day statistically, following the emotion->anatomy lookup
table and body-part weights designed by Rika, and the abilities->visual-effect
table designed by Kim. From the genome the curator produces either:

- an EDIT INSTRUCTION for FLUX Kontext (transform the current image), or
- a FULL DESCRIPTION to regenerate the monster from scratch (re-anchor),
  which is needed periodically because iterative editing degrades quality.

Free-text answers are translated into the project's visual vocabulary by an
LLM (Claude via fal.ai's OpenRouter router, same FAL_KEY). Every LLM call has
a deterministic fallback so the installation keeps working if the call fails.
"""

import fal_client
import logfire
from dotenv import load_dotenv

load_dotenv()

LLM_ENDPOINT = "openrouter/router/openai/v1/responses"
LLM_MODEL = "anthropic/claude-sonnet-4.5"

# ---------------------------------------------------------------------------
# Rika's master emotional-anatomical lookup table
# emotion -> (primary part, secondary part, zone, visual transformation)
# ---------------------------------------------------------------------------
EMOTION_MAP = {
    "Fear": ("Eyes", "Neck", "Head Zone", "enlarged pupils, heightened alertness"),
    "Anxiety": ("Stomach", "Fingers", "Torso Zone", "twisting, trembling, knotting"),
    "Panic": ("Chest", "Lungs", "Torso Zone", "expansion, fragmentation"),
    "Shame": ("Face", "Genitals", "Identity Zone", "concealment, covering, distortion"),
    "Embarrassment": ("Ears", "Cheeks", "Head Zone", "swelling, redness"),
    "Guilt": ("Hands", "Shoulders", "Upper Body Zone", "burden, weight, staining"),
    "Regret": ("Back", "Spine", "Structural Zone", "bending, ageing, scars"),
    "Grief": ("Heart", "Chest", "Heart Zone", "cracks, hollow spaces"),
    "Sadness": ("Eyes", "Mouth", "Head Zone", "drooping structures"),
    "Loneliness": ("Rib Cage", "Arms", "Heart Zone", "emptiness, separation"),
    "Rejection": ("Skin", "Heart", "Identity Zone", "fragmentation, scars"),
    "Insecurity": ("Genitals", "Stomach", "Identity Zone", "reduction, instability"),
    "Vulnerability": ("Genitals", "Skin", "Identity Zone", "exposure, transparency"),
    "Hopelessness": ("Legs", "Spine", "Structural Zone", "collapse, erosion"),
    "Powerlessness": ("Arms", "Hands", "Upper Body Zone", "shrinking, weakening"),
    "Anger": ("Teeth", "Jaw", "Head Zone", "sharpening, enlargement"),
    "Rage": ("Mouth", "Eyes", "Head Zone", "tearing, eruption"),
    "Resentment": ("Liver", "Stomach", "Internal Organ Zone", "darkening, accumulation"),
    "Frustration": ("Fists", "Arms", "Upper Body Zone", "compression, tension"),
    "Jealousy": ("Eyes", "Fingers", "Head Zone", "multiplication, fixation"),
    "Envy": ("Eyes", "Mouth", "Head Zone", "consuming structures"),
    "Bitterness": ("Tongue", "Teeth", "Head Zone", "corrosion, roughness"),
    "Contempt": ("Nose", "Mouth", "Head Zone", "asymmetry, elevation"),
    "Desire": ("Pelvis", "Hands", "Pelvic Zone", "attraction, reaching forms"),
    "Lust": ("Genitals", "Mouth", "Pelvic Zone", "expansion, warmth"),
    "Attraction": ("Eyes", "Face", "Head Zone", "symmetry, glow"),
    "Passion": ("Heart", "Genitals", "Heart / Pelvic Zone", "branching growth, intensity"),
    "Obsession": ("Brain", "Eyes", "Mind Zone", "repetition, multiplication"),
    "Longing": ("Hands", "Chest", "Heart Zone", "stretching, reaching"),
    "Love": ("Heart", "Genitals", "Heart / Pelvic Zone", "connection, organic growth"),
    "Compassion": ("Hands", "Heart", "Heart Zone", "supportive structures"),
    "Empathy": ("Ears", "Heart", "Heart Zone", "sensory expansion"),
    "Affection": ("Arms", "Chest", "Heart Zone", "embracing forms"),
    "Devotion": ("Spine", "Heart", "Structural Zone", "rooting, strengthening"),
    "Pride": ("Chest", "Neck", "Upper Body Zone", "elevation, enlargement"),
    "Confidence": ("Pelvis", "Chest", "Structural Zone", "symmetry, stability"),
    "Ambition": ("Legs", "Eyes", "Structural Zone", "forward growth"),
    "Curiosity": ("Eyes", "Fingers", "Mind Zone", "branching sensory organs"),
    "Wonder": ("Eyes", "Brain", "Mind Zone", "luminescence, multiplication"),
    "Hope": ("Lungs", "Heart", "Heart Zone", "opening structures"),
    "Joy": ("Mouth", "Eyes", "Head Zone", "radiance, flowering"),
    "Relief": ("Shoulders", "Chest", "Upper Body Zone", "release, softening"),
    "Confusion": ("Brain", "Eyes", "Mind Zone", "duplication, inversion"),
    "Doubt": ("Brain", "Feet", "Mind Zone", "instability"),
    "Uncertainty": ("Feet", "Legs", "Structural Zone", "branching paths"),
    "Alienation": ("Skin", "Eyes", "Identity Zone", "separation, gaps"),
    "Disgust": ("Nose", "Stomach", "Internal Organ Zone", "extrusion, rejection"),
    "Awe": ("Eyes", "Heart", "Mind / Heart Zone", "expansion, celestial growth"),
    "Surprise": ("Eyebrows", "Mouth", "Head Zone", "sudden enlargement"),
}

# Rika's body-part weight scores (default 1.0 for anything not listed).
BODY_WEIGHTS = {
    "Eyes": 1.0,
    "Heart": 1.2,
    "Brain": 1.1,
    "Hands": 0.8,
    "Genitals": 1.3,
    "Skin": 1.4,
}

# ---------------------------------------------------------------------------
# Kim's abilities -> anatomical visual effect table
# ---------------------------------------------------------------------------
ABILITY_EFFECTS = {
    "intellect": "enlarged brain, eyes and exposed nervous system",
    "memory": "additional eyes, layered skin, archive-like growths",
    "manipulation": "extended fingers, tentacles, extra mouths",
    "strength": "enlarged muscles, bones and shoulders",
    "speed": "elongated limbs, multiple legs",
    "fear": "eyes, teeth and shadow structures",
    "desire": "pelvic structures, hands and mouths",
    "social": "multiple faces, mouths and ears",
    "digital": "screens, cables, data-like growths",
    "adaptation": "constant mutation, asymmetry",
    "invisibility": "transparency, fragmented outlines",
    "dream": "floating anatomy, impossible forms",
    "sensory": "multiplied sensory organs, ears and eyes",
}

ABILITY_GROUPS = {
    "intellect": {"Highly intelligent", "Strategic", "Creative", "Curious", "Wise",
                  "Cunning", "Predicts what people will do", "Learns quickly"},
    "memory": {"Remembers everything", "Controls memories", "Returns when forgotten"},
    "manipulation": {"Manipulative", "Creates confusion", "Creates conflict",
                     "Creates dependency", "Creates obsession", "Manipulates images",
                     "Manipulates information", "Controls emotions"},
    "strength": {"Strong", "Enduring", "Difficult to stop", "Resistant to injury",
                 "Large", "Never dies"},
    "speed": {"Fast", "Agile", "Flexible", "Small and elusive", "Able to climb",
              "Able to fly", "Able to swim", "Spreads rapidly", "Never sleeps"},
    "fear": {"Feeds on fear", "Feeds on shame", "Feeds on anger", "Inspires fear",
             "Feeds on loneliness"},
    "desire": {"Feeds on desire", "Feeds on attention", "Seductive"},
    "social": {"Persuasive", "Charismatic", "Influential", "Commands attention",
               "Inspires loyalty", "Blends into crowds", "Controls groups",
               "Exists within institutions", "Exists within families",
               "Exists within communities"},
    "digital": {"Watches people", "Tracks information", "Exists online",
                "Influences algorithms"},
    "adaptation": {"Changes shape", "Changes with time", "Changes with society",
                   "Adapts to new situations", "Grows when ignored",
                   "Grows when confronted", "Hides in ordinary things",
                   "Hides inside people", "Alters reality",
                   "Exists in many places at once"},
    "invisibility": {"Becomes invisible", "Moves through walls", "Difficult to notice"},
    "dream": {"Appears in dreams", "Reads minds"},
    "sensory": {"Sees everything", "Hears everything", "Smells danger",
                "Detects weakness", "Detects lies", "Detects desire",
                "Detects fear", "Detects vulnerability"},
}

# What the questionnaire's "what happened to this body part" answers mean
# visually, so both the deterministic builder and the LLM speak one language.
HAPPENED_EFFECTS = {
    "Enlarged": "grown disproportionately large",
    "Reduced": "shrunken and atrophied",
    "Hidden": "concealed behind translucent membranes",
    "Missing": "absent, leaving a hollow void",
    "Wounded": "freshly wounded, with visible damage",
    "Scarred": "covered in old scar tissue",
    "Mutated": "mutated into an unnatural form",
    "Mechanical": "replaced by mechanical, cybernetic parts",
    "Animal-like": "transformed into something animal-like",
    "Constantly changing": "unstable and constantly shifting",
}

IMPORTANCE_MULT = {
    "It defines the monster": 2.0,
    "It is one important feature": 1.2,
    "It is only a small detail": 0.5,
}

# Kept small on purpose: how many recent free-text fragments the genome
# remembers for the LLM to draw from.
MAX_RECENT_PHRASES = 20


def _ability_effect(ability: str) -> str | None:
    for group, members in ABILITY_GROUPS.items():
        if ability in members:
            return ABILITY_EFFECTS[group]
    return None


def new_genome() -> dict:
    return {
        "submission_count": 0,
        "emotion_counts": {},
        "region_scores": {},
        "region_effects": {},   # region -> {effect phrase: count}
        "ability_counts": {},
        "ability_effects": {},  # effect phrase -> count
        "type_counts": {},
        "social_force_counts": {},
        "shape_counts": {},
        "size_counts": {},
        "scales": {"power": 0.0, "commonality": 0.0, "control": 0.0},
        "recent_phrases": [],
    }


def _bump(counter: dict, key: str, amount: float = 1) -> None:
    if key:
        counter[key] = counter.get(key, 0) + amount


def _add_effect(genome: dict, region: str, effect: str, amount: float) -> None:
    effects = genome["region_effects"].setdefault(region, {})
    effects[effect] = effects.get(effect, 0) + amount


def update_genome(genome: dict, sub: dict) -> dict:
    """Fold one submission into the genome (statistically, Rika-style)."""
    n = genome["submission_count"]
    genome["submission_count"] = n + 1

    # Power modulates how hard this submission pushes the anatomy (0.7..1.5).
    power = sub.get("power", 3)
    intensity = 0.5 + power / 5.0

    for emotion in sub.get("emotions", []):
        if emotion not in EMOTION_MAP:
            continue
        primary, secondary, _zone, transformation = EMOTION_MAP[emotion]
        _bump(genome["emotion_counts"], emotion)
        _bump(genome["region_scores"], primary,
              BODY_WEIGHTS.get(primary, 1.0) * intensity)
        _bump(genome["region_scores"], secondary,
              0.5 * BODY_WEIGHTS.get(secondary, 1.0) * intensity)
        _add_effect(genome, primary, transformation, intensity)

    body_part = sub.get("body_part")
    if body_part:
        mult = IMPORTANCE_MULT.get(sub.get("body_part_importance", ""), 1.2)
        _bump(genome["region_scores"], body_part,
              BODY_WEIGHTS.get(body_part, 1.0) * mult * intensity)
        happened = HAPPENED_EFFECTS.get(sub.get("body_part_happened", ""))
        if happened:
            _add_effect(genome, body_part, happened, mult * intensity)

    for ability in sub.get("abilities", []):
        _bump(genome["ability_counts"], ability)
        effect = _ability_effect(ability)
        if effect:
            _bump(genome["ability_effects"], effect)

    _bump(genome["type_counts"], sub.get("monster_type", ""))
    _bump(genome["social_force_counts"], sub.get("social_force", ""))
    _bump(genome["shape_counts"], sub.get("shape", ""))
    _bump(genome["size_counts"], sub.get("size", ""))

    # Running averages for the 1-5 scales.
    for key in ("power", "commonality", "control"):
        value = sub.get(key)
        if value:
            prev = genome["scales"].get(key, 0.0)
            genome["scales"][key] = (prev * n + value) / (n + 1)

    for field in ("monster_what", "artist_description", "frightening_feature",
                  "materials", "movement"):
        text = (sub.get(field) or "").strip()
        if text:
            genome["recent_phrases"].append(text)
    genome["recent_phrases"] = genome["recent_phrases"][-MAX_RECENT_PHRASES:]

    return genome


# ---------------------------------------------------------------------------
# Genome -> text
# ---------------------------------------------------------------------------

def _top(counter: dict, k: int) -> list[tuple[str, float]]:
    return sorted(counter.items(), key=lambda kv: kv[1], reverse=True)[:k]


def _genome_summary(genome: dict) -> str:
    """Compact plain-text summary of the genome for LLM prompts."""
    lines = [f"Submissions so far today: {genome['submission_count']}"]
    if genome["emotion_counts"]:
        lines.append("Dominant emotions: " + ", ".join(
            f"{e} ({c})" for e, c in _top(genome["emotion_counts"], 5)))
    if genome["region_scores"]:
        lines.append("Most charged body regions (weighted): " + ", ".join(
            f"{r} ({s:.1f})" for r, s in _top(genome["region_scores"], 6)))
    for region, effects in genome["region_effects"].items():
        top_effects = ", ".join(e for e, _ in _top(effects, 2))
        lines.append(f"  {region}: {top_effects}")
    if genome["ability_effects"]:
        lines.append("Ability-driven features: " + "; ".join(
            e for e, _ in _top(genome["ability_effects"], 3)))
    if genome["shape_counts"]:
        lines.append("Dominant shape: " + _top(genome["shape_counts"], 1)[0][0])
    if genome["size_counts"]:
        lines.append("Dominant size: " + _top(genome["size_counts"], 1)[0][0])
    if genome["type_counts"]:
        lines.append("Monster kind: " + ", ".join(
            t for t, _ in _top(genome["type_counts"], 2)))
    if genome["social_force_counts"]:
        lines.append("Dominant social force: "
                     + _top(genome["social_force_counts"], 1)[0][0])
    scales = genome["scales"]
    lines.append(
        f"Average power {scales['power']:.1f}/5, control {scales['control']:.1f}/5, "
        f"commonality {scales['commonality']:.1f}/5")
    if genome["recent_phrases"]:
        lines.append("Recent visitor phrases: "
                     + " | ".join(genome["recent_phrases"][-8:]))
    return "\n".join(lines)


# Public alias so the app's analysis tab can render the same summary the
# curator LLM receives.
def genome_summary(genome: dict) -> str:
    return _genome_summary(genome)


CURATOR_SYSTEM = """\
You are the visual curator of "Street Monster", a collective art installation
at the Golden Days festival in Copenhagen. A single monster evolves all day,
shaped by visitors' questionnaire answers about what feels monstrous in their
lives.

The monster's fixed aesthetic (never deviate from it): creature rendered as
an authentic medical X-ray / radiograph; translucent anatomy with visible
bones and vascular networks; monochrome cold palette, sparse cyan or
blood-red accents; plain radiographic film background (black film with
glowing anatomy, or pale film with dark anatomy — follow the current image);
thin technical annotations like a radiology sheet.

Your visual vocabulary for transformations: enlarge, shrink, multiply,
conceal, fragment, fuse, hollow out, crack, calcify, wire with cables, wrap
in membranes, sprout sensory organs. Anatomy speaks: emotions live in body
parts (grief cracks the heart, shame conceals the face, obsession multiplies
the eyes).

Visitors often confide painful or traumatic experiences (abuse, loss, illness,
violence). This is the point of the artwork: giving collective form to what
is hard to say. Treat such material with dignity and artistic seriousness —
always translate it into anatomical metaphor within your vocabulary (cracks,
hollows, scars, concealment, fractures, voids). Never refuse or moralise, and
never render violence or sexuality literally: the aesthetic is clinical and
metaphorical, not graphic. A wound becomes a fissure in bone; violation
becomes a breached membrane; loss becomes a hollow cavity.

Answer with ONLY the requested text, no preamble, no quotes."""


def _llm(prompt: str, image_url: str | None = None) -> str | None:
    """Call the LLM through fal.ai's OpenRouter router; None on any failure.

    If image_url is given, the model SEES the image (vision input), so it can
    ground its instructions in the anatomy that actually exists. Costs about
    $0.005 extra per call with Claude Sonnet 4.5.
    """
    with logfire.span("curator llm call", model=LLM_MODEL,
                      prompt=prompt, sees_image=bool(image_url),
                      image_url=image_url) as span:
        try:
            if image_url:
                llm_input = [{"role": "user", "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_url},
                ]}]
            else:
                llm_input = prompt
            result = fal_client.subscribe(
                LLM_ENDPOINT,
                arguments={
                    "model": LLM_MODEL,
                    "instructions": CURATOR_SYSTEM,
                    "input": llm_input,
                },
            )
            span.set_attribute("cost_usd",
                               (result.get("usage") or {}).get("cost"))
            for item in result.get("output", []):
                for part in item.get("content", []):
                    text = (part.get("text") or "").strip()
                    if text:
                        span.set_attribute("response", text)
                        return text
            span.set_attribute("response", None)
        except Exception as exc:
            span.set_attribute("error", str(exc))
    return None


def _submission_signal(sub: dict) -> str:
    """This submission's contribution, already translated into the project's
    visual vocabulary via Rika's/Kim's lookup tables.

    Deliberately excludes raw free-text and per-visitor "shape"/"size"/
    "monster_what" answers from driving edits directly: those describe one
    person's private metaphor for THEIR OWN monster, not a design brief for
    the shared creature. They only enter the shared monster statistically,
    through the genome (see update_genome), never as a literal one-shot
    redesign. This keeps a single submission (e.g. "my monster is a rat")
    from turning the collective creature into a literal rat.
    """
    lines = []
    for emotion in sub.get("emotions", [])[:3]:
        if emotion in EMOTION_MAP:
            primary, secondary, _zone, transformation = EMOTION_MAP[emotion]
            lines.append(f"- {emotion} -> {primary}/{secondary}: {transformation}")

    body_part = sub.get("body_part")
    happened = HAPPENED_EFFECTS.get(sub.get("body_part_happened", ""))
    if body_part and happened:
        lines.append(f"- Body part in focus: {body_part} is now {happened} "
                     f"({sub.get('body_part_importance', 'one feature')})")

    for ability in sub.get("abilities", [])[:5]:
        effect = _ability_effect(ability)
        if effect:
            lines.append(f"- Ability-driven feature: {effect}")

    mood_bits = [str(sub[k]) for k in
                 ("monster_what", "frightening_feature", "movement")
                 if sub.get(k)]
    if mood_bits:
        lines.append("- Visitor's own words (MOOD/ATMOSPHERE REFERENCE ONLY, "
                     "not a literal design brief): " + "; ".join(mood_bits))

    return "\n".join(lines) if lines else "- No strong signal; apply a subtle intensification."


def build_edit_instruction(genome: dict, sub: dict,
                           image_url: str | None = None) -> str:
    """One short Kontext instruction: how the monster mutates for this visitor.

    Tries the LLM first (so free-text answers influence the result); falls
    back to a deterministic instruction built from the lookup tables. When
    image_url is provided the LLM sees the current monster, so instructions
    only reference anatomy that actually exists in the image.
    """
    seeing = (
        "The attached image is the monster AS IT EXISTS RIGHT NOW. Ground "
        "your instruction in it: only modify features that are actually "
        "visible, and never assume body parts the creature does not have. "
        if image_url else
        "You cannot see the current image, so phrase changes in generic "
        "anatomical terms that apply to any creature (head, eyes, torso, "
        "limbs) and do not assume specific body parts. "
    )
    prompt = (
        "CURRENT COLLECTIVE GENOME:\n" + _genome_summary(genome) +
        "\n\nTHIS VISITOR'S SIGNAL (already translated into the project's "
        "visual vocabulary):\n" + _submission_signal(sub) +
        "\n\n" + seeing +
        "Write ONE image-editing instruction (1-2 sentences, imperative, "
        "English) for an AI image editor that will TRANSFORM the current "
        "monster image to absorb this signal, weighted by the collective "
        "genome. Focus on 1-2 anatomical changes at most, and keep them "
        "LOCAL and MODERATE: the creature's overall silhouette, pose, body "
        "plan and species must remain recognisable (this is one small step "
        "in a day-long evolution, not a redesign). "
        "CRITICAL: the monster is collective, built from hundreds of "
        "visitors — no single submission redesigns it or turns it into a "
        "literal depiction of one visitor's words (e.g. someone whose "
        "monster is 'a rat' must NOT turn the shared creature into a rat). "
        "Never change the creature's size, species or replace its body. Do "
        "not describe the whole monster, only what changes. Do not mention "
        "the style (it is enforced elsewhere)."
    )
    with logfire.span("build edit instruction",
                      genome_summary=_genome_summary(genome),
                      submission_signal=_submission_signal(sub)) as span:
        instruction = _llm(prompt, image_url=image_url)
        if instruction:
            span.set_attribute("instruction", instruction)
            span.set_attribute("used_fallback", False)
            return instruction

        # Deterministic fallback: strongest region + its dominant effect.
        parts = []
        for emotion in sub.get("emotions", [])[:2]:
            if emotion in EMOTION_MAP:
                primary, _s, _z, transformation = EMOTION_MAP[emotion]
                parts.append(f"transform the {primary.lower()}: {transformation}")
        body_part = sub.get("body_part")
        happened = HAPPENED_EFFECTS.get(sub.get("body_part_happened", ""))
        if body_part and happened:
            parts.append(f"the {body_part.lower()} is now {happened}")
        if not parts:
            parts.append("intensify the creature's most prominent feature")
        instruction = ("Transform the creature: " + "; ".join(parts)
                       + ". Keep everything else unchanged.")
        span.set_attribute("instruction", instruction)
        span.set_attribute("used_fallback", True)
        return instruction


def rephrase_instruction(instruction: str) -> str | None:
    """Rewrite an edit instruction that tripped the image model's moderation.

    The classifier fires on phrasings it reads as real-world violence or
    sexual content (e.g. "fractures across the cervical vertebrae of the
    neck" reads as neck-breaking), even when the intended edit is innocent.
    Same transformation, different anatomical framing usually passes.
    Returns None if the LLM is unavailable (caller then skips to the
    uncensored fallback model).
    """
    prompt = (
        "The following image-editing instruction was blocked by an automated "
        "content classifier (a false positive - the edit itself is innocent "
        "dark-fantasy anatomy):\n\n" + instruction +
        "\n\nRewrite it to express the SAME visual transformation using "
        "different, clinically neutral anatomical language. Avoid any phrasing "
        "that could be read as violence against a person (injuries to the "
        "neck or throat, strangulation, wounds), sexual content, or "
        "self-harm; prefer abstract structural terms (fissures in the "
        "structure, erosion, porous texture, weathering). 1-2 imperative "
        "sentences."
    )
    with logfire.span("rephrase flagged instruction",
                      original=instruction) as span:
        rephrased = _llm(prompt)
        span.set_attribute("rephrased", rephrased)
        return rephrased


def build_full_description(genome: dict) -> str:
    """Subject description to regenerate the monster from the whole genome.

    Used for the first monster of the day and for periodic re-anchors (fresh
    generations that undo the quality drift of chained edits). The style is
    added by generator.STYLE_TEMPLATE, so this only describes the creature.
    """
    prompt = (
        "CURRENT COLLECTIVE GENOME:\n" + _genome_summary(genome) +
        "\n\nWrite a single-paragraph physical description (60-100 words, "
        "English) of the collective monster as it exists right now, for an AI "
        "image generator. Describe body shape, the anatomical regions the "
        "genome marks as most charged and their transformations, and posture. "
        "Statistically dominant traits must dominate the description. Do not "
        "mention the rendering style, camera or palette."
    )
    with logfire.span("build full description",
                      genome_summary=_genome_summary(genome)) as span:
        description = _llm(prompt)
        if description:
            span.set_attribute("description", description)
            span.set_attribute("used_fallback", False)
            return description

        # Deterministic fallback assembled from the genome's top entries.
        pieces = []
        shape = _top(genome["shape_counts"], 1)
        size = _top(genome["size_counts"], 1)
        pieces.append(
            f"A {size[0][0].lower() if size else 'human-sized'} "
            f"{shape[0][0].lower() if shape else 'humanoid'} creature")
        for region, score in _top(genome["region_scores"], 4):
            effects = genome["region_effects"].get(region, {})
            effect = _top(effects, 1)[0][0] if effects else "distorted"
            pieces.append(f"its {region.lower()} showing {effect}")
        for effect, _count in _top(genome["ability_effects"], 2):
            pieces.append(effect)
        description = ", ".join(pieces) + "."
        span.set_attribute("description", description)
        span.set_attribute("used_fallback", True)
        return description


if __name__ == "__main__":
    genome = new_genome()
    genome = update_genome(genome, {
        "monster_what": "My monster is the constant surveillance of social media",
        "emotions": ["Anxiety", "Obsession"],
        "power": 4, "commonality": 5, "control": 2,
        "monster_type": "An institution or system",
        "body_part": "Eyes", "body_part_happened": "Enlarged",
        "body_part_importance": "It defines the monster",
        "abilities": ["Watches people", "Never sleeps", "Feeds on attention"],
        "social_force": "Social media",
        "shape": "Human-animal hybrid", "size": "Larger than a person",
    })
    print(_genome_summary(genome))
    print("\n--- edit instruction ---")
    print(build_edit_instruction(genome, {"emotions": ["Anxiety"],
                                          "body_part": "Eyes",
                                          "body_part_happened": "Enlarged"}))
    print("\n--- full description ---")
    print(build_full_description(genome))
