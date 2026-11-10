"""Prepare and launch the pinned official AstrBot runtime on loopback."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

from dotenv import load_dotenv
from .security import Vault


def credentials(root):
    vault = Vault(root / 'dashboard.key')
    path = root / 'dashboard-credentials.enc'
    if path.exists():
        return json.loads(vault.open(path.read_text(encoding='utf-8')))
    values = {'username': 'astrbot', 'password': secrets.token_urlsafe(24)}
    path.write_text(vault.seal(json.dumps(values)), encoding='utf-8')
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--show-login', action='store_true', help='Display local dashboard login to the operator')
    options = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    load_dotenv(project / '.env')
    root = project / 'data/astrbot'
    root.mkdir(parents=True, exist_ok=True)
    login = credentials(root)
    if options.show_login:
        print('Username', login['username'])
        print('Password', login['password'])
        return
    environment = os.environ.copy()
    environment.update(ASTRBOT_ROOT=str(root), ASTRBOT_DASHBOARD_INITIAL_PASSWORD=login['password'],
                       DASHBOARD_HOST='127.0.0.1', DASHBOARD_PORT='6185',
                       LOVEPILOT_BOT_STATE=str(root / 'data/lovepilot-delivery.sqlite'), PYTHONIOENCODING='utf-8',
                       ASTRBOT_DISABLE_METRICS='1')
    initialized = subprocess.run([sys.executable, '-m', 'astrbot.cli', 'init', '--yes'], cwd=root,
                                 env=environment, capture_output=True, timeout=90)
    if initialized.returncode:
        detail = initialized.stderr.decode('utf-8', errors='replace').replace(login['password'], '[redacted]')
        raise RuntimeError('AstrBot initialization failed. ' + detail[-1500:])
    config_path = root / 'data/cmd_config.json'
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding='utf-8-sig'))
        config['dashboard']['host'] = '127.0.0.1'
        config['log_level'] = 'WARNING'
        config['trace_enable'] = False
        config['disable_metrics'] = True
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    plugin = root / 'data/plugins/astrbot_plugin_lovepilot'
    plugin.mkdir(parents=True, exist_ok=True)
    for name in ('main.py', 'delivery.py', 'metadata.yaml', 'requirements.txt'):
        shutil.copy2(project / 'integrations/astrbot_plugin_lovepilot' / name, plugin / name)
    print('Starting official AstrBot at http://127.0.0.1:6185', flush=True)
    print('Use scripts/Show-Bot-Login.ps1 for the operator login.', flush=True)
    subprocess.run([sys.executable, '-m', 'astrbot.cli', 'run', '--port', '6185'], cwd=root, env=environment, check=True)


if __name__ == '__main__':
    main()
