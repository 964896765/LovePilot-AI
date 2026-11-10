package com.lovepilot.ai

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

/** Version 2 encrypts existing local data without replacing contact IDs. */
class Store(ctx: Context, name: String = "lovepilot.db") : SQLiteOpenHelper(ctx, name, null, 2) {
    private val secure = SecurePrefs(ctx)
    private var migrated = false

    companion object {
        private val databaseLock = Any()
    }

    private fun seal(value: String): String = "lp1:" + secure.seal(value)
    private fun open(value: String): String {
        require(value.startsWith("lp1:")) { "本地数据库需要迁移或恢复" }
        return secure.unseal(value.removePrefix("lp1:"))
    }

    override fun onConfigure(db: SQLiteDatabase) {
        db.execSQL("PRAGMA secure_delete=ON")
    }

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE contacts(id INTEGER PRIMARY KEY AUTOINCREMENT,label TEXT NOT NULL UNIQUE,notes TEXT NOT NULL DEFAULT '',consent INTEGER NOT NULL DEFAULT 0,label_hash TEXT NOT NULL UNIQUE)")
        db.execSQL("CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT,contact_id INTEGER NOT NULL,direction TEXT NOT NULL,content TEXT NOT NULL,created_at INTEGER NOT NULL)")
        db.execSQL("CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,status TEXT NOT NULL,detail TEXT NOT NULL,created_at INTEGER NOT NULL)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) {
            db.execSQL("ALTER TABLE contacts ADD COLUMN label_hash TEXT")
            val contacts = mutableListOf<Triple<Long, String, String>>()
            db.rawQuery("SELECT id,label,notes FROM contacts", null).use { cursor ->
                while (cursor.moveToNext()) contacts.add(Triple(cursor.getLong(0), cursor.getString(1), cursor.getString(2)))
            }
            contacts.forEach { (id, label, notes) ->
                db.execSQL("UPDATE contacts SET label=?,notes=?,label_hash=? WHERE id=?", arrayOf(seal(label), seal(notes), secure.fingerprint(label), id))
            }
            db.execSQL("CREATE UNIQUE INDEX contacts_label_hash ON contacts(label_hash)")
            val messages = mutableListOf<Pair<Long, String>>()
            db.rawQuery("SELECT id,content FROM messages", null).use { cursor ->
                while (cursor.moveToNext()) messages.add(cursor.getLong(0) to cursor.getString(1))
            }
            messages.forEach { (id, content) -> db.execSQL("UPDATE messages SET content=? WHERE id=?", arrayOf(seal(content), id)) }
            val events = mutableListOf<Triple<Long, String, String>>()
            db.rawQuery("SELECT id,status,detail FROM events", null).use { cursor ->
                while (cursor.moveToNext()) events.add(Triple(cursor.getLong(0), cursor.getString(1), cursor.getString(2)))
            }
            events.forEach { (id, status, detail) -> db.execSQL("UPDATE events SET status=?,detail=? WHERE id=?", arrayOf(seal(status), seal(detail), id)) }
            migrated = true
        }
    }

    override fun onOpen(db: SQLiteDatabase) {
        if (migrated) {
            db.execSQL("VACUUM")
            migrated = false
        }
    }

    fun log(status: String, detail: String) = synchronized(databaseLock) {
        writableDatabase.execSQL("INSERT INTO events(status,detail,created_at) VALUES(?,?,?)", arrayOf(seal(status), seal(detail.take(250)), System.currentTimeMillis()))
    }

    fun addContact(label: String, notes: String, consent: Boolean = false) = synchronized(databaseLock) {
        val db = writableDatabase
        val hash = secure.fingerprint(label)
        db.beginTransaction()
        try {
            val statement = db.compileStatement("UPDATE contacts SET notes=?,consent=? WHERE label_hash=?")
            val updated = statement.use {
                it.bindString(1, seal(notes)); it.bindLong(2, if (consent) 1 else 0); it.bindString(3, hash)
                it.executeUpdateDelete()
            }
            if (updated == 0) db.execSQL("INSERT INTO contacts(label,notes,consent,label_hash) VALUES(?,?,?,?)", arrayOf(seal(label), seal(notes), if (consent) 1 else 0, hash))
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
    }

    fun contacts(): String = synchronized(databaseLock) {
        val output = StringBuilder()
        readableDatabase.rawQuery("SELECT id,label,notes,consent FROM contacts ORDER BY id DESC", null).use { cursor ->
            while (cursor.moveToNext()) output.append("#${cursor.getLong(0)} ${open(cursor.getString(1))} | ${open(cursor.getString(2))} | 授权:${cursor.getInt(3) == 1}\n")
        }
        output.toString().ifBlank { "暂无联系人" }
    }

    fun history(): String = synchronized(databaseLock) {
        val output = StringBuilder()
        readableDatabase.rawQuery("SELECT status,detail FROM events ORDER BY id DESC LIMIT 30", null).use { cursor ->
            while (cursor.moveToNext()) output.append("${open(cursor.getString(0))}：${open(cursor.getString(1))}\n")
        }
        output.toString().ifBlank { "暂无记录" }
    }

    fun clearAll() = synchronized(databaseLock) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            db.delete("messages", null, null)
            db.delete("contacts", null, null)
            db.delete("events", null, null)
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
    }
}
