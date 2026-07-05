"""Logfire observability setup (https://logfire-eu.pydantic.dev).

Import this module ONCE, before anything else, from the app entry point.
Python caches module imports, so Streamlit's constant reruns do not
re-configure Logfire.

Credentials (either works):
- `LOGFIRE_TOKEN` in .env (write token from the Logfire project settings), or
- CLI OAuth: `uv run logfire --base-url='https://logfire-eu.pydantic.dev' auth`
  then `uv run logfire --base-url='https://logfire-eu.pydantic.dev' projects use --org 'bulacio' 'dark-monster-generator'`

If neither is present the app still runs normally; telemetry is simply
disabled (never break the installation over observability).
"""

import logfire
from dotenv import load_dotenv

load_dotenv()

LOGFIRE_BASE_URL = "https://logfire-eu.pydantic.dev"

try:
    logfire.configure(
        service_name="street-monster",
        advanced=logfire.AdvancedOptions(base_url=LOGFIRE_BASE_URL),
        # We always pass span attributes explicitly, so f-string
        # introspection is unnecessary — and it breaks under Streamlit's
        # exec()-based script runner, spamming warnings.
        inspect_arguments=False,
    )
except Exception:
    # No token and no CLI auth: run with telemetry disabled instead of
    # crashing the installation.
    logfire.configure(send_to_logfire=False, inspect_arguments=False)
