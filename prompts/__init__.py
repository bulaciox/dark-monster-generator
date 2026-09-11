"""All the wording sent to the LLM/image/video models for the individual-
monster pipeline (curator.extract_identity, curator.build_story_and_title,
generator.generate_organ, generator.generate_silhouette,
generator.generate_silhouette_video), split one concern per file so they are
easy to find and edit without touching the orchestration code in
curator.py/generator.py:

  system.py           - the shared LLM system prompt (voice, privacy rules,
                        how to handle difficult material)
  identity.py         - turns a visitor's free text into a visual identity
  story.py            - turns a visitor's answers into the story + title
  organ.py             - the organ-screen image prompt
  silhouette.py        - the monster-screen image prompt
  silhouette_video.py  - the monster-screen's occasional animation prompt

The legacy, unused "collective" pipeline's prompts (CURATOR_SYSTEM,
STYLE_TEMPLATES, EDIT_*, and the build_edit_*/build_full_description
functions) were left in curator.py/generator.py rather than moved here, since
that flow is kept only for reference (see pipeline.py's module docstring).
"""
