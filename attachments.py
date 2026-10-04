"""Validation and encoding of user-uploaded attachments.

Copied from ultima (``app/claude/attachments.py``). Attachments reach Claude
the way the API itself takes them: as content blocks on the user message, sent
on the long-lived client as one stream-json message. Saving the files to disk is
the caller's job (discord-server keeps them under ``~/.monika/inbox``).

Three kinds are accepted:

* **images** -> an ``image`` block; Claude sees the pixels directly.
* **PDFs** -> a ``document`` block; Claude reads text and page images.
* **anything that decodes as UTF-8** -> a fenced ``text`` block.

Binary of any other kind is refused rather than guessed at.
"""

from __future__ import annotations

import base64
import binascii
import os
from typing import Any

IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
PDF_TYPE = "application/pdf"

# The API caps an image at 5 MB; the browser downscales photos well below this,
# so hitting the limit means something unusual and is worth an explicit error.
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_ATTACHMENTS = 10
# A text file this long would swamp the context window; better to say so than to
# silently truncate and have Claude answer about half a file.
MAX_TEXT_CHARS = 200_000


class AttachmentError(ValueError):
    """A rejected upload. The message is shown to the user verbatim."""


def _human(n: int) -> str:
    return f"{n / (1024 * 1024):.1f} MB" if n >= 1024 * 1024 else f"{n / 1024:.0f} KB"


def _decode(att: Any) -> tuple[str, str, bytes]:
    if not isinstance(att, dict):
        raise AttachmentError("Malformed attachment.")
    name = os.path.basename(str(att.get("name") or "file"))
    media_type = str(att.get("media_type") or "").split(";")[0].strip().lower()
    data = att.get("data")
    if not isinstance(data, str) or not data:
        raise AttachmentError(f"{name}: no file data.")
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise AttachmentError(f"{name}: could not decode upload.")
    if not raw:
        raise AttachmentError(f"{name} is empty.")
    return name, media_type, raw


def build_blocks(attachments: Any) -> list[dict]:
    """Turn the API's attachment payload into user-message content blocks.

    Raises :class:`AttachmentError` with a user-facing message for anything
    oversized, undecodable, or of a kind Claude cannot read.
    """
    if not attachments:
        return []
    if not isinstance(attachments, list):
        raise AttachmentError("Malformed attachments.")
    if len(attachments) > MAX_ATTACHMENTS:
        raise AttachmentError(f"Too many attachments (max {MAX_ATTACHMENTS}).")

    blocks: list[dict] = []
    total = 0
    for att in attachments:
        name, media_type, raw = _decode(att)
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise AttachmentError(f"Attachments exceed {_human(MAX_TOTAL_BYTES)} in total.")

        if media_type in IMAGE_TYPES:
            if len(raw) > MAX_IMAGE_BYTES:
                raise AttachmentError(f"{name} is {_human(len(raw))}; images are limited to {_human(MAX_IMAGE_BYTES)}.")
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64.b64encode(raw).decode("ascii"),
                    },
                }
            )
            continue

        if len(raw) > MAX_FILE_BYTES:
            raise AttachmentError(f"{name} is {_human(len(raw))}; files are limited to {_human(MAX_FILE_BYTES)}.")

        if media_type == PDF_TYPE:
            blocks.append(
                {
                    "type": "document",
                    "title": name,
                    "source": {
                        "type": "base64",
                        "media_type": PDF_TYPE,
                        "data": base64.b64encode(raw).decode("ascii"),
                    },
                }
            )
            continue

        # Everything else is only usable if it is really text.
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise AttachmentError(
                f"{name}: unsupported file type ({media_type or 'unknown'}). "
                "Attach an image, a PDF, or a text file."
            )
        if len(text) > MAX_TEXT_CHARS:
            raise AttachmentError(f"{name} is too long ({len(text):,} characters; max {MAX_TEXT_CHARS:,}).")
        fence = "`" * max(3, _longest_backtick_run(text) + 1)
        blocks.append(
            {"type": "text", "text": f"Attached file `{name}`:\n\n{fence}\n{text}\n{fence}"}
        )

    return blocks


def _longest_backtick_run(text: str) -> int:
    """Longest run of backticks, so a fence can be made that the file cannot break."""
    best = run = 0
    for ch in text:
        run = run + 1 if ch == "`" else 0
        best = max(best, run)
    return best
