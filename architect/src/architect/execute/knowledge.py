"""KnowledgeManager — accumulate and search project knowledge."""

from __future__ import annotations

import logging
from pathlib import Path

from architect.core.exceptions import ExecuteError
from architect.core.models import KnowledgeEntry

__all__ = ["KnowledgeManager"]

log = logging.getLogger("architect.execute.knowledge")


class KnowledgeManager:
    """Persist and query a knowledge base stored as JSON-lines.

    Each line in the backing file is an independent JSON object that
    can be deserialised as a :class:`KnowledgeEntry`.
    """

    def __init__(self, knowledge_md_path: str) -> None:
        self._path = Path(knowledge_md_path)
        self._entries: list[KnowledgeEntry] = []
        if self._path.is_file():
            try:
                raw = self._path.read_text(encoding="utf-8").strip()
                for line in raw.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue
                    self._entries.append(KnowledgeEntry.model_validate_json(line))
                log.info(
                    "KnowledgeManager: loaded %d entries from %s",
                    len(self._entries),
                    self._path,
                )
            except Exception:  # noqa: BLE001
                # File may be Markdown from Generate Engine — start fresh
                log.info(
                    "KnowledgeManager: existing file is not JSON-lines, starting fresh (%s)",
                    self._path,
                )
                self._entries = []
        else:
            log.info("KnowledgeManager: starting fresh (no file at %s)", self._path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, entry: KnowledgeEntry) -> None:
        """Append a new entry, auto-generating an ID if empty."""
        if not entry.id:
            entry = entry.model_copy(
                update={"id": f"K{len(self._entries) + 1:03d}"}
            )
        self._entries.append(entry)
        self.save()
        log.info("knowledge.add: %s — %s", entry.id, entry.problem[:60])

    def search(self, tags: list[str], limit: int = 5) -> list[KnowledgeEntry]:
        """Return the top *limit* entries whose tags overlap with *tags*.

        Scoring: ``overlap_count * confidence``.  Entries with zero
        overlap are excluded.
        """
        tag_set = set(tags)
        scored: list[tuple[float, KnowledgeEntry]] = []
        for entry in self._entries:
            overlap = len(tag_set & set(entry.tags))
            if overlap > 0:
                scored.append((overlap * entry.confidence, entry))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def update_confidence(self, entry_id: str, success: bool) -> None:
        """Adjust an entry's confidence based on whether a fix succeeded."""
        for entry in self._entries:
            if entry.id == entry_id:
                new_applied = entry.applied_count + 1
                new_success = entry.success_count + (1 if success else 0)
                new_confidence = new_success / new_applied if new_applied else 0.0
                # Mutate via model_copy is safer, but since we own the list
                # we update in-place for simplicity.
                idx = self._entries.index(entry)
                self._entries[idx] = entry.model_copy(
                    update={
                        "applied_count": new_applied,
                        "success_count": new_success,
                        "confidence": round(new_confidence, 3),
                    },
                )
                self.save()
                log.info(
                    "knowledge.update_confidence: %s → %.3f",
                    entry_id,
                    new_confidence,
                )
                return
        log.warning("knowledge.update_confidence: entry %s not found", entry_id)

    def save(self) -> None:
        """Persist all entries as JSON-lines."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                entry.model_dump_json(exclude_none=False)
                for entry in self._entries
            ]
            self._path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as exc:
            raise ExecuteError(
                message="Failed to save knowledge base",
                detail=str(exc),
            ) from exc

    @property
    def entries(self) -> list[KnowledgeEntry]:
        """Read-only access to all entries."""
        return list(self._entries)
