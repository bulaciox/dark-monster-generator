"""Persistence layer backed by Supabase.

Saves generated images to Supabase Storage and records each (prompt, image URL)
pair in the database. Independent from the UI and from the generation logic.

Requires SUPABASE_URL and SUPABASE_KEY in the environment (loaded from .env).
"""

import datetime
import os
import uuid
import zoneinfo
from functools import lru_cache

import httpx
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

BUCKET = "monsters"
TABLE = "generations"
SUBMISSIONS_TABLE = "submissions"
STATE_TABLE = "monster_state"
MONSTERS_TABLE = "monsters"

FESTIVAL_TZ = zoneinfo.ZoneInfo("Europe/Copenhagen")


def today() -> str:
    """The festival day (ISO date) in Copenhagen time."""
    return datetime.datetime.now(FESTIVAL_TZ).date().isoformat()


@lru_cache(maxsize=1)
def _client() -> Client:
    """Return a cached Supabase client built from environment variables."""
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def _upload_to_bucket(image_bytes: bytes, content_type: str = "image/jpeg") -> str:
    ext = "jpg" if "jpeg" in content_type else content_type.split("/")[-1]
    path = f"{uuid.uuid4().hex}.{ext}"
    _client().storage.from_(BUCKET).upload(path, image_bytes, {"content-type": content_type})
    return _client().storage.from_(BUCKET).get_public_url(path)


def _insert_row(prompt: str, image_url: str, **extra) -> dict:
    row = _client().table(TABLE).insert(
        {"prompt": prompt, "image_url": image_url, **extra}).execute()
    return row.data[0]


def save_generation(prompt: str, source_url: str, **extra) -> dict:
    """Download a fal.ai temporary image, upload it to Storage and record it.

    Extra keyword args (day, version, kind) are stored on the generations row.
    PNG is preserved as PNG: re-saving each edit cycle as JPEG compounds
    compression artifacts visibly after a few passes.
    """
    response = httpx.get(source_url, follow_redirects=True)
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        content_type = ("image/png" if source_url.split("?")[0].endswith(".png")
                        else "image/jpeg")
    image_url = _upload_to_bucket(response.content, content_type)
    return _insert_row(prompt, image_url, **extra)


def save_upload(prompt: str, image_bytes: bytes, content_type: str) -> dict:
    """Upload a user-provided image to Storage and record it."""
    image_url = _upload_to_bucket(image_bytes, content_type)
    return _insert_row(prompt, image_url, kind="upload")


def list_generations(day: str | None = None) -> list[dict]:
    """Saved generations, newest first; optionally only one day's."""
    query = _client().table(TABLE).select("*")
    if day:
        query = query.eq("day", day)
    rows = query.order("created_at", desc=True).execute()
    return rows.data


# ---------------------------------------------------------------------------
# Questionnaire submissions
# ---------------------------------------------------------------------------

def save_submission(data: dict, image_url: str | None = None) -> dict:
    """Record one questionnaire submission (answers as jsonb)."""
    row = _client().table(SUBMISSIONS_TABLE).insert(
        {"day": today(), "data": data, "image_url": image_url}).execute()
    return row.data[0]


def list_submissions(day: str | None = None) -> list[dict]:
    """Questionnaire submissions, newest first; optionally only one day's."""
    query = _client().table(SUBMISSIONS_TABLE).select("*")
    if day:
        query = query.eq("day", day)
    rows = query.order("created_at", desc=True).execute()
    return rows.data


# ---------------------------------------------------------------------------
# Daily monster state (the genome)
# ---------------------------------------------------------------------------

def get_state(day: str | None = None) -> dict | None:
    """The monster_state row for a day (default today), or None."""
    rows = _client().table(STATE_TABLE).select("*").eq(
        "day", day or today()).execute()
    return rows.data[0] if rows.data else None


def upsert_state(genome: dict, image_url: str | None, version: int,
                 edits_since_anchor: int, day: str | None = None,
                 iteration: int = 1) -> dict:
    """Create or update the day's monster state."""
    row = _client().table(STATE_TABLE).upsert({
        "day": day or today(),
        "genome": genome,
        "image_url": image_url,
        "version": version,
        "edits_since_anchor": edits_since_anchor,
        "iteration": iteration,
        "updated_at": datetime.datetime.now(FESTIVAL_TZ).isoformat(),
    }).execute()
    return row.data[0]


def reset_day(day: str | None = None) -> int:
    """Archive the current monster and start fresh within the same day.

    Past generations keep their iteration number (shown as "Iteration X" in
    the gallery); the state is emptied so the next submission births a new
    monster. Returns the new iteration number.
    """
    state = get_state(day)
    new_iteration = (state.get("iteration") or 1) + 1 if state else 1
    upsert_state({}, None, 0, 0, day=day, iteration=new_iteration)
    return new_iteration


# ---------------------------------------------------------------------------
# Individual monsters (one per visitor)
# ---------------------------------------------------------------------------

def store_image(source_url: str) -> str:
    """Copy a fal.ai temporary image into Storage and return its public URL.

    Individual monsters are generated once and never edited, so JPEG is safe
    here: the compounding recompression that forced PNG on the collective path
    only happens when an image is re-saved on every edit cycle.
    """
    response = httpx.get(source_url, follow_redirects=True)
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        content_type = ("image/png" if source_url.split("?")[0].endswith(".png")
                        else "image/jpeg")
    return _upload_to_bucket(response.content, content_type)


def next_monster_number(day: str | None = None) -> int:
    """The respondent number for the next monster, counting up through the day.

    This is the number shown beside the title on the installation screens
    (21, 33, 45, 57 in the directors' sketches).
    """
    rows = _client().table(MONSTERS_TABLE).select(
        "id", count="exact").eq("day", day or today()).execute()
    return (rows.count or 0) + 1


def save_monster(identity: dict, organs: list[dict], story: str, title: str,
                 organ_image_url: str | None,
                 silhouette_image_url: str | None,
                 submission_id: str | None = None,
                 day: str | None = None) -> dict:
    """Record one visitor's monster: identity, organs and the four outputs."""
    day = day or today()
    row = _client().table(MONSTERS_TABLE).insert({
        "submission_id": submission_id,
        "day": day,
        "number": next_monster_number(day),
        "monster_type": identity.get("monster_type", "human"),
        "identity": identity,
        "organs": organs,
        "organ_image_url": organ_image_url,
        "silhouette_image_url": silhouette_image_url,
        "story": story,
        "title": title,
    }).execute()
    return row.data[0]


def list_monsters(day: str | None = None) -> list[dict]:
    """Visitors' monsters, newest first; optionally only one day's."""
    query = _client().table(MONSTERS_TABLE).select("*")
    if day:
        query = query.eq("day", day)
    rows = query.order("created_at", desc=True).execute()
    return rows.data


def get_monster(monster_id: str) -> dict | None:
    """One monster by id, or None."""
    rows = _client().table(MONSTERS_TABLE).select("*").eq(
        "id", monster_id).execute()
    return rows.data[0] if rows.data else None
