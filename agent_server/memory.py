"""SQLite storage with short transactions and cross-process fenced leases."""
from contextlib import contextmanager
import json
import re
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from .migrations import migrate
from .settings import PORTABLE_SETTINGS, validate_settings


class Memory:
    def __init__(self, path="lovepilot.sqlite3", vault=None):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).resolve().parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA secure_delete=ON")
        migrate(self.db)
        self.vault = vault
        self._protect_existing()
        self._repair_legacy_cache()

    def _repair_legacy_cache(self):
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM storage_metadata WHERE key='retry_cache_repaired'").fetchone():
                return
            for cid, mid, encoded in db.execute('SELECT contact_id,message_id,response FROM processed').fetchall():
                try:
                    result = json.loads(self.unseal(encoded))
                except (ValueError, TypeError):
                    db.execute('DELETE FROM processed WHERE contact_id=? AND message_id=?', (cid, mid))
                    continue
                if result.get('retryable') or result.get('reason') == '模型调用失败，请检查服务端日志和密钥配置':
                    db.execute('DELETE FROM processed WHERE contact_id=? AND message_id=?', (cid, mid))
                    db.execute('DELETE FROM handled WHERE contact_id=? AND message_id=?', (cid, mid))
            db.execute("INSERT INTO storage_metadata VALUES('retry_cache_repaired','done')")

    def seal(self, value):
        return self.vault.seal(value) if self.vault else value

    def unseal(self, value):
        return self.vault.open(value) if self.vault else value

    def _protect_existing(self):
        marker = self.db.execute("SELECT value FROM storage_metadata WHERE key='field_encryption'").fetchone()
        if marker:
            if not self.vault:
                raise RuntimeError("encrypted database requires its data key")
            self.unseal(marker[0])
            return
        if not self.vault:
            return
        fields = {"contacts": ["alias", "notes"], "messages": ["content"], "facts": ["fact_value"],
                  "processed": ["response"], "settings": ["value"], "candidates": ["value", "source"],
                  "fact_meta": ["source"], "runs": ["trace"]}
        with self.transaction() as db:
            # Recheck after acquiring the write lock, including concurrent startup.
            marker = db.execute("SELECT value FROM storage_metadata WHERE key='field_encryption'").fetchone()
            if marker:
                self.unseal(marker[0])
                return
            for table, columns in fields.items():
                for column in columns:
                    for rowid, value in db.execute(f"SELECT rowid,{column} FROM {table}").fetchall():
                        db.execute(f"UPDATE {table} SET {column}=? WHERE rowid=?", (self.seal(value), rowid))
            db.execute("INSERT INTO storage_metadata VALUES('field_encryption',?)", (self.seal("v1"),))
        self.db.execute('VACUUM')
        self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
                self.db.commit()
            except BaseException:
                self.db.rollback()
                raise

    def contact(self, cid):
        with self.lock:
            row = self.db.execute("SELECT id,alias,consent,notes FROM contacts WHERE id=?", (cid,)).fetchone()
            return (row[0], self.unseal(row[1]), row[2], self.unseal(row[3])) if row else None

    def upsert(self, cid, alias, consent=False, notes=""):
        with self.transaction() as db:
            db.execute("INSERT INTO contacts VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET alias=excluded.alias,consent=excluded.consent,notes=excluded.notes", (cid, self.seal(alias), int(consent), self.seal(notes)))
            db.execute("INSERT INTO contact_state VALUES(?,?) ON CONFLICT(contact_id) DO UPDATE SET revision=excluded.revision", (cid, uuid.uuid4().hex))
            self._invalidate(db, cid)

    def _invalidate(self, db, cid):
        db.execute('UPDATE contact_state SET revision=? WHERE contact_id=?', (uuid.uuid4().hex, cid))
        db.execute('DELETE FROM processed WHERE contact_id=?', (cid,))
        db.execute('DELETE FROM leases WHERE contact_id=?', (cid,))

    def history(self, cid, limit=20):
        with self.lock:
            rows = self.db.execute("SELECT role,content FROM messages WHERE contact_id=? ORDER BY id DESC LIMIT ?", (cid, limit)).fetchall()
        return [dict(role=role, content=self.unseal(content)) for role, content in reversed(rows)]

    def add(self, cid, role, content):
        with self.transaction() as db:
            db.execute("INSERT INTO messages(contact_id,role,content,created_at) VALUES(?,?,?,?)", (cid, role, self.seal(content), int(time.time())))

    def audit(self, cid, decision):
        with self.transaction() as db:
            db.execute("INSERT INTO audit(contact_id,decision,created_at) VALUES(?,?,?)", (cid, decision, int(time.time())))

    def facts(self, cid):
        with self.lock:
            return {key: self.unseal(value) for key, value in self.db.execute("SELECT fact_key,fact_value FROM facts WHERE contact_id=? ORDER BY fact_key", (cid,)).fetchall()}

    def set_fact(self, cid, key, value):
        if not (isinstance(key, str) and isinstance(value, str) and 1 <= len(key) <= 60 and 1 <= len(value) <= 500):
            raise ValueError("invalid fact")
        with self.transaction() as db:
            db.execute("INSERT INTO facts VALUES(?,?,?,?) ON CONFLICT(contact_id,fact_key) DO UPDATE SET fact_value=excluded.fact_value,updated_at=excluded.updated_at", (cid, key, self.seal(value), int(time.time())))
            db.execute("INSERT INTO fact_meta VALUES(?,?,?,?,?) ON CONFLICT(contact_id,fact_key) DO UPDATE SET source=excluded.source,weight=excluded.weight,updated_at=excluded.updated_at", (cid, key, self.seal('用户手动确认'), 1.0, int(time.time())))
            self._invalidate(db, cid)

    def cached(self, cid, mid):
        with self.lock:
            row = self.db.execute("SELECT response FROM processed WHERE contact_id=? AND message_id=?", (cid, mid)).fetchone()
        return json.loads(self.unseal(row[0])) if row else None

    def cache(self, cid, mid, result):
        with self.transaction() as db:
            db.execute("INSERT OR IGNORE INTO processed VALUES(?,?,?)", (cid, mid, self.seal(json.dumps(result, ensure_ascii=False))))

    def revoke(self, cid):
        with self.transaction() as db:
            db.execute("UPDATE contacts SET consent=0 WHERE id=?", (cid,))
            db.execute("UPDATE contact_state SET revision=? WHERE contact_id=?", (uuid.uuid4().hex, cid))
            db.execute("DELETE FROM processed WHERE contact_id=?", (cid,))
            db.execute("DELETE FROM leases WHERE contact_id=?", (cid,))

    def claim(self, cid, mid, owner):
        """None indicates another worker currently owns this contact."""
        with self.transaction() as db:
            contact = self.contact(cid)
            if not contact or not contact[2]:
                return {"result": {"action": "handoff", "reason": "联系人未绑定或未授权"}}
            if mid:
                cached = self.cached(cid, mid)
                if cached is not None:
                    return {"result": cached}
                if db.execute('SELECT 1 FROM handled WHERE contact_id=? AND message_id=?', (cid, mid)).fetchone():
                    return {'result': {'action': 'handoff', 'reason': '该消息已处理，资料或授权已变更，请发送新消息'}}
            now = time.time()
            db.execute("DELETE FROM leases WHERE contact_id=? AND expires_at<=?", (cid, now))
            if db.execute("SELECT 1 FROM leases WHERE contact_id=?", (cid,)).fetchone():
                return None
            db.execute("INSERT INTO leases VALUES(?,?,?)", (cid, owner, now + 60))
            revision = db.execute("SELECT revision FROM contact_state WHERE contact_id=?", (cid,)).fetchone()[0]
            rows = db.execute('SELECT m.role,m.content FROM messages m WHERE m.contact_id=? AND NOT EXISTS(SELECT 1 FROM model_exclusions x WHERE x.message_id=m.id) ORDER BY m.id DESC LIMIT 20', (cid,)).fetchall()
            history = [dict(role=role, content=self.unseal(content)) for role, content in reversed(rows)]
            return {"contact": contact, "revision": revision, "facts": self.facts(cid), "history": history}

    def finish(self, cid, mid, owner, revision, message, result):
        """Atomically persist messages and cache after rechecking consent."""
        with self.transaction() as db:
            if self.settings().get('processing_paused', False):
                return {'action': 'handoff', 'reason': 'AI 处理已暂停，请本人处理'}
            valid = db.execute("SELECT 1 FROM contacts c JOIN contact_state s ON s.contact_id=c.id JOIN leases l ON l.contact_id=c.id WHERE c.id=? AND c.consent=1 AND s.revision=? AND l.owner=? AND l.expires_at>?", (cid, revision, owner, time.time())).fetchone()
            if not valid:
                return {"action": "handoff", "reason": "联系人授权或资料已变更，请重新确认"}
            now = int(time.time())
            if not result.get("retryable") and result.get("record_message", True):
                db.execute("INSERT INTO messages(contact_id,role,content,created_at) VALUES(?,?,?,?)", (cid, "user", self.seal(message), now))
                if result.get("action") == "draft":
                    db.execute("INSERT INTO messages(contact_id,role,content,created_at) VALUES(?,?,?,?)", (cid, "assistant", self.seal(result["reply"]), now))
            decision = result.pop("audit_decision", result["action"])
            result.pop("record_message", None)
            db.execute("INSERT INTO audit(contact_id,decision,created_at) VALUES(?,?,?)", (cid, decision, now))
            if mid and not result.get("retryable"):
                db.execute("INSERT OR IGNORE INTO processed VALUES(?,?,?)", (cid, mid, self.seal(json.dumps(result, ensure_ascii=False))))
                db.execute('INSERT OR IGNORE INTO handled VALUES(?,?)', (cid, mid))
            db.execute("DELETE FROM leases WHERE contact_id=? AND owner=?", (cid, owner))
            return result

    def release(self, cid, owner):
        with self.transaction() as db:
            db.execute("DELETE FROM leases WHERE contact_id=? AND owner=?", (cid, owner))

    def export(self, cid):
        with self.transaction():
            contact = self.contact(cid)
            if not contact:
                return None
            return self.export_unlocked(cid)

    def delete(self, cid):
        with self.transaction() as db:
            db.execute("DELETE FROM messages WHERE contact_id=?", (cid,))
            db.execute("DELETE FROM audit WHERE contact_id=?", (cid,))
            db.execute("DELETE FROM contacts WHERE id=?", (cid,))

    def save_run(self, run_id, cid, action, trace):
        with self.transaction() as db:
            if self.contact(cid):
                db.execute("INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?)", (run_id, cid, action, self.seal(json.dumps(trace, ensure_ascii=False)), int(time.time())))

    def contacts(self):
        with self.lock:
            rows = self.db.execute("SELECT id,alias,consent,notes FROM contacts ORDER BY alias,id").fetchall()
        return [dict(contact_id=cid, alias=self.unseal(alias), consent=bool(consent), notes=self.unseal(notes)) for cid, alias, consent, notes in rows]

    def settings(self):
        with self.lock:
            return {key: json.loads(self.unseal(value)) for key, value in self.db.execute("SELECT key,value FROM settings")}

    def update_settings(self, values):
        with self.transaction() as db:
            was_paused = self.settings().get('processing_paused', False)
            for key, value in values.items():
                db.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, self.seal(json.dumps(value, ensure_ascii=False))))
            if values.get('processing_paused') and not was_paused:
                for (cid,) in db.execute('SELECT id FROM contacts').fetchall():
                    self._invalidate(db, cid)

    def runs(self, cid=None, limit=100):
        with self.lock:
            rows = self.db.execute("SELECT id,contact_id,action,trace,created_at FROM runs WHERE (? IS NULL OR contact_id=?) ORDER BY created_at DESC,rowid DESC LIMIT ?", (cid, cid, limit)).fetchall()
        return [dict(id=rid, contact_id=contact, action=action, trace=json.loads(self.unseal(trace)), created_at=created) for rid, contact, action, trace, created in rows]

    def logs(self, limit=100):
        with self.lock:
            rows = self.db.execute("SELECT id,contact_id,decision,created_at FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(id=rid, contact_id=cid, decision=decision, created_at=created) for rid, cid, decision, created in rows]

    def offer_candidates(self, cid, message, revision):
        # Only literal statements made by the contact become pending candidates.
        patterns = {"兴趣": r"我喜欢([^。！？\n]{1,80})", "边界": r"我不喜欢([^。！？\n]{1,80})", "称呼": r"我叫([^，。！？\n]{1,30})"}
        with self.transaction() as db:
            current = db.execute("SELECT 1 FROM contacts c JOIN contact_state s ON s.contact_id=c.id WHERE c.id=? AND c.consent=1 AND s.revision=?", (cid, revision)).fetchone()
            if not current:
                return
            for category, pattern in patterns.items():
                for match in re.finditer(pattern, message):
                    value = match.group(1).strip()
                    known = {(item['category'], item['value']) for item in self.candidates(cid)}
                    if (category, value) not in known:
                        db.execute("INSERT INTO candidates(id,contact_id,category,value,source,created_at) VALUES(?,?,?,?,?,?)", (uuid.uuid4().hex, cid, category, self.seal(value), self.seal(match.group(0)), int(time.time())))

    def candidates(self, cid=None):
        with self.lock:
            rows = self.db.execute("SELECT id,contact_id,category,value,source,status,created_at FROM candidates WHERE (? IS NULL OR contact_id=?) ORDER BY created_at DESC,rowid DESC", (cid, cid)).fetchall()
        return [dict(id=rid, contact_id=contact, category=category, value=self.unseal(value), source=self.unseal(source), status=status, created_at=created) for rid, contact, category, value, source, status, created in rows]

    def confirm_candidate(self, cid, candidate_id, approve):
        with self.transaction() as db:
            row = db.execute("SELECT category,value,source,status FROM candidates WHERE id=? AND contact_id=?", (candidate_id, cid)).fetchone()
            if not row:
                raise KeyError("candidate not found")
            if row[3] != "pending":
                return
            if approve:
                contact = self.contact(cid)
                if not contact or not contact[2]:
                    raise PermissionError("contact consent required")
                # Each confirmed item keeps its own stable key, avoiding category overwrites.
                key = row[0] + "-" + candidate_id[:12]
                db.execute("INSERT INTO facts VALUES(?,?,?,?)", (cid, key, row[1], int(time.time())))
                db.execute("INSERT INTO fact_meta VALUES(?,?,?,?,?)", (cid, key, row[2], 1.0, int(time.time())))
                self._invalidate(db, cid)
            db.execute("UPDATE candidates SET status=? WHERE id=?", ("confirmed" if approve else "rejected", candidate_id))

    def delete_fact(self, cid, key):
        with self.transaction() as db:
            value = self.facts(cid).get(key)
            if value:
                for mid, content in db.execute('SELECT id,content FROM messages WHERE contact_id=?', (cid,)).fetchall():
                    if value in self.unseal(content):
                        db.execute('INSERT OR IGNORE INTO model_exclusions VALUES(?)', (mid,))
                for candidate in self.candidates(cid):
                    if candidate['category'] + '-' + candidate['id'][:12] == key:
                        db.execute('DELETE FROM candidates WHERE id=?', (candidate['id'],))
            db.execute("DELETE FROM facts WHERE contact_id=? AND fact_key=?", (cid, key))
            self._invalidate(db, cid)

    def fact_details(self, cid):
        with self.lock:
            rows = self.db.execute("SELECT f.fact_key,f.fact_value,f.updated_at,COALESCE(m.source,''),COALESCE(m.weight,1) FROM facts f LEFT JOIN fact_meta m ON f.contact_id=m.contact_id AND f.fact_key=m.fact_key WHERE f.contact_id=? ORDER BY f.updated_at DESC", (cid,)).fetchall()
        now = time.time()
        return [dict(key=key, value=self.unseal(value), updated_at=updated, source=self.unseal(source) if source else '', base_weight=weight, weight=round(weight * 0.5 ** (max(0, now - updated) / (180 * 86400)), 4)) for key, value, updated, source, weight in rows]

    def backup_document(self):
        with self.transaction():
            contacts = []
            for contact in self.contacts():
                record = self.export_unlocked(contact['contact_id'])
                record['candidates'] = self.candidates(contact['contact_id'])
                record['fact_details'] = self.fact_details(contact['contact_id'])
                rows = self.db.execute('SELECT m.created_at,x.message_id FROM messages m LEFT JOIN model_exclusions x ON x.message_id=m.id WHERE m.contact_id=? ORDER BY m.id', (contact['contact_id'],)).fetchall()
                record['message_times'] = [row[0] for row in rows]
                record['excluded_history_indices'] = [index for index, row in enumerate(rows) if row[1] is not None]
                record['audit'] = [{'decision': decision, 'created_at': created} for decision, created in self.db.execute('SELECT decision,created_at FROM audit WHERE contact_id=? ORDER BY id', (contact['contact_id'],))]
                record['runs'] = self.runs(contact['contact_id'], -1)
                record['handled_message_ids'] = [row[0] for row in self.db.execute('SELECT message_id FROM handled WHERE contact_id=? ORDER BY message_id', (contact['contact_id'],))]
                contacts.append(record)
            settings = {key: value for key, value in self.settings().items() if key in PORTABLE_SETTINGS}
            return {'version': 1, 'created_at': int(time.time()), 'contacts': contacts, 'settings': settings}

    def export_unlocked(self, cid):
        contact = self.contact(cid)
        return {'contact_id': contact[0], 'alias': contact[1], 'consent': bool(contact[2]), 'notes': contact[3],
                'facts': self.facts(cid), 'history': self.history(cid, -1)}

    def restore_document(self, document):
        if not isinstance(document, dict) or document.get('version') != 1 or not isinstance(document.get('contacts'), list):
            raise ValueError('invalid backup document')
        records = document['contacts']
        saved_settings = document.get('settings', {})
        if not isinstance(saved_settings, dict):
            raise ValueError('invalid backup settings')
        settings = {key: value for key, value in saved_settings.items() if key in PORTABLE_SETTINGS}
        validate_settings(settings)
        ids = []
        for record in records:
            if not isinstance(record, dict):
                raise ValueError('invalid backup contact')
            cid = record.get('contact_id')
            if not isinstance(cid, str) or not 1 <= len(cid) <= 100 or cid in ids:
                raise ValueError('invalid or duplicate backup contact')
            ids.append(cid)
            if not isinstance(record.get('alias'), str) or not isinstance(record.get('notes'), str):
                raise ValueError('invalid backup profile')
            facts, history = record.get('facts'), record.get('history')
            if not isinstance(facts, dict) or not isinstance(history, list):
                raise ValueError('invalid backup contents')
            for key, value in facts.items():
                if not isinstance(key, str) or not isinstance(value, str) or not 1 <= len(key) <= 60 or not 1 <= len(value) <= 500:
                    raise ValueError('invalid backup fact')
            for message in history:
                if not isinstance(message, dict) or message.get('role') not in ('user', 'assistant') or not isinstance(message.get('content'), str):
                    raise ValueError('invalid backup message')
            handled = record.get('handled_message_ids', [])
            if not isinstance(handled, list) or any(not isinstance(mid, str) or not 1 <= len(mid) <= 120 for mid in handled):
                raise ValueError('invalid handled message IDs')
            details = record.get('fact_details', [])
            if not isinstance(details, list):
                raise ValueError('invalid fact metadata')
            detail_keys = set()
            for item in details:
                if not isinstance(item, dict) or not isinstance(item.get('key'), str) or item['key'] not in facts or item['key'] in detail_keys:
                    raise ValueError('invalid fact metadata key')
                detail_keys.add(item['key'])
                weight = item.get('base_weight', 1.0)
                if type(weight) not in (int, float) or not 0 <= weight <= 100:
                    raise ValueError('invalid fact weight')
                if not isinstance(item.get('source', ''), str) or type(item.get('updated_at')) is not int or item['updated_at'] < 0:
                    raise ValueError('invalid fact metadata')
            for item in record.get('candidates', []):
                if not isinstance(item, dict) or item.get('status') not in ('pending', 'confirmed', 'rejected'):
                    raise ValueError('invalid backup candidate')
                for field in ('id', 'category', 'value', 'source'):
                    if not isinstance(item.get(field), str) or not item[field] or len(item[field]) > 4000:
                        raise ValueError('invalid backup candidate field')
                if type(item.get('created_at')) is not int:
                    raise ValueError('invalid backup timestamp')
            times = record.get('message_times', [0] * len(history))
            exclusions = record.get('excluded_history_indices', [])
            if len(times) != len(history) or any(type(value) is not int or value < 0 for value in times):
                raise ValueError('invalid message timestamps')
            if not isinstance(exclusions, list) or any(type(value) is not int or not 0 <= value < len(history) for value in exclusions):
                raise ValueError('invalid context exclusions')
            for event in record.get('audit', []):
                if not isinstance(event, dict) or not isinstance(event.get('decision'), str) or type(event.get('created_at')) is not int:
                    raise ValueError('invalid audit record')
            for run in record.get('runs', []):
                if not isinstance(run, dict) or not isinstance(run.get('id'), str) or run.get('action') not in ('draft', 'handoff') or not isinstance(run.get('trace'), list) or type(run.get('created_at')) is not int:
                    raise ValueError('invalid workflow record')
        with self.transaction() as db:
            for record in records:
                cid = record['contact_id']
                if self.contact(cid):
                    raise ValueError('restore conflict, existing contacts are protected')
                # Restored contacts require fresh consent and have no stale draft cache.
                db.execute('INSERT INTO contacts VALUES(?,?,0,?)', (cid, self.seal(record['alias']), self.seal(record['notes'])))
                db.execute('INSERT INTO contact_state VALUES(?,?)', (cid, uuid.uuid4().hex))
                for mid in record.get('handled_message_ids', []):
                    db.execute('INSERT OR IGNORE INTO handled VALUES(?,?)', (cid, mid))
                for key, value in record['facts'].items():
                    db.execute('INSERT INTO facts VALUES(?,?,?,?)', (cid, key, self.seal(value), int(time.time())))
                times = record.get('message_times', [int(time.time())] * len(record['history']))
                for index, message in enumerate(record['history']):
                    cursor = db.execute('INSERT INTO messages(contact_id,role,content,created_at) VALUES(?,?,?,?)', (cid, message['role'], self.seal(message['content']), times[index]))
                    if index in record.get('excluded_history_indices', []):
                        db.execute('INSERT INTO model_exclusions VALUES(?)', (cursor.lastrowid,))
                for event in record.get('audit', []):
                    db.execute('INSERT INTO audit(contact_id,decision,created_at) VALUES(?,?,?)', (cid, event['decision'], event['created_at']))
                for run in record.get('runs', []):
                    db.execute('INSERT INTO runs VALUES(?,?,?,?,?)', (run['id'], cid, run['action'], self.seal(json.dumps(run['trace'], ensure_ascii=False)), run['created_at']))
                for item in record.get('candidates', []):
                    db.execute('INSERT INTO candidates VALUES(?,?,?,?,?,?,?)', (item['id'], cid, item['category'], self.seal(item['value']), self.seal(item['source']), item['status'], item['created_at']))
                for item in record.get('fact_details', []):
                    db.execute('UPDATE facts SET updated_at=? WHERE contact_id=? AND fact_key=?', (item['updated_at'], cid, item['key']))
                    db.execute('INSERT INTO fact_meta VALUES(?,?,?,?,?)', (cid, item['key'], self.seal(item.get('source', '')), item.get('base_weight', 1.0), item['updated_at']))
            for key, value in settings.items():
                db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, self.seal(json.dumps(value, ensure_ascii=False))))
        return len(records)

    def erase_personal_data(self):
        with self.transaction() as db:
            ids = [row[0] for row in db.execute('SELECT id FROM contacts')]
            db.execute('DELETE FROM messages')
            db.execute('DELETE FROM audit')
            db.execute('DELETE FROM contacts')
            db.execute('DELETE FROM settings')
            db.execute("INSERT INTO settings VALUES('model_api_key',?)", (self.seal(json.dumps('')),))
            return ids
