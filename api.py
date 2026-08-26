"""HTTP API for the Street Monster installation.

Thin FastAPI layer over the existing modules — it holds no logic of its own:
generation lives in generator.py, the collective genome in curator.py, the
submission flow in pipeline.py and persistence in storage.py.

Run with: uv run uvicorn api:app --reload --port 8000
"""

import observability  # noqa: F401  (must be first: configures Logfire once)

import base64
import datetime
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse, Response

from curator import (
    EMOTION_GROUPS,
    RELATION_INTENSITY,
    RESPONSE_POSTURES,
    genome_summary,
)
from generator import STYLE_TEMPLATES, free_generate
from pipeline import process_submission
from storage import (
    get_monster,
    get_state,
    list_free_generations,
    list_generations,
    list_monsters,
    list_submissions,
    reset_day,
    save_free_generation,
    store_image,
    today,
)

app = FastAPI(title="Street Monster")

# While the piece is in development the whole site sits behind a shared
# password. Set APP_PASSWORD to enable it (any username is accepted); leave it
# unset locally and the gate disappears.
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
PUBLIC_PATHS = {"/health"}


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not APP_PASSWORD or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        header = request.headers.get("authorization", "")
        if header.startswith("Basic "):
            try:
                decoded = base64.b64decode(header[6:]).decode("utf-8")
                _, _, password = decoded.partition(":")
                if secrets.compare_digest(password, APP_PASSWORD):
                    return await call_next(request)
            except Exception:
                pass

        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Street Monster"'},
        )


app.add_middleware(BasicAuthMiddleware)

# The Vite dev server runs on another origin; in production the frontend is
# served by this same app, so this only matters during local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Unauthenticated so the platform can health-check the machine."""
    return {"ok": True}

VALID_EMOTIONS = {e for group in EMOTION_GROUPS.values() for e in group}


class Submission(BaseModel):
    """One visitor's answers to the revised questionnaire."""

    encountered: bool = Field(description="Q1: have you ever met a monster?")
    emotions: list[str] = Field(default_factory=list)
    # Yes branch only
    monster_who: str = ""
    monster_look: str = ""
    monster_effect: str = ""
    responses: list[str] = Field(default_factory=list)
    relation_today: str = ""

    @model_validator(mode="after")
    def _check_branch(self):
        unknown = sorted(set(self.emotions) - VALID_EMOTIONS)
        if unknown:
            raise ValueError(f"Unknown emotions: {unknown}")
        if not self.encountered:
            if not self.emotions:
                raise ValueError("Select at least one emotion.")
            # The No branch carries nothing else.
            self.monster_who = self.monster_look = self.monster_effect = ""
            self.responses, self.relation_today = [], ""
            return self
        for field in ("monster_who", "monster_look", "monster_effect"):
            if len(getattr(self, field).split()) < 10:
                raise ValueError(f"'{field}' needs at least 10 words.")
        if not self.emotions:
            raise ValueError("Select at least one emotion.")
        unknown_responses = sorted(set(self.responses) - set(RESPONSE_POSTURES))
        if unknown_responses:
            raise ValueError(f"Unknown responses: {unknown_responses}")
        if self.relation_today and self.relation_today not in RELATION_INTENSITY:
            raise ValueError("Unknown value for relation_today.")
        return self


class Monster(BaseModel):
    """One visitor's monster: the four outputs the installation shows."""

    id: str
    number: int                    # respondent number, shown beside the title
    day: str
    monster_type: str              # human | environmental
    organ_image_url: str | None
    silhouette_image_url: str | None
    story: str
    title: str
    organs: list[dict]
    identity: dict
    # The answers this monster came from, so the gallery can show them side by
    # side. Empty for rows saved without a submission.
    submission: dict

    @classmethod
    def from_row(cls, row: dict) -> "Monster":
        embedded = row.get("submissions") or {}
        return cls(
            id=str(row["id"]),
            number=row.get("number") or 0,
            day=str(row.get("day") or today()),
            monster_type=row.get("monster_type") or "human",
            organ_image_url=row.get("organ_image_url"),
            silhouette_image_url=row.get("silhouette_image_url"),
            story=row.get("story") or "",
            title=row.get("title") or "",
            organs=row.get("organs") or [],
            identity=row.get("identity") or {},
            submission=embedded.get("data") or {},
        )


@app.get("/api/form")
def form_options() -> dict:
    """Everything the questionnaire UI needs to render itself."""
    return {
        "emotion_groups": EMOTION_GROUPS,
        "responses": list(RESPONSE_POSTURES),
        "relations": list(RELATION_INTENSITY),
        "styles": list(STYLE_TEMPLATES),
        "min_words": 10,
    }


@app.get("/api/monster")
def monster(day: str | None = None) -> dict:
    """Today's monster: current image, counters and genome summary."""
    state = get_state(day)
    if not state or not state.get("image_url"):
        return {"born": False, "day": day or today(),
                "iteration": (state or {}).get("iteration", 1)}
    genome = state.get("genome") or {}
    iteration = state.get("iteration") or 1
    versions = [g for g in list_generations(day=day or today())
                if (g.get("iteration") or 1) == iteration]
    return {
        "born": True,
        "day": day or today(),
        "image_url": state["image_url"],
        "version": state.get("version"),
        "iteration": iteration,
        "edits_since_anchor": state.get("edits_since_anchor"),
        "submission_count": genome.get("submission_count", 0),
        "genome_summary": genome_summary(genome) if genome else "",
        "genome": genome,
        "versions": versions,
    }


