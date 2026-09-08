"""User prompt for curator.build_story_and_title: the visitor's answers
become a short third-person tale (the "story" screen) and a caption about
where they stand today (the "title" screen).

Uses system.MONSTER_SYSTEM as its system prompt.
"""


def build(parts: list[str], postures: list[str]) -> str:
    """The full prompt sent to the model.

    Args:
        parts: The data lines (effect, emotions, responses, where they stand
            today, the monster's form), already formatted by
            curator.build_story_and_title.
        postures: Up to 3 English phrases describing the visitor's bearing
            (from RESPONSE_POSTURES); appended as a hint when given.
    """
    prompt = (
        "A visitor's encounter with their monster:\n\n" + "\n".join(parts) +
        "\n\nWrite two things and reply with ONLY a JSON object:\n"
        '  "story": 40-70 words. Write one scene from a tale, in the third '
        "person, in which the visitor is the main character meeting this "
        "monster. Give the scene the narrative structure and symbolic "
        "quality of myth or fable: the character may run, break free, "
        "stand up, strike back, forgive or endure. But keep the writing "
        "straightforward and colloquial. Avoid the elevated, poetic or "
        "archaic language of classical myth. Any real person becomes an "
        "archetype (a mentor, an oracle, a gatekeeper, a shadow), never a "
        "father, teacher, manager or partner. Name no real place or event.\n"
        '  "title": 2-6 words. A line about where they stand NOW, spoken as '
        "if the tale had a caption. It may be a statement or a question. In "
        'the register of: "I retire in peace", "It\'s alright to run", '
        '"Still clueless?", "Did I call for you?"'
    )
    if postures:
        prompt += f"\n\nTheir bearing in the scene: {'; '.join(postures[:3])}."
    return prompt
