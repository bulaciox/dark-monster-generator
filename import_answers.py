"""Import the test-interview answers and generate a monster for each.

Throwaway: this exists so the directors can see what the model makes of real
answers, side by side with what each person said, before the house style is
decided. Delete once the style is settled.

    uv run --with openpyxl python import_answers.py [path/to/answers.xlsx]

Runs every row through pipeline.process_submission -- the same function the API
calls -- so nothing about the generation path is special-cased here.
"""

import sys
import time
from pathlib import Path

import observability  # noqa: F401  (must be first: configures Logfire once)

import openpyxl

from curator import EMOTION_GROUPS, RELATION_INTENSITY, RESPONSE_POSTURES
from pipeline import process_submission

DEFAULT_WORKBOOK = Path.home() / "Downloads" / "answers.xlsx"

# The interviews used a finer scale for Q6 than the questionnaire offers. Both
# variants collapse onto the one option the app has. Worth raising with the
# directors: Q6 sets the organ's intensity level, so a "fully / mostly / still
# processing" scale would give them more control than the single option does.
RELATION_ALIASES = {
    "I have fully come to terms with it": "I have come to terms with it",
    "I have mostly come to terms with it": "I have come to terms with it",
}

# Interviewer bookkeeping, not something the visitor said. Fed to the model it
# would read as testimony, so these are blanked instead.
PLACEHOLDERS = (
    "not recorded separately",
    "has not encountered a monster",
)

VALID_EMOTIONS = {e for group in EMOTION_GROUPS.values() for e in group}


def _clean(value) -> str:
    text = str(value or "").strip()
    if not text or text.lower().startswith(PLACEHOLDERS):
        return ""
    return text


def _split(value) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


def _responses(value) -> list[str]:
    out = []
    for response in _split(value):
        # "I escaped from it (tried to escape)" -> "I escaped from it"
        response = response.split("(")[0].strip()
        if response in RESPONSE_POSTURES:
            out.append(response)
        else:
            print(f"      ! unknown response dropped: {response!r}")
    return out


def _emotions(value) -> list[str]:
    out = []
    for emotion in _split(value):
        if emotion in VALID_EMOTIONS:
            out.append(emotion)
        else:
            print(f"      ! unknown emotion dropped: {emotion!r}")
    return out


def _relation(value) -> str:
    relation = _clean(value)
    relation = RELATION_ALIASES.get(relation, relation)
    if relation and relation not in RELATION_INTENSITY:
        print(f"      ! unknown relation dropped: {relation!r}")
        return ""
    return relation


def read_rows(path: Path) -> list[tuple[int, dict]]:
    """(row number, submission) for every answered row in the workbook."""
    sheet = openpyxl.load_workbook(path).active
    rows = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row[0] is None:
            continue
        encountered = str(row[2] or "").strip().lower() == "yes"
        submission = {
            "encountered": encountered,
            "emotions": _emotions(row[6]),
            "responses": _responses(row[7]),
            "relation_today": _relation(row[8]),
            "monster_who": _clean(row[3]),
            "monster_look": _clean(row[4]),
            "monster_effect": _clean(row[5]),
        }
        if not encountered:
            # The app drops the free text on the No branch. Three of these rows
            # did describe a hypothetical monster; that description is currently
            # discarded, which is a question for the directors.
            submission["monster_who"] = ""
            submission["monster_look"] = ""
            submission["monster_effect"] = ""
            submission["responses"] = []
            submission["relation_today"] = ""
        rows.append((int(row[0]), submission))
    return rows


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_WORKBOOK
    if not path.exists():
        sys.exit(f"No workbook at {path}")

    rows = read_rows(path)
    print(f"{len(rows)} rows from {path.name}\n")

    failures = []
    for number, submission in rows:
        label = (submission["monster_who"] or "(no encounter)")[:58]
        print(f"[{number:>2}] {label}")
        started = time.monotonic()
        try:
            # Called directly rather than through the API model, so rows with no
            # emotions are not blocked by the questionnaire's validation.
            monster, kind = process_submission(submission)
        except Exception as exc:
            print(f"      FAILED — {exc}\n")
            failures.append((number, str(exc)))
            continue

        organs = ", ".join(f"{o['part']} L{o['level']}" for o in monster["organs"])
        print(f"      no.{monster['number']} · {monster['monster_type']} · "
              f"{kind} · {time.monotonic() - started:.0f}s")
        print(f"      organs   {organs or '(none)'}")
        print(f"      title    {monster['title'] or '(none)'}")
        print(f"      images   organ={'ok' if monster['organ_image_url'] else 'MISSING'} "
              f"silhouette={'ok' if monster['silhouette_image_url'] else 'MISSING'}\n")

    print(f"Done. {len(rows) - len(failures)}/{len(rows)} imported.")
    for number, error in failures:
        print(f"  row {number}: {error}")


if __name__ == "__main__":
    main()
