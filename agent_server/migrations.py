"""Ordered transactional migrations, including adoption of legacy databases."""
import time

MIGRATIONS = [
    (1, [
        "CREATE TABLE IF NOT EXISTS contacts(id TEXT PRIMARY KEY, alias TEXT NOT NULL, consent INTEGER NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '')",
        "CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id TEXT NOT NULL REFERENCES contacts(id), role TEXT NOT NULL, content TEXT NOT NULL, created_at INTEGER NOT NULL)",
        "CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id TEXT, decision TEXT NOT NULL, created_at INTEGER NOT NULL)",
        "CREATE TABLE IF NOT EXISTS facts(contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE, fact_key TEXT NOT NULL, fact_value TEXT NOT NULL, updated_at INTEGER NOT NULL, PRIMARY KEY(contact_id,fact_key))",
        "CREATE TABLE IF NOT EXISTS processed(contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE, message_id TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(contact_id,message_id))",
    ]),
    (2, [
        "CREATE TABLE contact_state(contact_id TEXT PRIMARY KEY REFERENCES contacts(id) ON DELETE CASCADE, revision TEXT NOT NULL)",
        "INSERT INTO contact_state SELECT id,lower(hex(randomblob(16))) FROM contacts",
        "CREATE TABLE leases(contact_id TEXT PRIMARY KEY REFERENCES contacts(id) ON DELETE CASCADE, owner TEXT NOT NULL, expires_at REAL NOT NULL)",
        "CREATE INDEX messages_contact_order ON messages(contact_id,id)",
        "CREATE INDEX audit_contact_order ON audit(contact_id,id)",
    ]),
    (3, [
        "CREATE TABLE runs(id TEXT PRIMARY KEY,contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,action TEXT NOT NULL,trace TEXT NOT NULL,created_at INTEGER NOT NULL)",
        "CREATE INDEX runs_contact_time ON runs(contact_id,created_at)",
    ]),
    (4, [
        "CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)",
        "CREATE TABLE candidates(id TEXT PRIMARY KEY,contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,category TEXT NOT NULL,value TEXT NOT NULL,source TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at INTEGER NOT NULL,UNIQUE(contact_id,category,value))",
        "CREATE TABLE fact_meta(contact_id TEXT NOT NULL,fact_key TEXT NOT NULL,source TEXT NOT NULL DEFAULT '',weight REAL NOT NULL DEFAULT 1,updated_at INTEGER NOT NULL,PRIMARY KEY(contact_id,fact_key),FOREIGN KEY(contact_id,fact_key) REFERENCES facts(contact_id,fact_key) ON DELETE CASCADE)",
    ]),
    (5, ["CREATE TABLE storage_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)"]),
    (6, [
        "CREATE TABLE handled(contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,message_id TEXT NOT NULL,PRIMARY KEY(contact_id,message_id))",
        "INSERT INTO handled SELECT contact_id,message_id FROM processed",
        "CREATE TABLE model_exclusions(message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE)",
    ]),
]


def migrate(connection):
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL)")
        current = connection.execute("PRAGMA user_version").fetchone()[0]
        if current > MIGRATIONS[-1][0]:
            raise RuntimeError("Database schema is newer than this server")
        for version, statements in MIGRATIONS:
            if version <= current:
                continue
            for statement in statements:
                connection.execute(statement)
            connection.execute("INSERT INTO schema_migrations VALUES(?,?)", (version, int(time.time())))
            connection.execute(f"PRAGMA user_version={version}")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
