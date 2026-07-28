# SQLite storage for hit records: timestamp, plate string, confidence,
# format (KZ/RU/unknown), and filenames of the saved full-frame and
# cropped-plate images (see storage/images.py). One writer (the capture
# loop thread) and readers (dashboard requests) share a single connection
# guarded by a lock -- write/read volume here is low, so a lock is simpler
# and plenty fast enough versus a connection pool.
from __future__ import annotations

import dataclasses
import sqlite3
import threading
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS hits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    plate TEXT NOT NULL,
    confidence REAL NOT NULL,
    format TEXT NOT NULL,
    frame_filename TEXT NOT NULL,
    crop_filename TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hits_timestamp ON hits(timestamp);
CREATE INDEX IF NOT EXISTS idx_hits_plate ON hits(plate);
"""


@dataclasses.dataclass(frozen=True)
class Hit:
    id: int
    timestamp: str
    plate: str
    confidence: float
    format: str
    frame_filename: str
    crop_filename: str


class HitStore:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def insert(
        self,
        timestamp: str,
        plate: str,
        confidence: float,
        format_: str,
        frame_filename: str,
        crop_filename: str,
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO hits "
                "(timestamp, plate, confidence, format, frame_filename, crop_filename) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (timestamp, plate, confidence, format_, frame_filename, crop_filename),
            )
            self._conn.commit()
            return cur.lastrowid

    def recent(self, limit: int = 50) -> list[Hit]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, timestamp, plate, confidence, format, "
                "frame_filename, crop_filename FROM hits ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [Hit(*row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
