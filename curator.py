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

import json

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

# ---------------------------------------------------------------------------
# Street Monster emotion groups and body-part mapping (revised questionnaire).
# Replaces the per-emotion table: the revised form asks for emotions grouped in
# six families, and the directors' mapping assigns three body parts per family.
#
# Genitals are deliberately excluded for now (user decision), which leaves the
# Vulnerability and Desire groups with two parts each.
# ---------------------------------------------------------------------------
EMOTION_GROUPS = {
    "Fear and threat": ["Horror", "Fear", "Anxiety", "Shock", "Confusion"],
    "Anger and rejection": ["Rage", "Hatred", "Disgust", "Frustration",
                            "Resentment"],
    "Vulnerability": ["Shame", "Guilt", "Inferiority", "Powerlessness",
                      "Helplessness", "Loneliness"],
    "Loss": ["Sorrow", "Grief", "Despair", "Emptiness"],
    "Desire and attraction": ["Attraction", "Passion", "Fascination",
                              "Obsession"],
    "Energy and resistance": ["Curiosity", "Hope", "Courage", "Determination",
                              "Defiance", "Relief"],
}

# Emotion -> its group, for O(1) lookup.
EMOTION_TO_GROUP = {e: g for g, es in EMOTION_GROUPS.items() for e in es}

# Body parts per group, most significant first.
GROUP_BODY_PARTS = {
    "Fear and threat": ["Eyes", "Heart", "Skin"],
    "Anger and rejection": ["Mouth and teeth", "Hands and fists",
                            "Stomach and gut"],
    "Vulnerability": ["Chest", "Shoulders and back"],
    "Loss": ["Eyes and tear ducts", "Heart", "Lungs"],
    "Desire and attraction": ["Mouth, lips and tongue", "Eyes"],
    "Energy and resistance": ["Legs and feet", "Spine", "Hands and arms"],
}

# The core principle of the mapping document: the same body part appears in
# several groups on purpose, and the emotional meaning is carried by HOW it is
# transformed, not merely by which part is affected.
GROUP_TRANSFORMATIONS = {
    ("Fear and threat", "Eyes"):
        "enlarged, wide, multiplied, looking in different directions",
    ("Fear and threat", "Heart"):
        "racing and swollen, straining against the ribs",
    ("Fear and threat", "Skin"):
        "bristling and blanched, drawn tight in alarm",
    ("Anger and rejection", "Mouth and teeth"):
        "enlarged jaw, exposed teeth, distorted bite",
    ("Anger and rejection", "Hands and fists"):
        "clenched and knotted, knuckles straining",
    ("Anger and rejection", "Stomach and gut"):
        "churning and darkened, twisted with visceral revulsion",
    ("Vulnerability", "Chest"):
        "laid open and exposed, unshielded",
    ("Vulnerability", "Shoulders and back"):
        "shrunken, bent, carrying an unseen burden",
    ("Loss", "Eyes and tear ducts"):
        "swollen and streaming, ducts enlarged and raw",
    ("Loss", "Heart"):
        "hollowed and cracked, an emptiness where it should beat",
    ("Loss", "Lungs"):
        "collapsed and heavy, caught mid-sigh",
    ("Desire and attraction", "Mouth, lips and tongue"):
        "exaggerated lips, tongue, softness and openness",
    ("Desire and attraction", "Eyes"):
        "focused, luminous, elongated, hypnotic",
    ("Energy and resistance", "Legs and feet"):
        "braced and driving forward, muscles gathered",
    ("Energy and resistance", "Spine"):
        "straightened and reinforced, rising",
    ("Energy and resistance", "Hands and arms"):
        "reaching and gripping, arms set to act",
}

# How the visitor responded (Q6) reads as the body's posture on the table.
RESPONSE_POSTURES = {
    "I confronted it": "braced and straining upward against the restraints",
    "I resisted it": "rigid and pushing back, muscles locked",
    "I tried to understand it": "still and attentive, head turned toward the hands",
    "I tried to change it": "half-risen, reaching toward its own wounds",
    "I adapted to it": "settled into the table, reshaped around the instruments",
    "I accepted it": "loose and yielding, open to the hands",
    "I avoided it": "turned away, curled from the light",
    "I escaped from it": "straining off the table, one limb already gone",
    "I sought help": "reaching outward, palms open",
    "I protected myself": "curled inward, arms shielding the torso",
    "I protected others": "arched outward, spread over something beneath it",
    "I ignored it": "utterly slack, indifferent to the surgery",
    "I used it to make a change": "propped up and re-forming, grafts taking hold",
    "I did not know what to do": "frozen mid-movement, caught between postures",
    "I did nothing": "inert and heavy, sunk into the drapes",
}

