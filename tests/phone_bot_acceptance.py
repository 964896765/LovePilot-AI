"""Opt-in official QR acceptance through the installed app and Android UI."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--serial', required=True)
    parser.add_argument('--directory', required=True)
    arguments = parser.parse_args()
    directory = Path(arguments.directory)
    directory.mkdir(parents=True, exist_ok=True)
    command = ['adb', '-s', arguments.serial]

    def adb(*parts):
        return subprocess.check_output(command + list(parts), timeout=20)

    def find_node(label):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            adb('shell', 'uiautomator', 'dump', '--compressed', '/sdcard/lovepilot-acceptance.xml')
            document = adb('exec-out', 'cat', '/sdcard/lovepilot-acceptance.xml')
            for node in ET.fromstring(document).iter('node'):
                if label in (node.get('text'), node.get('content-desc')) and node.get('enabled') == 'true':
                    return node
            time.sleep(0.5)
        raise AssertionError('UI element did not appear: ' + label)

    def click(label):
        node = find_node(label)
        left, top, right, bottom = map(int, re.findall(r'\d+', node.attrib['bounds']))
        adb('shell', 'input', 'tap', str((left + right) // 2), str((top + bottom) // 2))

    started = time.monotonic()
    adb('shell', 'am', 'start', '-n', 'com.lovepilot.ai/.MainActivity')
    try:
        click('管理 Bot →')
        click('获取官方登录二维码')
        find_node('微信官方登录二维码')
        screenshot = directory / 'official-qr-device.png'
        screenshot.write_bytes(adb('exec-out', 'screencap', '-p'))
        result = {'official_qr_rendered': True, 'upstream': 'official AstrBot + Tencent iLink',
                  'elapsed_seconds': round(time.monotonic() - started, 3),
                  'account_login_verified': False, 'message_delivery_verified': False}
        (directory / 'bot-qr-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))
    finally:
        adb('shell', 'rm', '-f', '/sdcard/lovepilot-acceptance.xml')


if __name__ == '__main__':
    main()
