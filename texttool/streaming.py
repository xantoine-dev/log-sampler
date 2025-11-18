"""Streaming utilities for handling very large log files."""

from __future__ import annotations

from collections.abc import Generator, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LineStreamConfig:
    """Configuration for chunked streaming."""

    chunk_size: int = 1024 * 1024
    encoding: str = "utf-8"
    errors: str = "ignore"


class LineStream(Iterator[str]):
    """Buffered iterator that only keeps a small window of the file in memory."""

    def __init__(self, path: Path | str, *, config: LineStreamConfig | None = None) -> None:
        self.path = Path(path)
        self.config = config or LineStreamConfig()
        self._file_handle = None

    def __iter__(self) -> LineStream:  # pragma: no cover - behaviour trivial
        return self

    def __next__(self) -> str:
        if self._file_handle is None:
            self._file_handle = self.path.open(
                "r",
                encoding=self.config.encoding,
                errors=self.config.errors,
                buffering=self.config.chunk_size,
            )

        line = self._file_handle.readline()
        if line:
            return line

        self._close()
        raise StopIteration

    def _close(self) -> None:
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None


def iter_chunks(path: Path | str, *, chunk_size: int = 1024 * 1024) -> Generator[str, None, None]:
    """Yield text chunks from *path*."""

    with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            yield chunk


def iter_lines(path: Path | str, *, config: LineStreamConfig | None = None) -> Iterable[str]:
    """Convenience wrapper that exposes :class:`LineStream` as a generator."""

    return LineStream(path, config=config)