# How the visitor relates to it today (Q7) replaces the old power scale as the
# intensity modulator: unresolved wounds push the anatomy hardest.
RELATION_INTENSITY = {
    "It became a positive turning point in my life": 0.7,
    "I have come to terms with it": 0.85,
    "I am still processing it": 1.15,
    "It still has a strong impact on my life": 1.35,
    "It continues to have a deeply negative impact on my life": 1.5,
    "I prefer not to answer": 1.0,
}

# Visitors who answered "No" still shape the monster, but faintly: they are the
# voice of those who have not met a monster.
NO_ENCOUNTER_INTENSITY = 0.4

# Kept small on purpose: how many recent free-text fragments the genome
# remembers for the LLM to draw from.
MAX_RECENT_PHRASES = 20


def group_of(emotion: str) -> str | None:
    return EMOTION_TO_GROUP.get(emotion)


def transformation_for(group: str, part: str) -> str:
    """How this group transforms this body part (see GROUP_TRANSFORMATIONS)."""
    return GROUP_TRANSFORMATIONS.get((group, part), "distorted and altered")


def _ability_effect(ability: str) -> str | None:
    for group, members in ABILITY_GROUPS.items():
        if ability in members:
            return ABILITY_EFFECTS[group]
    return None


def new_genome() -> dict:
    return {
        "submission_count": 0,
        "encounter_counts": {"yes": 0, "no": 0},
        "emotion_counts": {},
        "group_scores": {},     # emotion family -> weighted score
        "region_scores": {},    # body part -> weighted score
        "region_effects": {},   # region -> {transformation phrase: count}
        "response_counts": {},
        "posture_counts": {},   # posture phrase -> count
        "relation_counts": {},
        "recent_phrases": [],
    }


def _bump(counter: dict, key: str, amount: float = 1) -> None:
    if key:
        counter[key] = counter.get(key, 0) + amount


def _add_effect(genome: dict, region: str, effect: str, amount: float) -> None:
    effects = genome["region_effects"].setdefault(region, {})
    effects[effect] = effects.get(effect, 0) + amount


def update_genome(genome: dict, sub: dict) -> dict:
    """Fold one revised-questionnaire submission into the genome.

    Expected keys (see the revised questionnaire):
        encountered        bool   - Q1, drives the branch
        emotions           [str]  - Q5 (or Q1-No), any of EMOTION_GROUPS
        monster_who        str    - Q2 free text (Yes branch)
        monster_look       str    - Q3 free text
        monster_effect     str    - Q4 free text
        responses          [str]  - Q6, RESPONSE_POSTURES keys
        relation_today     str    - Q7, RELATION_INTENSITY keys
    """
    genome = _migrate_genome(genome)
    genome["submission_count"] += 1

    encountered = bool(sub.get("encountered", True))
    genome["encounter_counts"]["yes" if encountered else "no"] += 1

    # Q7 replaces the old power scale as the intensity modulator; visitors who
    # never met a monster push the anatomy only faintly.
    intensity = (RELATION_INTENSITY.get(sub.get("relation_today", ""), 1.0)
                 if encountered else NO_ENCOUNTER_INTENSITY)

    for emotion in sub.get("emotions", []):
        group = group_of(emotion)
        if not group:
            continue
        _bump(genome["emotion_counts"], emotion)
        _bump(genome["group_scores"], group, intensity)
        # Parts are ordered by significance: the first carries full weight,
        # the rest progressively less.
        for rank, part in enumerate(GROUP_BODY_PARTS.get(group, [])):
            weight = intensity / (rank + 1)
            _bump(genome["region_scores"], part, weight)
            if rank == 0:
                _add_effect(genome, part, transformation_for(group, part),
                            intensity)

    for response in sub.get("responses", []):
        _bump(genome["response_counts"], response)
        posture = RESPONSE_POSTURES.get(response)
        if posture:
            _bump(genome["posture_counts"], posture, intensity)

    _bump(genome["relation_counts"], sub.get("relation_today", ""))

    for field in ("monster_who", "monster_look", "monster_effect"):
        text = (sub.get(field) or "").strip()
        if text:
            genome["recent_phrases"].append(text)
    genome["recent_phrases"] = genome["recent_phrases"][-MAX_RECENT_PHRASES:]

    return genome


