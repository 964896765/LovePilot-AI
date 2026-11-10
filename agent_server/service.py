"""Application operations shared by the Android client and Bot bridge."""
import os
import time

from .models import validate_base_url
from .security import decrypt_backup, encrypt_backup
from .skills import CATALOGUE, GUARDIANS, catalogue
from .astrbot_admin import AstrBotAdmin


def text(data, key, maximum, required=True):
    value = data.get(key, "")
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError("invalid " + key)
    return value


class Service:
    def __init__(self, memory, agent, semantic):
        self.memory, self.agent, self.semantic = memory, agent, semantic
        self.started_at = int(time.time())
        self.bot_admin = AstrBotAdmin()

    def get(self, path, query):
        cid = query.get("contact_id", [None])
        if len(cid) != 1:
            raise ValueError("one contact_id required")
        cid = cid[0]
        if path == "/contacts":
            return {"contacts": self.memory.contacts()}
        if path == "/skills":
            items = catalogue(self.memory.settings())
            return {"skills": {item['id']: item['instructions'] for item in items}, "items": items}
        if path == "/memory":
            if not cid or not self.memory.contact(cid):
                raise KeyError("contact not found")
            return {"facts": self.memory.facts(cid), "history": self.memory.history(cid),
                    "items": self.memory.fact_details(cid), "candidates": self.memory.candidates(cid)}
        if path == "/candidates":
            return {"candidates": self.memory.candidates(cid)}
        if path == "/runs":
            return {"runs": self.memory.runs(cid)}
        if path == "/logs":
            return {"logs": self.memory.logs()}
        if path == "/settings":
            values = self.memory.settings()
            values.pop("model_api_key", None)
            config = self.agent.model_client.config()
            values.update(model_base_url=config['base_url'], model_name=config['model'],
                          model_key_configured=bool(config['api_key']))
            return values
        if path == "/status":
            self.semantic.start()
            with self.memory.lock:
                schema = self.memory.db.execute("PRAGMA user_version").fetchone()[0]
                counts = {table: self.memory.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                          for table in ("contacts", "messages", "facts", "runs")}
            return {"version": "2.0.0-dev", "started_at": self.started_at, "database_version": schema,
                    "counts": counts, "model_configured": bool(self.agent.model_client.config()['api_key']),
                    "memory_status": self.semantic.status, "memory_error_type": self.semantic.error_type,
                    "workflow": [name for name in self.agent.graph.get_graph().nodes if not name.startswith('__')],
                    "field_encryption": bool(self.memory.vault)}
        if path == "/bot/status":
            settings = self.memory.settings()
            seen = settings.get("bot_last_seen", 0)
            return {"state": "recent_event" if time.time() - seen < 120 else "waiting",
                    "last_seen": seen, "auto_reply_enabled": settings.get("auto_reply_enabled", False),
                    "login_owner": "AstrBot WebUI", "adapter": "weixin_oc"}
        if path == "/bot/permit":
            contact = self.memory.contact(cid)
            return {"consent": bool(contact and contact[2]),
                    "auto_reply_enabled": self.memory.settings().get("auto_reply_enabled", False)}
        if path == "/memory/search":
            message = query.get("q", [""])[0]
            if not cid or not self.memory.contact(cid):
                raise KeyError("contact not found")
            if not self.memory.contact(cid)[2]:
                raise PermissionError("contact consent required")
            matches = self.semantic.search(cid, message)
            return {"results": matches, "method": "mem0" if self.semantic.status == 'ready' else "unavailable"}
        raise KeyError("not found")

    def settings(self, values):
        allowed = {"model_base_url", "model_name", "model_api_key", "auto_reply_enabled", "disabled_skills", "personal_style", "astrbot_url"}
        if set(values) - allowed:
            raise ValueError("unknown settings")
        for key in ("model_base_url", "astrbot_url"):
            if key in values:
                validate_base_url(values[key])
        for key in ("model_name", "model_api_key"):
            if key in values:
                text(values, key, 4096, required=False)
        if 'auto_reply_enabled' in values and type(values['auto_reply_enabled']) is not bool:
            raise ValueError('invalid switch')
        if 'disabled_skills' in values:
            disabled = values['disabled_skills']
            if not isinstance(disabled, list) or any(item not in CATALOGUE or item in GUARDIANS for item in disabled):
                raise ValueError('invalid disabled skills')
        if 'personal_style' in values:
            style = values['personal_style']
            choices = {'length': {'简短', '适中'}, 'tone': {'口语', '温和', '正式'},
                       'humor': {'少量', '关闭'}, 'flirting': {'克制', '关闭'}, 'questions': {'最多一个', '避免追问'}}
            if not isinstance(style, dict) or any(key not in choices or value not in choices[key] for key, value in style.items()):
                raise ValueError('invalid personal style')
        self.memory.update_settings(values)
        self.semantic.start()
        return {"ok": True}

    def post(self, path, data):
        if path == '/bot/login/start':
            return self.bot_admin.start_login()
        if path == '/bot/login/poll':
            return self.bot_admin.poll_login(text(data, 'session_id', 100))
        if path == '/model/test':
            sample = self.agent.model_client.complete('请输出 JSON 对象，reply 字段为一句连接成功提示。', [{'role': 'user', 'content': '测试连接'}])
            if not isinstance(sample, str) or not sample.strip():
                raise ValueError('invalid model response')
            return {'ok': True}
        if path == '/settings':
            return self.settings(data)
        if path == '/backup':
            return encrypt_backup(self.memory.backup_document(), text(data, 'password', 1024))
        if path == '/restore':
            if data.get('confirm') != 'RESTORE':
                raise ValueError('restore confirmation required')
            document = decrypt_backup(data.get('backup', {}), text(data, 'password', 1024))
            count = self.memory.restore_document(document)
            return {'ok': True, 'restored_contacts': count, 'consent_required': True}
        if path == '/data/delete':
            if data.get('confirm') != 'DELETE_ALL':
                raise ValueError('delete confirmation required')
            for cid in self.memory.erase_personal_data():
                self.semantic.sync(cid)
            return {'ok': True}
        if path == '/bot/heartbeat':
            self.memory.update_settings({'bot_last_seen': int(time.time())})
            return {'ok': True}
        cid = text(data, 'contact_id', 100)
        if path == '/contacts':
            consent = data.get('consent', False)
            if type(consent) is not bool:
                raise ValueError('consent must be boolean')
            self.memory.upsert(cid, text(data, 'alias', 100, False), consent, text(data, 'notes', 2000, False))
            self.semantic.sync(cid)
            return {'ok': True}
        if path == '/draft':
            message = text(data, 'message', 4000)
            mid = data.get('message_id')
            if mid is not None:
                text(data, 'message_id', 120)
            skill = data.get('skill')
            if skill is not None and skill not in CATALOGUE:
                raise ValueError('invalid skill')
            if data.get('source') == 'bot' and not self.memory.settings().get('auto_reply_enabled', False):
                return {'action': 'paused', 'reason': 'Bot 自动回复已暂停'}
            return self.agent.decide(cid, message, mid, skill=skill)
        if not self.memory.contact(cid):
            raise KeyError('contact not found')
        if path == '/facts':
            self.memory.set_fact(cid, text(data, 'key', 60), text(data, 'value', 500))
            self.semantic.sync(cid)
            return {'ok': True}
        if path == '/facts/delete':
            self.memory.delete_fact(cid, text(data, 'key', 60))
            self.semantic.sync(cid)
            return {'ok': True}
        if path == '/candidates/confirm':
            if type(data.get('approve')) is not bool:
                raise ValueError('approve must be boolean')
            self.memory.confirm_candidate(cid, text(data, 'candidate_id', 64), data['approve'])
            self.semantic.sync(cid)
            return {'ok': True}
        if path == '/revoke':
            self.memory.revoke(cid)
            self.semantic.sync(cid)
            return {'ok': True, 'consent': False}
        if path == '/export':
            return self.memory.export(cid)
        if path == '/delete':
            self.memory.delete(cid)
            self.semantic.sync(cid)
            return {'ok': True}
        raise KeyError('not found')
