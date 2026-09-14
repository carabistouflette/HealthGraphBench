"""Source-manifest and download helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        candidates = (
            Path(__file__).parents[1] / "data" / "manifests" / "v0.1.json",
            Path.cwd() / "data" / "manifests" / "v0.1.json",
        )
        path = next(
            (candidate for candidate in candidates if candidate.is_file()),
            candidates[0],
        )
    return json.loads(path.read_text(encoding="utf-8"))


def verify_files(root: Path, entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Verify every manifest entry, failing instead of silently accepting drift."""

    verified: list[dict[str, Any]] = []
    for entry in entries:
        path = root / entry["path"]
        if not path.is_file():
            raise FileNotFoundError(path)
        actual_bytes = path.stat().st_size
        actual_sha256 = sha256_file(path)
        if actual_bytes != entry["bytes"] or actual_sha256 != entry["sha256"]:
            raise ValueError(
                f"source hash mismatch for {path}: "
                f"expected {entry['bytes']} bytes/{entry['sha256']}, "
                f"got {actual_bytes} bytes/{actual_sha256}"
            )
        verified.append({**entry, "verified": True})
    return verified
