# -*- coding: utf-8 -*-
"""快照存储：SQLite 保存每次采集结果，作为变化对比基准。"""
import json
import os
import sqlite3
from datetime import datetime, timezone


class SnapshotStore:
    def __init__(self, db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                source  TEXT NOT NULL,
                run_at  TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def latest(self, source):
        """返回指定数据源最近一次快照（dict），无则返回 None。"""
        cur = self.conn.execute(
            "SELECT payload FROM snapshots WHERE source = ? ORDER BY id DESC LIMIT 1",
            (source,),
        )
        row = cur.fetchone()
        return json.loads(row[0]) if row else None

    def save(self, source, payload):
        run_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S%z")
        self.conn.execute(
            "INSERT INTO snapshots (source, run_at, payload) VALUES (?, ?, ?)",
            (source, run_at, json.dumps(payload, ensure_ascii=False, sort_keys=True)),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
