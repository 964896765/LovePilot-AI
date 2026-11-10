"""Create local configuration without overwriting existing credentials."""
import os
from pathlib import Path
import secrets


def main():
    root = Path(__file__).resolve().parents[1]
    destination = root / '.env'
    if destination.exists():
        print('Existing .env preserved.')
        return
    values = {
        'LOVEPILOT_TOKEN': secrets.token_urlsafe(36),
        'LOVEPILOT_BOT_TOKEN': secrets.token_urlsafe(36),
        'LOVEPILOT_READ_TOKEN': secrets.token_urlsafe(36),
        'LOVEPILOT_DB': './data/lovepilot.sqlite3',
        'DEEPSEEK_API_KEY': '',
        'DEEPSEEK_MODEL': 'deepseek-chat',
        'LOVEPILOT_URL': 'http://127.0.0.1:8768',
        'LOVEPILOT_AUTO_REPLY': 'true',
        'LOVEPILOT_TIMEOUT': '50',
        'LOVEPILOT_COOLDOWN_SECONDS': '3',
    }
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
        output.write('\n'.join(key + '=' + value for key, value in values.items()) + '\n')
    print('Local .env created. Configure model credentials from the Android app.')


if __name__ == '__main__':
    main()
