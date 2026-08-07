"""Read individual secrets from ~/.credentials/.

Secrets live in one file per service under ~/.credentials (override the
directory with MONIKA_CREDENTIALS_DIR). Call read_key / read_json at the point
where a secret is actually needed and pass it straight to the client that uses
it, rather than loading everything into the process environment.

Missing or malformed files return the supplied default so a caller can surface a
friendly error instead of crashing at import time.
"""

import json
import os
from pathlib import Path


def _credentials_dir() -> Path:
    override = os.getenv("MONIKA_CREDENTIALS_DIR")
    return Path(override) if override else Path.home() / ".credentials"


def read_key(filename: str, default=None):
    """Return the stripped contents of a plain-text credential file."""
    path = _credentials_dir() / filename
    if not path.exists():
        return default
    return path.read_text().strip()


def read_json(filename: str, default=None):
    """Return the parsed contents of a JSON credential file.

    Falls back to an empty dict (or the given default) when the file is absent or
    unparseable, so callers can use `.get(...)` and handle missing keys.
    """
    path = _credentials_dir() / filename
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default
