"""User prompt for curator.extract_identity: turns a visitor's free-text
answers (Q1-Q3, "who/what was it", "what did it look like", "how did it
affect you") into a visual identity -- shape, setting, one object, a few
traits -- with nothing that could name the actual person, place or event.

Uses system.MONSTER_SYSTEM as its system prompt.
"""


def build(answers: str) -> str:
    """The full prompt sent to the model.

    Args:
        answers: The visitor's raw Q1-Q3 text, already formatted by
            curator.extract_identity as one "Label: answer" line per question.
    """
    return (
        "A visitor described their monster:\n\n" + answers +
        "\n\nTranspose this into a visual identity and reply with ONLY a JSON "
        "object with these keys:\n"
        '  "monster_type": "human" if the monster was a person or a '
        'relationship, "environmental" if it was an event, a system, an '
        "illness, a place or a condition.\n"
        '  "who_what": 10-20 words. The monster\'s FORM, as pure shape, scale '
        "and bearing. For a human monster: how it stands, its proportions, how "
        "it occupies space. For an environmental one: what kind of mass, "
        "swarm, architecture, weather or landscape it is. Never a role or a "
        "relationship.\n"
        '  "where": 5-12 words. The setting reduced to light, geometry and '
        "atmosphere only. Never a named place.\n"
        '  "object": 4-10 words. One significant object from the account, '
        "described as bare form and material. Empty string if there is none.\n"
        '  "traits": 2-4 strings, each 3-8 words. Concrete visual '
        "characteristics -- texture, material, posture, colour, movement.\n"
        '  "language": 2-6 words taken from or close to the visitor\'s own '
        "phrasing, evocative rather than identifying.\n\n"
        "Every value must survive the test: the visitor recognises it, a "
        "stranger learns nothing about who or what it was."
    )
