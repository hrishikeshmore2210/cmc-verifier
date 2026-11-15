"""Local filesystem "MCP store" — the build-now seam (ARCHITECTURE.md §6).

Right now this just lists/reads files from a directory so the pipeline runs
end-to-end on real files. Later, replace the internals with a real MCP server
(Veeva Vault / SharePoint / LIMS) WITHOUT touching the nodes that call it —
keep this interface stable.

`read` is confined to the store root (no path traversal, no symlink escape) and
refuses oversized files.
"""

from __future__ import annotations

from pathlib import Path

MAX_DOCUMENT_BYTES = 50 * 1024 * 1024


class DocumentAccessError(Exception):
    """A path escaped the store root or the document is too large."""


class LocalDocumentStore:
    def __init__(self, root: str | Path, max_bytes: int = MAX_DOCUMENT_BYTES):
        self.root = Path(root)
        self.max_bytes = max_bytes

    def list_documents(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(p for p in self.root.rglob("*") if p.is_file())

    def _resolve(self, path: str | Path) -> Path:
        root = self.root.resolve()
        p = Path(path)
        resolved = (p if p.is_absolute() else root / p).resolve()   # follows symlinks
        if resolved != root and root not in resolved.parents:
            raise DocumentAccessError(f"{path} is outside the document store root")
        return resolved

    def read(self, path: str | Path) -> bytes:
        resolved = self._resolve(path)
        if resolved.stat().st_size > self.max_bytes:
            raise DocumentAccessError(f"{path} exceeds {self.max_bytes} bytes")
        return resolved.read_bytes()
