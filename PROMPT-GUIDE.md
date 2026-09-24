# Street Monster: Creative Guide

Each visitor's monster is made of three things: a close-up photo, a full-body
silhouette, and a short story with a title. This guide shows you, for each
of the three, which questionnaire answers it's built from, the exact
instruction ("prompt") currently sent to the AI, and which model to use if
you want to test your own version.

**You don't need any code or access to the installation to try things out.**
Test on the model's own website (links below), and once you're happy with a
version, send it to us and we'll put it live.

## How to test

- **The two images**: we use the model `fal-ai/flux-2-pro`, available
  through [fal.ai](https://fal.ai), in case you want to try it yourself.
  Each section below names the exact model to pick.
- **The story and title text**: we use Claude Sonnet 4.5, available at
  [claude.ai](https://claude.ai) or through
  [OpenRouter's playground](https://openrouter.ai/playground) using the model
  `anthropic/claude-sonnet-4.5`, in case you want to try it yourself.

---

## 1. The organ photo

The close-up image of a single body part, shown as a coiling, glistening
mass of skin on a dark studio table.

**Built from:**
- The emotions the visitor picked, which decide *which* body part appears
  and *how* it looks distorted (see the table in section 5).

**Current prompt** (the bracketed parts are filled in per visitor):

> A dense coiling abstract mass of human skin (#b87541) on a dark tabletop,
> seen from a high three-quarter angle, filling most of the frame. A spiral
> of **[BODY PART]**, **[HOW IT'S DISTORTED]** into a fractal vortex at the
> center, each opening nested inside the last. Skin taut, wet and
> glistening, ridged.
> The only things in the image are the skin mass, the dark tabletop, and a
> seamless black velvet backdrop (#050505) that fills the entire background
> edge to edge, uniformly dark.
> Lighting: cool pale backlight (#59c8f4) falling from high above and behind
> the subject, grazing the far contours and tops of the coils so the wet
> skin catches a cool glossy sheen where it turns away from the camera,
> separating the mass from the black. Dim warm tungsten fill from the
> front.
> Analog film studio photograph, warm near-black palette, film grain.

**Model to test with:** `fal-ai/flux-2-pro`

---

## 2. The monster silhouette

The full dark figure shown on the big screen.

**Built from:**
- Whether the monster was a person, or something more like an event, illness
  or place, which picks one of the two versions below.
- A short description of the monster's overall shape and bearing. For a
  person, that's all that's used. For an event/place, any object or visual
  details from the visitor's account are also placed in, always rewritten
  so nothing that could identify them appears (no names, no real places).

**Current prompt** (a different version depending on the monster's type):

If it's a person:
> A pitch-black silhouette of a standing human figure against a warm
> glowing haze (#e3ae86), backlit, the whole body a flat featureless
> cut-out. **[THE MONSTER'S SHAPE AND BEARING]** its head is huge and
> heavy -- a swollen, lumpen mass far too large for the small body,
> sagging sideways and slumping onto the shoulder under its own weight.
> Extra ear-like folds and bulging lobes swell from the head's black
> outline. Analog film studio photograph, warm near-black palette.

If it's an event, system or place:
> A pitch-black silhouette of a vast dark formation against a warm glowing
> haze (#e3ae86), backlit, its whole mass a flat featureless cut-out
> filling the frame. Not a creature and not a person: **[THE MONSTER'S
> SHAPE AND BEARING]**. **[ANY OBJECT / VISUAL DETAILS / BACKGROUND]** The
> formation coils on itself in a slow spiral, the same heavy ridged
> structure nested ring inside ring, each turn larger than the last,
> winding toward an unlit core. Analog film studio photograph, warm
> near-black palette.

**Model to test with:** `fal-ai/flux-2-pro`

> ⚠️ Whatever version you write, the figure must stay a flat, featureless,
> unrecognisable cut-out, no visible face, no identifying detail. This is
> what keeps the visitor anonymous, and it's the biggest screen in the
> room.

---

## 3. The story and the title

The short text shown on the story screen.

**Built from:**
- How the monster affected them.
- Which emotions they picked.
- How they responded to it (e.g. "I confronted it", "I avoided it"...).
- Where they feel they stand with it today.
- The monster's shape (same description used in section 2).

**Current prompt:**

> A visitor's encounter with their monster:
>
> [the five things above, each as a short line]
>
> Write two things and reply with ONLY a JSON object:
> "story": 40-70 words. Write one scene from a tale, in the third person, in
> which the visitor is the main character meeting this monster. Give the
> scene the narrative structure and symbolic quality of myth or fable: the
> character may run, break free, stand up, strike back, forgive or endure.
> But keep the writing straightforward and colloquial. Avoid the elevated,
> poetic or archaic language of classical myth. Any real person becomes an
> archetype (a mentor, an oracle, a gatekeeper, a shadow), never a father,
> teacher, manager or partner. Name no real place or event.
> "title": 2-6 words. A line about where they stand NOW, spoken as if the
> tale had a caption. It may be a statement or a question. In the register
> of: "I retire in peace", "It's alright to run", "Still clueless?", "Did I
> call for you?"

**Model to test with:** Claude Sonnet 4.5 (`anthropic/claude-sonnet-4.5`)

---

## 4. Which body part shows which emotion

This is the table that decides which body part appears in the organ photo
(section 1), and how it's described as distorted. Each emotion in the
questionnaire belongs to one of six groups; each group has three body parts,
from a milder response to the most serious one.

Feel free to suggest different body parts, different ways of describing the
distortion, or even a different grouping of emotions. Just make sure every
emotion on the questionnaire still ends up mapped to something.

| Emotion group | Emotions in this group | Body part (mild → severe) | How it's described as distorted |
|---|---|---|---|
| Fear and threat | Horror, Fear, Anxiety, Shock, Confusion | Eyes | enlarged, wide, multiplied, looking in different directions |
| | | Heart | racing and swollen, straining against the ribs |
| | | Skin | bristling and blanched, drawn tight in alarm |
| Anger and rejection | Rage, Hatred, Disgust, Frustration, Resentment | Mouth and teeth | enlarged jaw, exposed teeth, distorted bite |
| | | Hands and fists | clenched and knotted, knuckles straining |
| | | Stomach and gut | churning and darkened, twisted with visceral revulsion |
| Vulnerability | Shame, Guilt, Inferiority, Powerlessness, Helplessness, Loneliness | Chest | laid open and exposed, unshielded |
| | | Shoulders and back | shrunken, bent, carrying an unseen burden |
| | | Pelvis and hips | drawn inward and concealed, shielded, diminished |
| Loss | Sorrow, Grief, Despair, Emptiness | Eyes and tear ducts | swollen and streaming, ducts enlarged and raw |
| | | Heart | hollowed and cracked, an emptiness where it should beat |
| | | Lungs | collapsed and heavy, caught mid-sigh |
| Desire and attraction | Attraction, Passion, Fascination, Obsession | Mouth, lips and tongue | exaggerated lips, tongue, softness and openness |
| | | Eyes | focused, luminous, elongated, hypnotic |
| | | Pelvis and hips | opened outward and warm, tilted, drawn toward something |
| Energy and resistance | Curiosity, Hope, Courage, Determination, Defiance, Relief | Legs and feet | braced and driving forward, muscles gathered |
| | | Spine | straightened and reinforced, rising |
| | | Hands and arms | reaching and gripping, arms set to act |

A visitor can pick emotions from more than one group; the strongest one or
two groups (based on how many emotions they picked from each) decide which
body part(s) show up. Never more than two per monster.

---

## 5. Full examples, ready to paste and test

The prompts above have blanks that get filled in per visitor. Before those
blanks are filled in, there's actually one more hidden step you haven't
seen yet: the visitor's raw written answers are first sent to the text
model on their own, to be turned into a short, safe description of the
monster's shape and setting. It's THAT description that fills the blanks
in the organ and silhouette prompts, never the visitor's original words
directly.

Here's a full worked example, all the way through, based on one realistic
set of answers, so you can see exactly what goes in and what comes out at
every step.

### Step 1: the visitor's raw answers

> Who or what the monster was: My high school music teacher, who
> humiliated me in front of the whole class whenever I made a mistake.
> What it looked like: Always standing very upright at the front of the
> room, arms crossed, staring silently until I broke down.
> How it affected their life: It made me terrified of speaking in front of
> groups for years afterward, like my throat would close up.
>
> Emotions picked: Fear
> How they responded: I avoided it
> Where they stand with it today: I am still processing it

### Step 2: what gets sent to the text model, to turn that into a safe description

This is the input the LLM actually receives (paste this whole thing as one
message to test it):

> You are the curator of "Street Monster", an art installation. Each
> visitor answers a questionnaire about a monster in their life -- someone
> or something that felt monstrous to them -- and from those answers you
> build THAT PERSON'S monster, shown on the installation's screens. The
> visitor must be able to look at the screens and recognise their own
> monster. Everyone else must not be able to identify who or what it was.
> You TRANSPOSE, you never copy: every attribute is carried over as
> material, shape, texture, light or posture, never as the thing itself
> (e.g. "my teacher in a grey cardigan" becomes "grey wool texture across
> the shoulders"). Never name a person, a role, a relationship, a place, an
> institution or an event. Answer with ONLY what is asked for, no preamble,
> no quotes, no markdown.
>
> A visitor described their monster:
>
> Who or what the monster was: My high school music teacher, who
> humiliated me in front of the whole class whenever I made a mistake.
> What it looked like: Always standing very upright at the front of the
> room, arms crossed, staring silently until I broke down.
> How it affected their life: It made me terrified of speaking in front of
> groups for years afterward, like my throat would close up.
>
> Transpose this into a visual identity and reply with ONLY a JSON object
> with these keys:
> "monster_type": "human" if the monster was a person or a relationship,
> "environmental" if it was an event, a system, an illness, a place or a
> condition.
> "who_what": 10-20 words. The monster's FORM, as pure shape, scale and
> bearing. For a human monster: how it stands, its proportions, how it
> occupies space. For an environmental one: what kind of mass, swarm,
> architecture, weather or landscape it is. Never a role or a relationship.
> "where": 5-12 words. The setting reduced to light, geometry and
> atmosphere only. Never a named place.
> "object": 4-10 words. One significant object from the account, described
> as bare form and material. Empty string if there is none.
> "traits": 2-4 strings, each 3-8 words. Concrete visual characteristics --
> texture, material, posture, colour, movement.
> "language": 2-6 words taken from or close to the visitor's own phrasing,
> evocative rather than identifying.
>
> Every value must survive the test: the visitor recognises it, a stranger
> learns nothing about who or what it was.

### Step 3: what the model replies with

> {
>   "monster_type": "human",
>   "who_what": "A tall, rigid figure standing motionless at the front of
> a room, arms crossed, radiating silent judgment",
>   "where": "Rows of hard seats, harsh overhead light, all eyes turned
> forward",
>   "object": "A wooden baton held loosely, ready to strike a surface",
>   "traits": ["Arms locked tightly across the chest", "A stare that fixes
> and does not blink", "Shoulders squared like a wall"],
>   "language": "throat closing, frozen, judged"
> }

That's it: nothing in this reply could identify the actual teacher, but
the visitor would recognise every detail. This is what fills in the blanks
below.

### Step 4: the organ photo, using that description

The body part itself ("eyes") comes from the emotion table in section 4
(Fear → Eyes) and how it's distorted comes from the same table row.

> A dense coiling abstract mass of human skin (#b87541) on a dark tabletop,
> seen from a high three-quarter angle, filling most of the frame. A
> spiral of eyes, enlarged, wide, multiplied, looking in different
> directions into a fractal vortex at the center, each opening nested
> inside the last. Skin taut, wet and glistening, ridged.
> The only things in the image are the skin mass, the dark tabletop, and a
> seamless black velvet backdrop (#050505) that fills the entire
> background edge to edge, uniformly dark.
> Lighting: cool pale backlight (#59c8f4) falling from high above and
> behind the subject, grazing the far contours and tops of the coils so
> the wet skin catches a cool glossy sheen where it turns away from the
> camera, separating the mass from the black. Dim warm tungsten fill from
> the front.
> Analog film studio photograph, warm near-black palette, film grain.

### Step 5: the monster silhouette, using the same description

The visitor's monster is a person, so this uses the "person" version from
section 2:

> A pitch-black silhouette of a standing human figure against a warm
> glowing haze (#e3ae86), backlit, the whole body a flat featureless
> cut-out. A tall, rigid figure standing motionless at the front of a
> room, arms crossed, radiating silent judgment its head is huge and
> heavy -- a swollen, lumpen mass far too large for the small body,
> sagging sideways and slumping onto the shoulder under its own weight.
> Extra ear-like folds and bulging lobes swell from the head's black
> outline. Analog film studio photograph, warm near-black palette.

Note that, unlike the organ photo, the "person" silhouette doesn't use the
"object", "traits" or "where" parts of the description at all: only the
monster's shape and bearing. Those extra details only get used for
monsters that are an event or a place rather than a person (see the second
example below).

### Step 6: the story and title, using the same answers

> A visitor's encounter with their monster:
>
> How it affected them: It made me terrified of speaking in front of
> groups for years afterward, like my throat would close up.
> Emotions they felt: Fear
> How they responded: I avoided it
> Where they stand today: I am still processing it
> The monster's form: A tall, rigid figure standing motionless at the
> front of a room, arms crossed, radiating silent judgment
>
> Write two things and reply with ONLY a JSON object:
> "story": 40-70 words. Write one scene from a tale, in the third person,
> in which the visitor is the main character meeting this monster. Give
> the scene the narrative structure and symbolic quality of myth or fable:
> the character may run, break free, stand up, strike back, forgive or
> endure. But keep the writing straightforward and colloquial. Avoid the
> elevated, poetic or archaic language of classical myth. Any real person
> becomes an archetype (a mentor, an oracle, a gatekeeper, a shadow), never
> a father, teacher, manager or partner. Name no real place or event.
> "title": 2-6 words. A line about where they stand NOW, spoken as if the
> tale had a caption. It may be a statement or a question. In the register
> of: "I retire in peace", "It's alright to run", "Still clueless?", "Did I
> call for you?"
>
> Their bearing in the scene: turned away, curled from the light.

### A second example, for when the monster isn't a person

Some visitors describe an event, illness or system rather than a person.
The same process produces a description like this instead, which then
opens with the "not a creature and not a person" version of the silhouette
prompt (section 2):

> {
>   "monster_type": "environmental",
>   "who_what": "A vertical column of perpetually shifting matter, neither
> solid nor dispersed, suspended without anchor, drifting with glacial
> slowness",
>   "where": "Beneath an arch, cold stone overhead, stagnant air",
>   "object": "",
>   "traits": ["Twin points of dim phosphorescence, unblinking", "Surface
> never settles, constant dissolution", "No frontal plane, no
> orientation"],
>   "language": "small and cold, air turned against"
> }

That description would fill the "event, system or place" version of the
silhouette prompt from section 2 like this:

> A pitch-black silhouette of a vast dark formation against a warm glowing
> haze (#e3ae86), backlit, its whole mass a flat featureless cut-out
> filling the frame. Not a creature and not a person: A vertical column of
> perpetually shifting matter, neither solid nor dispersed, suspended
> without anchor, drifting with glacial slowness. Across it: Twin points
> of dim phosphorescence, unblinking; Surface never settles, constant
> dissolution; No frontal plane, no orientation. Behind it: Beneath an
> arch, cold stone overhead, stagnant air. The formation coils on itself
> in a slow spiral, the same heavy ridged structure nested ring inside
> ring, each turn larger than the last, winding toward an unlit core.
> Analog film studio photograph, warm near-black palette.

Notice this version DOES use the object/traits/where details ("Across it:
...", "Behind it: ..."), unlike the "person" version in step 5 above.

Real visitors' answers will read very differently from one submission to
the next. These are just worked examples so you have a realistic starting
point to test against.
