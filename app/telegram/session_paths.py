from __future__ import annotations

import re
from pathlib import Path

_INVALID_CHARS = re.compile(r"[^\w.-]+")


def session_slug(username: str | None, telegram_id: int) -> str:
    if username:
        slug = _INVALID_CHARS.sub("_", username.strip().lower()).strip("._")
        if slug:
            return slug
    return f"user_{telegram_id}"


def resolve_session_path(
    sessions_dir: Path,
    *,
    username: str | None,
    telegram_id: int,
    reserved: set[str] | None = None,
) -> Path:
    reserved = reserved or set()
    base = session_slug(username, telegram_id)
    candidates = [base, f"{base}_{telegram_id}"]

    for name in candidates:
        if name in reserved:
            continue
        path = sessions_dir / name
        if not path.with_suffix(".session").exists():
            return path

    return sessions_dir / f"{base}_{telegram_id}"


def move_session_files(src: Path, dst: Path) -> None:
    for suffix in (".session", ".session-journal"):
        source = Path(f"{src}{suffix}")
        target = Path(f"{dst}{suffix}")
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target.unlink()
            source.rename(target)