def _migrate_genome(genome: dict) -> dict:
    """Make a genome from any earlier schema usable with the current one."""
    defaults = new_genome()
    for key, value in defaults.items():
        genome.setdefault(key, value)
    for key in ("yes", "no"):
        genome["encounter_counts"].setdefault(key, 0)
    return genome


# ---------------------------------------------------------------------------
# Genome -> text
# ---------------------------------------------------------------------------

def _top(counter: dict, k: int) -> list[tuple[str, float]]:
    return sorted(counter.items(), key=lambda kv: kv[1], reverse=True)[:k]


def _genome_summary(genome: dict) -> str:
    """Compact plain-text summary of the genome for LLM prompts."""
    genome = _migrate_genome(genome)
    counts = genome["encounter_counts"]
    lines = [f"Submissions so far today: {genome['submission_count']} "
             f"({counts.get('yes', 0)} met a monster, "
             f"{counts.get('no', 0)} never did)"]
    if genome["group_scores"]:
        lines.append("Dominant emotion families: " + ", ".join(
            f"{g} ({s:.1f})" for g, s in _top(genome["group_scores"], 3)))
    if genome["emotion_counts"]:
        lines.append("Most named emotions: " + ", ".join(
            f"{e} ({c})" for e, c in _top(genome["emotion_counts"], 6)))
    if genome["region_scores"]:
        lines.append("Most charged body regions (weighted): " + ", ".join(
            f"{r} ({s:.1f})" for r, s in _top(genome["region_scores"], 6)))
    for region, effects in genome["region_effects"].items():
        lines.append(f"  {region}: "
                     + ", ".join(e for e, _ in _top(effects, 2)))
    if genome["posture_counts"]:
        lines.append("Body's posture on the table: " + "; ".join(
            p for p, _ in _top(genome["posture_counts"], 2)))
    if genome["response_counts"]:
        lines.append("How visitors responded: " + ", ".join(
            r for r, _ in _top(genome["response_counts"], 3)))
    if genome["relation_counts"]:
        lines.append("How they relate to it today: "
                     + _top(genome["relation_counts"], 1)[0][0])
    if genome["recent_phrases"]:
        lines.append("Recent visitor phrases: "
                     + " | ".join(genome["recent_phrases"][-6:]))
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

The monster's fixed aesthetic (never deviate from it): a wide 1970s analog
film photograph of an operating room, camera set back so the whole table and
body are visible. The monster is the PATIENT lying on the table, wearing an
oxygen mask, while surgeons work on the body. Saturated Fuji film colour,
deep green-turquoise drapes, warm brown shadows, overhead spotlights, visible
film grain. Everything reads as a real documentary photograph, never a render.

CRITICAL — the patient is HUMAN. Visitors' accounts show that real monsters
are far more ordinary than people expect: a manager, a parent, a partner, an
illness, a silence. So the body on the table is a recognisable human being,
and the monstrousness shows as something quietly WRONG with it — a part
enlarged or missing, a texture that should not be there, an asymmetry, a
wound that has healed strangely. Restraint is the point: one or two clear
alterations on an otherwise human body disturb far more than a creature made
of tentacles. Never build a fantasy beast, never cover the body in growths,
never make it unrecognisable as a person.

Because it is a surgery, every change is something the surgeons are doing to
the body, or something the body is doing on the table.

