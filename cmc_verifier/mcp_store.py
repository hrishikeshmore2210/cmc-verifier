"""Local filesystem "MCP store" — the build-now seam (ARCHITECTURE.md §6).

Right now this just lists/reads files from a directory so the pipeline runs
end-to-end on real files. Later, replace the internals with a real MCP server
(Veeva Vault / SharePoint / LIMS) WITHOUT touching the nodes that call it —
keep this interface stable.
"""

from __future__ import annotations

from pathlib import Path


class LocalDocumentStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def list_documents(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(p for p in self.root.rglob("*") if p.is_file())

    def read(self, path: str | Path) -> bytes:
        return Path(path).read_bytes()
