"""Isolated device-test backend. Only the external LLM response is a fixture."""
import argparse
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    arguments = parser.parse_args()
    directory = Path(arguments.directory)
    directory.mkdir(parents=True, exist_ok=True)
    stop = directory / 'phone-stop'
    stop.unlink(missing_ok=True)
    token = secrets.token_urlsafe(32)
    model_calls = []

    class ModelFixture(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert payload['messages'][-1]['role'] == 'user'
            model_calls.append(1)
            content = json.dumps({'reply': '听起来很有意思，你最近看了哪部电影？',
                                  'analysis': {'expression_cues': ['原话主动分享'], 'uncertain': True}}, ensure_ascii=False)
            response = json.dumps({'choices': [{'message': {'content': content}}]}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, *_):
            pass

    with tempfile.TemporaryDirectory(prefix='lovepilot-phone-test-') as temporary:
        os.environ['LOVEPILOT_DB'] = str(Path(temporary) / 'phone.sqlite')
        os.environ['LOVEPILOT_TOKEN'] = token
        os.environ['MEM0_TELEMETRY'] = 'false'
        from agent_server import server
        model = ThreadingHTTPServer(('127.0.0.1', 0), ModelFixture)
        server.memory.update_settings({'model_api_key': 'synthetic-phone-test-key',
            'model_base_url': 'http://127.0.0.1:' + str(model.server_port), 'model_name': 'fixture-model'})
        api = server.AgentHTTPServer(('127.0.0.1', 8870))
        workers = [threading.Thread(target=model.serve_forever), threading.Thread(target=api.serve_forever)]
        for worker in workers:
            worker.start()
        server.semantic.start()
        deadline = time.monotonic() + 120
        while server.semantic.status == 'loading' and time.monotonic() < deadline:
            time.sleep(0.2)
        ready = directory / 'phone-ready.json'
        ready.write_text(json.dumps({'token': token, 'memory_status': server.semantic.status}), encoding='utf-8')
        print('PHONE_FIXTURE_READY memory=' + server.semantic.status, flush=True)
        try:
            while not stop.exists():
                time.sleep(0.2)
        finally:
            api.shutdown()
            model.shutdown()
            for worker in workers:
                worker.join()
            api.server_close()
            model.server_close()
            summary = {'external_llm': 'fixture', 'actual_model_http_calls': len(model_calls),
                       'actual_mem0_status': server.semantic.status,
                       'contacts': len(server.memory.contacts()),
                       'confirmed_facts': server.memory.db.execute('SELECT count(*) FROM facts').fetchone()[0],
                       'runs': server.memory.db.execute('SELECT count(*) FROM runs').fetchone()[0]}
            (directory / 'phone-summary.json').write_text(json.dumps(summary), encoding='utf-8')
            if server.semantic.adapter:
                server.semantic.adapter.memory.vector_store.client.close()
                server.semantic.adapter.memory.db.close()
            server.memory.db.close()
            ready.unlink(missing_ok=True)
            print('PHONE_FIXTURE_STOPPED', flush=True)


if __name__ == '__main__':
    main()