Your visual vocabulary for transformations: enlarge, shrink, multiply,
conceal, fragment, fuse, hollow out, crack, calcify, suture, clamp, expose,
graft, wrap in membranes, sprout sensory organs. Anatomy speaks: emotions
live in body parts (grief cracks the heart, shame conceals the face,
obsession multiplies the eyes).

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
    if not sub.get("encountered", True):
        lines.append("- This visitor has NEVER met a monster: their emotions "
                     "shape the body only faintly, as a distant echo.")

    seen_groups = []
    for emotion in sub.get("emotions", []):
        group = group_of(emotion)
        if group and group not in seen_groups:
            seen_groups.append(group)
    for group in seen_groups[:3]:
        named = [e for e in sub["emotions"] if group_of(e) == group]
        parts = GROUP_BODY_PARTS.get(group, [])
        primary = parts[0] if parts else ""
        lines.append(
            f"- {group} ({', '.join(named)}) -> {' / '.join(parts)}; "
            f"{primary}: {transformation_for(group, primary)}")

    for response in sub.get("responses", [])[:3]:
        posture = RESPONSE_POSTURES.get(response)
        if posture:
            lines.append(f"- Response '{response}' -> posture: {posture}")

    relation = sub.get("relation_today")
    if relation:
        lines.append(f"- Today they say: {relation}")

    mood_bits = [str(sub[k]) for k in
                 ("monster_who", "monster_look", "monster_effect")
                 if sub.get(k)]
    if mood_bits:
        lines.append("- Visitor's own words (MOOD/ATMOSPHERE REFERENCE ONLY, "
                     "not a literal design brief): " + " | ".join(mood_bits))

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
        "genome. "
        "Focus on ONE anatomical change (two at most), and make it CLEARLY "
        "VISIBLE AT A GLANCE: a visitor comparing before and after must "
        "immediately spot what changed. Prefer bold structural moves "
        "(enlarge dramatically, multiply, crack open, hollow out, sprout a "
        "new structure) over subtle tints, slight darkening or texture "
        "changes that read as noise. When it fits the emotion, ignite the "
        "affected structure with a single saturated accent — a blood-red or "
        "electric cyan glow — since one color reads powerfully against the "
        "monochrome radiograph; never use more than one accent color. "
        "Keep the change LOCAL: the creature's overall silhouette, pose, "
        "body plan and species must remain recognisable (one bold step in a "
        "day-long evolution, not a redesign). "
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

        # Deterministic fallback: the groups named, via their primary parts.
        parts = []
        seen = []
        for emotion in sub.get("emotions", []):
            group = group_of(emotion)
            if group and group not in seen:
                seen.append(group)
        for group in seen[:2]:
            body_parts = GROUP_BODY_PARTS.get(group, [])
            if body_parts:
                primary = body_parts[0]
                parts.append(f"transform the {primary.lower()}: "
                             f"{transformation_for(group, primary)}")
        if not parts:
            parts.append("intensify the creature's most prominent feature")
        instruction = ("Transform the creature: " + "; ".join(parts)
                       + ". Keep everything else unchanged.")
        span.set_attribute("instruction", instruction)
        span.set_attribute("used_fallback", True)
        return instruction


def build_edit_plan(genome: dict, sub: dict,
                    image_url: str | None = None) -> dict:
    """Classified edit plan for the hybrid pipeline.

    Returns {"type": "local"|"structural", "region": str, "instruction": str}.

    - "local": the change transforms ONE existing visible region -> the
      pipeline segments that region (EVF-SAM) and repaints only it (FLUX
      Fill). `region` is a literal visual phrase for the segmenter;
      `instruction` describes what the region BECOMES.
    - "structural": the change adds new structures or affects the whole
      body -> the pipeline uses the Kontext edit chain. `instruction` is an
      imperative edit command.

    Falls back to a structural plan via build_edit_instruction if the LLM
    is unavailable or returns unparseable output.
    """
    seeing = (
        "The attached image is the monster AS IT EXISTS RIGHT NOW. Ground "
        "your plan in it: only reference features that are actually visible. "
        if image_url else
        "You cannot see the current image, so use generic anatomical terms. "
    )
    prompt = (
        "CURRENT COLLECTIVE GENOME:\n" + _genome_summary(genome) +
        "\n\nTHIS VISITOR'S SIGNAL (already translated into the project's "
        "visual vocabulary):\n" + _submission_signal(sub) +
        "\n\n" + seeing +
        "Decide how the monster absorbs this signal and answer with ONLY a "
        "JSON object, no code fences:\n"
        '{"type": "local" or "structural", "region": "...", '
        '"instruction": "..."}\n\n'
        "Use type \"local\" when the change transforms ONE existing, "
        "clearly visible body region (the common case). Then \"region\" is "
        "a short literal phrase naming that visible region for an image "
        "segmenter (e.g. \"the skull\", \"the ribcage\", \"both hands\") — "
        "it must be ONE compact feature, never the whole body, torso or "
        "figure. \"instruction\" is a self-contained description of what "
        "that region now looks like after absorbing the signal (it will be "
        "REPAINTED from your description). Describe only what IS VISIBLE "
        "after the change: image models cannot paint absence, so never "
        "phrase it as something missing or gone and never name the absent "
        "thing (e.g. for a missing heart, describe 'an empty black cavity "
        "between the ribs, edges cracked inward' — do not mention a heart). "
        "Make the transformation CLEARLY VISIBLE AT A GLANCE.\n"
        "Use type \"structural\" only when the change must add NEW "
        "structures outside the existing silhouette (sprouting limbs, "
        "growths) or alter the whole body at once. Then \"region\" is an "
        "empty string and \"instruction\" is an imperative editing command "
        "(1-2 sentences).\n"
        "In both cases: one bold change, keep the body's silhouette, pose and "
        "human identity recognisable, never a redesign, never a literal "
        "depiction of one visitor's words. The patient must stay a "
        "recognisable person — alter a part, never turn them into a beast or "
        "bury them under growths. Do not mention the rendering style.\n"
        "ANTI-DRIFT: the body accumulates a day of surgery, so ADD to what "
        "is already there instead of replacing it. Prefer a region that "
        "previous edits have NOT already rewritten — if the centre of the "
        "torso is already transformed, work on the head, a limb, the "
        "shoulders or the skin instead. Never overwrite an existing "
        "transformation with an unrelated one."
    )
    with logfire.span("build edit plan",
                      genome_summary=_genome_summary(genome),
                      submission_signal=_submission_signal(sub)) as span:
        raw = _llm(prompt, image_url=image_url)
        plan = _parse_plan(raw)
        if plan:
            span.set_attribute("plan", plan)
            span.set_attribute("used_fallback", False)
            return plan
        # LLM missing or malformed answer: fall back to the classic
        # structural instruction (deterministic path included).
        instruction = build_edit_instruction(genome, sub, image_url=image_url)
        plan = {"type": "structural", "region": "", "instruction": instruction}
        span.set_attribute("plan", plan)
        span.set_attribute("used_fallback", True)
        return plan


