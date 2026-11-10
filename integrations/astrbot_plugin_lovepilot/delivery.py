"""Durable incoming message claims. Remote send receipts remain adapter-owned."""
from pathlib import Path
import sqlite3
import threading
import time


class DeliveryStore:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS deliveries(scope TEXT NOT NULL,message_id TEXT NOT NULL,state TEXT NOT NULL,expires_at REAL NOT NULL,PRIMARY KEY(scope,message_id))')

    def claim(self, scope, mid):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                row = self.db.execute('SELECT state,expires_at FROM deliveries WHERE scope=? AND message_id=?', (scope, mid)).fetchone()
                if row and (row[0] == 'sent' or row[1] > time.time()):
                    self.db.commit()
                    return False
                self.db.execute("INSERT INTO deliveries VALUES(?,?,'pending',?) ON CONFLICT(scope,message_id) DO UPDATE SET state='pending',expires_at=excluded.expires_at", (scope, mid, time.time() + 90))
                self.db.commit()
                return True
            except BaseException:
                self.db.rollback()
                raise

    def finish(self, scope, mid, completed):
        with self.lock:
            if completed:
                self.db.execute("UPDATE deliveries SET state='sent',expires_at=0 WHERE scope=? AND message_id=?", (scope, mid))
            else:
                self.db.execute("DELETE FROM deliveries WHERE scope=? AND message_id=? AND state='pending'", (scope, mid))

    def close(self):
        self.db.close()
