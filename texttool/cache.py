"""Simple persistence layer for memoizing expensive summaries."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class CacheEntry:
    """Metadata + payload stored in the summary cache."""

    size: int
    mtime: float
    summary: dict[str, Any]

    def matches_file(self, path: Path) -> bool:
        stats = path.stat()
        return stats.st_size == self.size and stats.st_mtime == self.mtime


class SummaryCache:
    """Disk-backed memoization for per-file summaries."""

    def __init__(self, cache_path: Path | str | None = None) -> None:
        base = Path(cache_path) if cache_path else Path.home() / ".cache" / "text_processing_cli"
        self.cache_path = base if base.suffix == ".json" else base / "summaries.json"
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, CacheEntry] | None = None

    def _load(self) -> None:
        if self._entries is not None:
            return
        if not self.cache_path.exists():
            self._entries = {}
            return
        data = json.loads(self.cache_path.read_text())
        self._entries = {
            path: CacheEntry(size=entry["size"], mtime=entry["mtime"], summary=entry["summary"])
            for path, entry in data.items()
        }

    def _persist(self) -> None:
        assert self._entries is not None, "Cache must be initialized before persisting"
        serializable = {path: asdict(entry) for path, entry in self._entries.items()}
        self.cache_path.write_text(json.dumps(serializable, indent=2))

    def get(self, path: Path | str) -> dict[str, Any] | None:
        self._load()
        assert self._entries is not None
        normalized = str(Path(path).resolve())
        entry = self._entries.get(normalized)
        if not entry:
            return None
        try:
            if entry.matches_file(Path(path)):
                return entry.summary
        except FileNotFoundError:
            return None
        return None

    def set(self, path: Path | str, summary: dict[str, Any]) -> None:
        self._load()
        assert self._entries is not None
        resolved = Path(path).resolve()
        stats = resolved.stat()
        self._entries[str(resolved)] = CacheEntry(
            size=stats.st_size,
            mtime=stats.st_mtime,
            summary=summary,
        )
        self._persist()

    def clear(self) -> None:
        self._entries = {}
        if self.cache_path.exists():
            self.cache_path.unlink()


def get_cache(enabled: bool) -> SummaryCache | None:
    """Return a cache instance only when memoization is enabled."""

    return SummaryCache() if enabled else None
