"""JSONL event logger."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict


class JsonlLogger:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **data: Any) -> Dict[str, Any]:
        record: Dict[str, Any] = {"timestamp": time.time(), "event": event}
        record.update(data)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record
