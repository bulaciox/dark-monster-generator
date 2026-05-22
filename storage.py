"""Persistence layer backed by Supabase.

Saves generated images to Supabase Storage and records each (prompt, image URL)
pair in the database. Independent from the UI and from the generation logic.

Requires SUPABASE_URL and SUPABASE_KEY in the environment (loaded from .env).
"""

import os
import uuid
from functools import lru_cache

import httpx
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

BUCKET = "monsters"
TABLE = "generations"


@lru_cache(maxsize=1)
def _client() -> Client:
    """Return a cached Supabase client built from environment variables."""
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def _upload_to_bucket(image_bytes: bytes, content_type: str = "image/jpeg") -> str:
    ext = "jpg" if "jpeg" in content_type else content_type.split("/")[-1]
    path = f"{uuid.uuid4().hex}.{ext}"
    _client().storage.from_(BUCKET).upload(path, image_bytes, {"content-type": content_type})
    return _client().storage.from_(BUCKET).get_public_url(path)


def _insert_row(prompt: str, image_url: str) -> dict:
    row = _client().table(TABLE).insert({"prompt": prompt, "image_url": image_url}).execute()
    return row.data[0]


def save_generation(prompt: str, source_url: str) -> dict:
    """Download a fal.ai temporary image, upload it to Storage and record it."""
    image_bytes = httpx.get(source_url, follow_redirects=True).content
    image_url = _upload_to_bucket(image_bytes, "image/jpeg")
    return _insert_row(prompt, image_url)


def save_upload(prompt: str, image_bytes: bytes, content_type: str) -> dict:
    """Upload a user-provided image to Storage and record it."""
    image_url = _upload_to_bucket(image_bytes, content_type)
    return _insert_row(prompt, image_url)


def list_generations() -> list[dict]:
    """Return all saved generations, newest first."""
    rows = _client().table(TABLE).select("*").order("created_at", desc=True).execute()
    return rows.data
