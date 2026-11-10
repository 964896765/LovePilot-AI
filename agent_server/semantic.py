"""Derived Mem0 index. Confirmed SQLite facts remain the durable source of truth."""
import logging
import os
import threading
import time

from .mem0_adapter import Mem0Adapter

logger = logging.getLogger(__name__)


class SemanticMemory:
    def __init__(self, storage, config):
        self.storage = storage
        self.config = config
        self.adapter = None
        self.status = "not_configured"
        self.error_type = None
        self.lock = threading.RLock()
        self.last_attempt = 0
        self.closed = False

    def start(self):
        with self.lock:
            if self.closed or self.status in ("loading", "ready"):
                return
            if time.monotonic() - self.last_attempt < 30:
                return
            key = self.config().get("api_key")
            if not key:
                return
            self.status = "loading"
            self.last_attempt = time.monotonic()
        threading.Thread(target=self._load, name="lovepilot-memory", daemon=True).start()

    def _load(self):
        try:
            from qdrant_client import QdrantClient
            config = self.config()
            os.environ.setdefault("MEM0_TELEMETRY", "false")
            adapter = Mem0Adapter({
                "embedder": {"provider": "fastembed", "config": {
                    "model": "BAAI/bge-small-zh-v1.5", "embedding_dims": 512,
                }},
                "llm": {"provider": "openai", "config": {
                    "api_key": config["api_key"], "openai_base_url": config["base_url"],
                    "model": config["model"],
                }},
                "vector_store": {"provider": "qdrant", "config": {
                    "client": QdrantClient(":memory:"), "embedding_model_dims": 512,
                }},
                "history_db_path": ":memory:",
            })
            with self.lock:
                if self.closed:
                    adapter.memory.vector_store.client.close()
                    adapter.memory.db.close()
                    return
                if self.adapter:
                    self.adapter.memory.vector_store.client.close()
                    self.adapter.memory.db.close()
                self.adapter = adapter
                for contact in self.storage.contacts():
                    if contact["consent"]:
                        self._sync(contact["contact_id"])
                self.status = "ready"
                self.error_type = None
        except Exception as exc:
            logger.warning("Memory index failed type=%s", type(exc).__name__)
            with self.lock:
                if self.adapter:
                    self.adapter.memory.vector_store.client.close()
                    self.adapter.memory.db.close()
                    self.adapter = None
                self.status, self.error_type = "unavailable", type(exc).__name__

    def _sync(self, cid):
        self.adapter.delete_contact(cid)
        contact = self.storage.contact(cid)
        if contact and contact[2]:
            for key, value in self.storage.facts(cid).items():
                self.adapter.add_consented_fact(cid, key + " " + value, consent=True)

    def sync(self, cid):
        with self.lock:
            if self.status == "ready":
                try:
                    self._sync(cid)
                except Exception as exc:
                    self.status, self.error_type = 'unavailable', type(exc).__name__
                    logger.warning('Memory index update failed type=%s', self.error_type)

    def search(self, cid, query):
        with self.lock:
            if self.status != "ready":
                return []
            contact = self.storage.contact(cid)
            if not contact or not contact[2]:
                return []
            allowed = {key + " " + value for key, value in self.storage.facts(cid).items()}
            try:
                records = self.adapter.search(cid, query, consent=True).get("results", [])
            except Exception as exc:
                self.status, self.error_type = 'unavailable', type(exc).__name__
                logger.warning('Memory search failed type=%s', self.error_type)
                return []
            return [{"memory": item["memory"], "score": item.get("score", 0)}
                    for item in records if item.get("memory") in allowed]

    def close(self):
        with self.lock:
            self.closed = True
            self.status = 'closed'
            if self.adapter:
                self.adapter.memory.vector_store.client.close()
                self.adapter.memory.db.close()
                self.adapter = None
