"""P0 opt-in notification probe using an already authorized controlled Bot peer."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET

from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--serial', required=True)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--send-test', action='store_true')
    options = parser.parse_args()
    directory = Path(options.directory)
    directory.mkdir(parents=True, exist_ok=True)
    command = ['adb', '-s', options.serial]

    def adb(*arguments):
        with (directory / 'notification-adb.stderr.log').open('ab') as errors:
            return subprocess.check_output(command + list(arguments), stderr=errors, timeout=20)

    def click(label):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            adb('shell', 'uiautomator', 'dump', '--compressed', '/sdcard/lovepilot-notification-test.xml')
            xml = adb('exec-out', 'cat', '/sdcard/lovepilot-notification-test.xml')
            root = ET.fromstring(xml)
            parents = {child: parent for parent in root.iter() for child in parent}
            for node in root.iter('node'):
                if label not in (node.get('text'), node.get('content-desc')):
                    continue
                collapsed_label = node.get('bounds') == '[0,0][0,0]'
                while node is not None and node.tag == 'node':
                    left, top, right, bottom = map(int, re.findall(r'\d+', node.attrib['bounds']))
                    if (node.get('clickable') == 'true' or collapsed_label) and node.get('enabled') == 'true' and right > left and bottom > top:
                        adb('shell', 'input', 'tap', str((left + right) // 2), str((top + bottom) // 2))
                        return
                    node = parents.get(node)
            time.sleep(0.5)
        raise AssertionError('UI element did not appear: ' + label)

    def evidence():
        return json.loads(adb('exec-out', 'run-as', 'com.lovepilot.ai', 'cat', 'files/notification-probe.json'))

    adb('shell', 'am', 'start', '-n', 'com.lovepilot.ai/.MainActivity')
    try:
        click('我的')
        click('微信接入验证')
        click('开始新的通知测试')
        report = evidence()
        if options.send_test:
            if not report.get('listener_connected'):
                click('重新连接监听服务')
                time.sleep(2)
                report = evidence()
            if not report.get('listener_connected'):
                raise RuntimeError('Notification listener is not connected')
            values = dotenv_values('.env')
            port = values.get('LOVEPILOT_PORT', '8768')
            request = urllib.request.Request('http://127.0.0.1:' + port + '/contacts',
                headers={'Authorization': 'Bearer ' + values['LOVEPILOT_TOKEN']})
            with urllib.request.urlopen(request, timeout=10) as response:
                contacts = json.load(response)['contacts']
            from agent_server.astrbot_admin import AstrBotAdmin
            admin = AstrBotAdmin()
            bots = admin.request('GET', '/bots')
            if isinstance(bots, dict):
                bots = bots.get('bots', bots.get('platforms', []))
            bot_ids = {item['id'] for item in bots if item.get('type') == 'weixin_oc'}
            peers = [item['contact_id'] for item in contacts if item['consent'] and
                     any(item['contact_id'].startswith(bot + ':FriendMessage:') for bot in bot_ids)]
            if len(peers) != 1:
                raise RuntimeError('Exactly one opted-in controlled test session is required')
            admin.request('POST', '/im/messages', json={'umo': peers[0], 'message': report['marker']})
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                report = evidence()
                if report.get('notification_seen'):
                    break
                time.sleep(0.5)
            report['controlled_peer_send_accepted'] = True
        report['android_release'] = adb('shell', 'getprop', 'ro.build.version.release').decode().strip()
        report['personal_wechat_delivery_verified'] = False
        (directory / 'personal-wechat-p0.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
    finally:
        adb('shell', 'rm', '-f', '/sdcard/lovepilot-notification-test.xml')


if __name__ == '__main__':
    main()
