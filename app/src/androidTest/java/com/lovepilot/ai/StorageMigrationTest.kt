package com.lovepilot.ai

import android.content.Context
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test

class StorageMigrationTest {
    @Test fun legacyDataSurvivesEncryptedMigration() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val name = "migration-test-${System.currentTimeMillis()}.db"
        try {
            context.openOrCreateDatabase(name, Context.MODE_PRIVATE, null).use { db ->
                db.execSQL("CREATE TABLE contacts(id INTEGER PRIMARY KEY AUTOINCREMENT,label TEXT NOT NULL UNIQUE,notes TEXT NOT NULL DEFAULT '',consent INTEGER NOT NULL DEFAULT 0)")
                db.execSQL("CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT,contact_id INTEGER NOT NULL,direction TEXT NOT NULL,content TEXT NOT NULL,created_at INTEGER NOT NULL)")
                db.execSQL("CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,status TEXT NOT NULL,detail TEXT NOT NULL,created_at INTEGER NOT NULL)")
                db.execSQL("INSERT INTO contacts(label,notes,consent) VALUES('legacy-private-marker','old-note',1)")
                db.version = 1
            }
            Store(context, name).use { store ->
                assertTrue(store.contacts().contains("legacy-private-marker"))
                store.addContact("legacy-private-marker", "new-note", true)
                val text = store.contacts()
                assertTrue(text.contains("#1"))
                assertTrue(text.contains("new-note"))
                assertFalse(text.contains("old-note"))
                store.log("test-status", "private-event-marker")
                assertTrue(store.history().contains("private-event-marker"))
            }
            val raw = context.getDatabasePath(name).readBytes().toString(Charsets.ISO_8859_1)
            assertFalse(raw.contains("legacy-private-marker"))
            assertFalse(raw.contains("new-note"))
            assertFalse(raw.contains("private-event-marker"))
        } finally { context.deleteDatabase(name) }
    }
}
