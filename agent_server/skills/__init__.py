"""Versioned, independently configurable skill contracts."""
import json
from pathlib import Path


CATALOGUE = {item["id"]: item for item in (
    json.loads(path.read_text(encoding="utf-8")) for path in sorted(Path(__file__).parent.glob("*.json"))
)}
GUARDIANS = {"boundary-guardian", "human-handoff"}


def catalogue(settings):
    disabled = settings.get("disabled_skills", [])
    return [dict(item, enabled=item["id"] not in disabled or item["id"] in GUARDIANS)
            for item in CATALOGUE.values()]


def instructions(skill_id, settings):
    if skill_id not in CATALOGUE:
        raise ValueError("unknown skill")
    if skill_id in settings.get("disabled_skills", []) and skill_id not in GUARDIANS:
        raise ValueError("skill disabled")
    style = settings.get("personal_style", {})
    return CATALOGUE[skill_id]["instructions"] + "\n用户确认的个人表达偏好：" + json.dumps(style, ensure_ascii=False)
