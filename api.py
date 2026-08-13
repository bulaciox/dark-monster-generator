"""HTTP API for the Street Monster installation.

Thin FastAPI layer over the existing modules — it holds no logic of its own:
generation lives in generator.py, the collective genome in curator.py, the
submission flow in pipeline.py and persistence in storage.py.

Run with: uv run uvicorn api:app --reload --port 8000
"""

import observability  # noqa: F401  (must be first: configures Logfire once)

import base64
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from curator import (
    EMOTION_GROUPS,
    RELATION_INTENSITY,
    RESPONSE_POSTURES,
    genome_summary,
)
from generator import DEFAULT_THEME, STYLE_TEMPLATES
from pipeline import process_submission
from storage import (
    get_state,
    list_generations,
    list_submissions,
    reset_day,
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
            if len(getattr(self, field).split()) < 30:
                raise ValueError(f"'{field}' needs at least 30 words.")
        if not self.emotions:
            raise ValueError("Select at least one emotion.")
        unknown_responses = sorted(set(self.responses) - set(RESPONSE_POSTURES))
        if unknown_responses:
            raise ValueError(f"Unknown responses: {unknown_responses}")
        if self.relation_today and self.relation_today not in RELATION_INTENSITY:
            raise ValueError("Unknown value for relation_today.")
        return self


class SubmissionResult(BaseModel):
    kind: str          # initial | edit | reanchor | absorbed
    image_url: str | None
    previous_image_url: str | None
    version: int | None
    iteration: int | None


@app.get("/api/form")
def form_options() -> dict:
    """Everything the questionnaire UI needs to render itself."""
    return {
        "emotion_groups": EMOTION_GROUPS,
        "responses": list(RESPONSE_POSTURES),
        "relations": list(RELATION_INTENSITY),
        "styles": list(STYLE_TEMPLATES),
        "min_words": 30,
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


@app.post("/api/submissions", response_model=SubmissionResult)
def create_submission(sub: Submission,
                      theme: str = DEFAULT_THEME) -> SubmissionResult:
    """Fold a visitor's answers into the monster and return the new image.

    Synchronous on purpose: a birth takes ~30s and an edit ~12s, and the UI
    shows a waiting screen meanwhile.
    """
    previous = get_state()
    try:
        saved, kind = process_submission(sub.model_dump(), theme)
    except Exception as exc:  # storage/model failure — surface it to the UI
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SubmissionResult(
        kind=kind,
        image_url=saved.get("image_url"),
        previous_image_url=(previous or {}).get("image_url"),
        version=saved.get("version"),
        iteration=saved.get("iteration"),
    )


@app.post("/api/reset")
def reset(day: str | None = None) -> dict:
    """Archive the current monster and start a fresh iteration."""
    return {"iteration": reset_day(day)}


# In production the built React app is served from this same origin, so there
# is a single URL and the password gate covers the interface too. Mounted last
# so it never shadows the /api routes. Absent during local development, where
# Vite serves the frontend instead.
WEB_DIST = Path(__file__).parent / "web" / "dist"
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
