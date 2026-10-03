"""事件库（SQLite，WAL）。所有访问经同一把锁串行化，连接 ``check_same_thread=False``。"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from smartview.types import AlarmLevel, Event

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_start      REAL NOT NULL,
    ts_end        REAL,
    level_max     INTEGER NOT NULL,
    cam_id        TEXT NOT NULL,
    cls_name      TEXT NOT NULL,
    track_id      INTEGER NOT NULL,
    dist_min      REAL,
    ttc_min       REAL,
    speed_mps     REAL,
    acked         INTEGER NOT NULL DEFAULT 0,
    ack_ts        REAL,
    clip_path     TEXT,
    snapshot_path TEXT,
    extra         TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts_start);
CREATE TABLE IF NOT EXISTS purge_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL NOT NULL,
    channel TEXT NOT NULL,
    reason  TEXT NOT NULL
);
"""


def _row_to_event(r: sqlite3.Row) -> Event:
    return Event(
        event_id=r["event_id"],
        ts_start=r["ts_start"],
        ts_end=r["ts_end"],
        level_max=AlarmLevel(int(r["level_max"])),
        cam_id=r["cam_id"],
        cls_name=r["cls_name"],
        track_id=int(r["track_id"]),
        dist_min=r["dist_min"],
        ttc_min=r["ttc_min"],
        speed_mps=r["speed_mps"],
        acked=bool(r["acked"]),
        ack_ts=r["ack_ts"],
        clip_path=r["clip_path"],
        snapshot_path=r["snapshot_path"],
        extra=json.loads(r["extra"] or "{}"),
    )


class EventStore:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None, timeout=5.0)
        self._conn.row_factory = sqlite3.Row
        if self.db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)

    # ---------------------------------------------------------------- events
    def insert(self, ev: Event) -> int:
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO events(ts_start, ts_end, level_max, cam_id, cls_name, track_id, dist_min, ttc_min,
                   speed_mps, acked, ack_ts, clip_path, snapshot_path, extra)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    ev.ts_start,
                    ev.ts_end,
                    int(ev.level_max),
                    ev.cam_id,
                    ev.cls_name,
                    ev.track_id,
                    ev.dist_min,
                    ev.ttc_min,
                    ev.speed_mps,
                    int(ev.acked),
                    ev.ack_ts,
                    ev.clip_path,
                    ev.snapshot_path,
                    json.dumps(ev.extra, ensure_ascii=False),
                ),
            )
            ev.event_id = int(cur.lastrowid)
            return ev.event_id

    def update(self, event_id: int, **fields: Any) -> None:
        if not fields:
            return
        allowed = {"ts_end", "level_max", "dist_min", "ttc_min", "speed_mps", "acked", "ack_ts", "clip_path", "snapshot_path", "extra", "cls_name", "track_id", "cam_id"}
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"不允许更新字段 {bad}")
        vals = []
        cols = []
        for k, v in fields.items():
            if k == "extra" and not isinstance(v, str):
                v = json.dumps(v, ensure_ascii=False)
            if k == "level_max" and isinstance(v, AlarmLevel):
                v = int(v)
            if k == "acked":
                v = int(bool(v))
            cols.append(f"{k}=?")
            vals.append(v)
        vals.append(event_id)
        with self._lock:
            self._conn.execute(f"UPDATE events SET {', '.join(cols)} WHERE event_id=?", vals)

    def get(self, event_id: int) -> Event | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
        return _row_to_event(r) if r else None

    def list(self, limit: int = 50, since: float | None = None, min_level: int = 0) -> list[Event]:
        q = "SELECT * FROM events WHERE level_max>=?"
        args: list[Any] = [int(min_level)]
        if since is not None:
            q += " AND ts_start>=?"
            args.append(float(since))
        q += " ORDER BY ts_start DESC, event_id DESC LIMIT ?"
        args.append(int(limit))
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
        return [_row_to_event(r) for r in rows]

    def ack(self, event_id: int, ts: float) -> None:
        self.update(event_id, acked=True, ack_ts=ts)

    def stats(self, since: float | None = None) -> dict[str, Any]:
        q = "SELECT level_max, COUNT(*) AS n FROM events"
        args: list[Any] = []
        if since is not None:
            q += " WHERE ts_start>=?"
            args.append(float(since))
        q += " GROUP BY level_max"
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
            total = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        by_level = {f"L{int(r['level_max'])}": int(r["n"]) for r in rows}
        return {"total": int(total), "by_level": by_level}

    # ------------------------------------------------------------- purge log
    def log_purge(self, ts: float, channel: str, reason: str) -> None:
        with self._lock:
            self._conn.execute("INSERT INTO purge_log(ts, channel, reason) VALUES(?,?,?)", (ts, channel, reason))

    def purge_count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM purge_log").fetchone()[0])

    def journal_mode(self) -> str:
        with self._lock:
            return str(self._conn.execute("PRAGMA journal_mode").fetchone()[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()