@app.get("/api/generations")
def generations(day: str | None = None) -> list[dict]:
    return list_generations(day=day)


@app.get("/api/submissions")
def submissions(day: str | None = None) -> list[dict]:
    return list_submissions(day=day or today())


@app.post("/api/submissions", response_model=Monster)
def create_submission(sub: Submission) -> Monster:
    """Turn a visitor's answers into their own monster and return it.

    Synchronous on purpose: generation takes ~20-30s and the UI shows a
    waiting screen meanwhile.
    """
    try:
        monster, _kind = process_submission(sub.model_dump())
    except Exception as exc:  # storage/model failure — surface it to the UI
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Monster.from_row(monster)


@app.get("/api/monsters", response_model=list[Monster])
def monsters(day: str | None = None) -> list[Monster]:
    """Visitors' monsters, newest first; optionally only one day's."""
    return [Monster.from_row(row) for row in list_monsters(day=day)]


@app.get("/api/monsters/{monster_id}", response_model=Monster)
def monster_by_id(monster_id: str) -> Monster:
    row = get_monster(monster_id)
    if not row:
        raise HTTPException(status_code=404, detail="No such monster.")
    return Monster.from_row(row)


class FreeGenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)


class FreeGeneration(BaseModel):
    id: str
    prompt: str
    image_url: str
    created_at: str


@app.post("/api/free-generate", response_model=FreeGeneration)
def create_free_generation(req: FreeGenerationRequest) -> FreeGeneration:
    """Generate an image from a bare prompt and save it.

    The prompt is sent to FLUX.2 pro exactly as written — no system prompt,
    no style wrapping. Useful for exploring what the model can do before
    committing to a house style.
    """
    try:
        raw_url = free_generate(req.prompt)
        image_url = store_image(raw_url)
    except Exception as exc:
        detail = (
            "The prompt was flagged by the content checker. Try rephrasing it."
            if "content_policy_violation" in str(exc)
            else str(exc)
        )
        raise HTTPException(status_code=502, detail=detail) from exc
    row = save_free_generation(req.prompt, image_url)
    return FreeGeneration(
        id=str(row["id"]),
        prompt=row["prompt"],
        image_url=row["image_url"],
        created_at=str(row["created_at"]),
    )


@app.get("/api/free-generations", response_model=list[FreeGeneration])
def get_free_generations() -> list[FreeGeneration]:
    """All free generations, newest first."""
    return [
        FreeGeneration(
            id=str(r["id"]),
            prompt=r["prompt"],
            image_url=r["image_url"],
            created_at=str(r["created_at"]),
        )
        for r in list_free_generations()
    ]


@app.post("/api/reset")
def reset(day: str | None = None) -> dict:
    """Archive the current monster and start a fresh iteration."""
    return {"iteration": reset_day(day)}


# ---------------------------------------------------------------------------
# Exhibition screens: three URLs (/screen/story, /screen/monster, /screen/organ)
# each show part of the monster currently "on stage". A single server-side
# schedule decides who is on stage so the three screens always agree.
# ---------------------------------------------------------------------------

# Each monster holds the stage at least this long before the next one in the
# queue takes over. Chosen by the directors.
DWELL_SECONDS = 60


class Stage(BaseModel):
    monster: Monster | None


def _parse_created(value) -> datetime.datetime:
    """A monster row's created_at as an aware UTC datetime."""
    text = str(value or "").replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(text)
    except ValueError:
        return datetime.datetime.now(datetime.timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def _staged_monster(rows: list[dict]) -> dict | None:
    """Which monster is on stage now, from its schedule of entry times.

    Given the day's monsters oldest-first with entry times S(i):

        S(0) = t(0)
        S(i) = max(t(i), S(i-1) + DWELL)

    the one on stage is the last whose entry time has already passed. This
    gives every monster at least DWELL seconds, plays the queue in order when
    submissions pile up, and holds the latest once the queue is exhausted —
    all as a pure function of the creation times and the server clock, so the
    three screens need no coordination to stay in sync.
    """
    if not rows:
        return None

    now = datetime.datetime.now(datetime.timezone.utc)
    dwell = datetime.timedelta(seconds=DWELL_SECONDS)

    staged = None
    entry = None
    for row in rows:
        created = _parse_created(row.get("created_at"))
        entry = created if entry is None else max(created, entry + dwell)
        if entry <= now:
            staged = row
        else:
            break
    return staged


@app.get("/api/stage", response_model=Stage)
def stage() -> Stage:
    """The monster the exhibition screens should be showing right now."""
    rows = list_monsters(day=today())          # newest-first
    staged = _staged_monster(list(reversed(rows)))  # schedule wants oldest-first
    return Stage(monster=Monster.from_row(staged) if staged else None)


# In production the built React app is served from this same origin, so there
# is a single URL and the password gate covers the interface too. Mounted last
# so it never shadows the /api routes. Absent during local development, where
# Vite serves the frontend instead.
WEB_DIST = Path(__file__).parent / "web" / "dist"

if WEB_DIST.is_dir():
    # The exhibition screen URLs are client-side routes, so they have no file of
    # their own; hand them the SPA and let React read the path. Declared before
    # the catch-all mount, which would otherwise 404 them.
    @app.get("/screen/{name}")
    def screen_page(name: str) -> FileResponse:
        return FileResponse(WEB_DIST / "index.html")

    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
