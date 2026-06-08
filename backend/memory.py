import json
from pathlib import Path

MEMORY_FILE = Path(__file__).parent / "memory.json"


class CorrectionMemory:
    """
    Persistent key-value correction dictionary.
    Maps raw OCR strings -> human-verified correct strings.
    Stored in memory.json alongside the backend.
    """

    def __init__(self):
        self._data: dict = {}
        self._load()

    def _load(self):
        if MEMORY_FILE.exists():
            try:
                with open(MEMORY_FILE) as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = {}

    def _save(self):
        with open(MEMORY_FILE, "w") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def apply(self, raw: str) -> str:
        """Return corrected version of raw string, or raw if no correction exists."""
        return self._data.get(raw, raw)

    def add(self, raw: str, corrected: str):
        """Store a correction and persist to disk."""
        if raw and corrected:
            self._data[raw] = corrected
            self._save()

    def add_batch(self, corrections: dict) -> int:
        """Add multiple corrections at once. Returns count of new/updated entries."""
        count = 0
        for raw, corrected in corrections.items():
            if raw and corrected and raw != corrected:
                self._data[raw] = corrected
                count += 1
        if count:
            self._save()
        return count

    def get_all(self) -> dict:
        return dict(self._data)

    def clear(self):
        self._data = {}
        if MEMORY_FILE.exists():
            MEMORY_FILE.unlink()
