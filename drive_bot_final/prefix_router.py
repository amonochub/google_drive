# drive_bot_final/prefix_router.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Tuple, Optional

from rapidfuzz import process, fuzz
import logging

logger = logging.getLogger(__name__)


class PrefixRouter:
    """
    Сопоставляет префикс (первые символы имени файла до '_')
    с ID папки Google Drive.
    """

    def __init__(self, config_file: str = "prefix_config.json") -> None:
        self.path = Path(config_file)
        self.prefix_to_folder: Dict[str, str] = {}
        self.default_folder_id: str = ""
        self.load()

    # ---------------------------------------------------------
    def load(self) -> None:
        if not self.path.exists():
            self.save()  # создаём пустой
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.prefix_to_folder = data.get("prefix_to_folder", {})
            self.default_folder_id = data.get("default_folder_id", "")
        except Exception as e:  # pragma: no cover
            logger.error("PrefixRouter: cannot load config → %s", e)

    def save(self) -> None:
        data = {
            "prefix_to_folder": self.prefix_to_folder,
            "default_folder_id": self.default_folder_id,
        }
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")

    # ---------------------------------------------------------
    @staticmethod
    def _extract_prefix(filename: str) -> Optional[str]:
        parts = filename.split("_", 1)
        return parts[0].upper() if len(parts) >= 2 else None

    def route(self, filename: str) -> Tuple[Optional[str], float]:
        """Возвращает (folder_id, confidence). 0.0 – нет совпадений."""
        prefix = self._extract_prefix(filename)
        if not prefix:
            return None, 0.0

        if prefix in self.prefix_to_folder:
            return self.prefix_to_folder[prefix], 1.0

        if self.prefix_to_folder:
            found = process.extractOne(
                prefix, self.prefix_to_folder.keys(), scorer=fuzz.ratio, score_cutoff=70
            )
            if found:
                best, score, _ = found  # rapidfuzz возвращает (value, score, index)
                return self.prefix_to_folder[best], score / 100

        return (self.default_folder_id or None, 0.1 if self.default_folder_id else 0.0)