def _parse_plan(raw: str | None) -> dict | None:
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        plan = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    if plan.get("type") not in ("local", "structural"):
        return None
    if not (plan.get("instruction") or "").strip():
        return None
    if plan["type"] == "local" and not (plan.get("region") or "").strip():
        return None
    return {"type": plan["type"],
            "region": (plan.get("region") or "").strip(),
            "instruction": plan["instruction"].strip()}


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
        "\n\nWrite a single-paragraph physical description (40-70 words, "
        "English) of the collective monster as it exists right now, for an AI "
        "image generator. It will be dropped into a scene where it is the "
        "patient lying on an operating table, so describe only the BODY.\n"
        "Start from an ordinary human being — give them an age, a build, a "
        "face — and then apply ONLY the two or three most charged anatomical "
        "transformations from the genome. Everything else about them stays "
        "unremarkably human. The horror comes from how little is wrong, not "
        "how much: a person you could recognise, with something that should "
        "not be there. Never describe a beast, a hybrid or a body covered in "
        "growths. Include how they lie on the table. Do not mention the "
        "operating room, the surgeons, the rendering style, camera or palette."
    )
    with logfire.span("build full description",
                      genome_summary=_genome_summary(genome)) as span:
        description = _llm(prompt)
        if description:
            span.set_attribute("description", description)
            span.set_attribute("used_fallback", False)
            return description

        # Deterministic fallback assembled from the genome's top entries.
        pieces = ["A body lying on the table"]
        for region, _score in _top(genome["region_scores"], 4):
            effects = genome["region_effects"].get(region, {})
            effect = _top(effects, 1)[0][0] if effects else "distorted"
            pieces.append(f"its {region.lower()} {effect}")
        posture = _top(genome["posture_counts"], 1)
        if posture:
            pieces.append(posture[0][0])
        description = ", ".join(pieces) + "."
        span.set_attribute("description", description)
        span.set_attribute("used_fallback", True)
        return description


if __name__ == "__main__":
    import observability  # noqa: F401  (configures Logfire for the self-test)

    # Yes branch
    yes = {
        "encountered": True,
        "monster_who": ("My manager at my first job, who made a sport of "
                        "correcting me in front of the whole team."),
        "monster_look": ("Tall and always backlit, a shape I could never see "
                         "properly, with a voice that arrived before it did."),
        "monster_effect": ("I stopped speaking in meetings for years and I "
                           "still rehearse sentences before I say them."),
        "emotions": ["Shame", "Fear", "Rage", "Powerlessness"],
        "responses": ["I avoided it", "I protected myself"],
        "relation_today": "I am still processing it",
    }
    # No branch
    no = {"encountered": False, "emotions": ["Curiosity", "Fascination"]}

    genome = update_genome(update_genome(new_genome(), yes), no)
    print(_genome_summary(genome))
    print("\n--- submission signal (yes) ---")
    print(_submission_signal(yes))
    print("\n--- submission signal (no) ---")
    print(_submission_signal(no))
    print("\n--- full description ---")
    print(build_full_description(genome))
