"""Image generation logic backed by fal.ai.

This module is independent from the UI: it can be used from Streamlit, a script
or tests. The API key is read from the FAL_KEY environment variable (loaded from
a .env file).
"""

import fal_client
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "fal-ai/flux/schnell"


class ContentFlaggedError(Exception):
    """Raised when fal.ai's safety filter flags the generated image."""


def generate_image(prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Generate an image from a prompt and return its URL.

    Args:
        prompt: Text description of the image to generate.
        model: fal.ai model id to use.

    Returns:
        Direct URL to the generated image.

    Raises:
        ValueError: If the prompt is empty.
        ContentFlaggedError: If the safety filter flags the result (fal.ai
            returns a blank/black image in that case).
    """
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("The prompt cannot be empty.")

    result = fal_client.subscribe(model, arguments={"prompt": prompt})

    if any(result.get("has_nsfw_concepts", [])):
        raise ContentFlaggedError(
            "The prompt was flagged by the safety filter, so the image came back "
            "blank. Try rephrasing it."
        )

    return result["images"][0]["url"]


if __name__ == "__main__":
    url = generate_image("a dark monster in a foggy forest")
    print(url)
