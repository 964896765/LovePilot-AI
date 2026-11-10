"""Display and poll the official QR login for an operator at the computer."""
import base64
import json
from pathlib import Path
import time

from .astrbot_admin import AstrBotAdmin


def main():
    root = Path(__file__).resolve().parents[1] / 'data/astrbot'
    admin = AstrBotAdmin(root)
    login = admin.start_login()
    image = root / 'ilink-login.png'
    image.write_bytes(base64.b64decode(login['qr_image_base64']))
    print('OFFICIAL_WECHAT_QR_READY ' + str(image), flush=True)
    while time.time() < login['expires_at']:
        status = admin.poll_login(login['session_id'])
        if status['status'] != 'pending':
            (root / 'login-status.json').write_text(json.dumps(status), encoding='utf-8')
            print('OFFICIAL_WECHAT_LOGIN_STATUS ' + status['status'], flush=True)
            return
        time.sleep(2)
    print('OFFICIAL_WECHAT_LOGIN_STATUS expired', flush=True)


if __name__ == '__main__':
    main()
