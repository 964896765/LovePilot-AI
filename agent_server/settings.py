"""Shared validation for live configuration and portable backups."""
from .models import validate_base_url
from .skills import CATALOGUE, GUARDIANS


PORTABLE_SETTINGS = {'model_base_url', 'model_name', 'disabled_skills', 'personal_style'}


def validate_settings(values):
    allowed = PORTABLE_SETTINGS | {'model_api_key', 'auto_reply_enabled', 'astrbot_url', 'processing_paused'}
    if not isinstance(values, dict) or set(values) - allowed:
        raise ValueError('unknown settings')
    for key in ('model_base_url', 'astrbot_url'):
        if key in values:
            validate_base_url(values[key])
    for key in ('model_name', 'model_api_key'):
        if key in values and (not isinstance(values[key], str) or len(values[key]) > 4096):
            raise ValueError('invalid ' + key)
    for key in ('auto_reply_enabled', 'processing_paused'):
        if key in values and type(values[key]) is not bool:
            raise ValueError('invalid switch')
    if 'disabled_skills' in values:
        disabled = values['disabled_skills']
        if not isinstance(disabled, list) or any(not isinstance(item, str) or item not in CATALOGUE or item in GUARDIANS for item in disabled):
            raise ValueError('invalid disabled skills')
    if 'personal_style' in values:
        style = values['personal_style']
        choices = {'length': {'简短', '适中'}, 'tone': {'口语', '温和', '正式'},
                   'humor': {'少量', '关闭'}, 'flirting': {'克制', '关闭'}, 'questions': {'最多一个', '避免追问'}}
        if not isinstance(style, dict) or any(key not in choices or not isinstance(value, str) or value not in choices[key] for key, value in style.items()):
            raise ValueError('invalid personal style')
