"""Local service lifecycle control with authenticated graceful shutdown."""
import argparse
import json
import os
from pathlib import Path
import socket
import time
import urllib.error
import urllib.request

from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stop', action='store_true')
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    values = dict(dotenv_values(root / '.env'))
    values.update(os.environ)
    token = values.get('LOVEPILOT_TOKEN', '')
    port = int(values.get('LOVEPILOT_PORT', '8768'))
    path = '/admin/shutdown' if options.stop else '/health'
    if options.stop:
        (root / 'data').mkdir(exist_ok=True)
        (root / 'data/agent.stop').touch()
    request = urllib.request.Request('http://127.0.0.1:' + str(port) + path,
        data=json.dumps({'confirm': 'STOP_AGENT'}).encode() if options.stop else None,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.load(response)
    except urllib.error.URLError:
        if options.stop:
            print('Agent is not reachable. Watcher stop requested.')
            return
        raise
    if not options.stop:
        print(json.dumps(result))
        return
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.3):
                pass
        except OSError:
            print('Agent stopped gracefully.')
            return
        time.sleep(0.5)
    raise RuntimeError('Agent shutdown did not finish within 60 seconds')


if __name__ == '__main__':
    main()
