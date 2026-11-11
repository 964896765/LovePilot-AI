import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from agent_server import control


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / '.env').write_text('LOVEPILOT_PORT=18868\nLOVEPILOT_TOKEN=synthetic-token\n')
        self.stack = contextlib.ExitStack()
        self.stack.enter_context(patch.object(control, '__file__', str(self.root / 'agent_server/control.py')))
        self.stack.enter_context(patch.dict(os.environ, {}, clear=True))
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))

    def tearDown(self):
        self.stack.close()
        self.temp.cleanup()

    def run_control(self, *arguments):
        with patch('sys.argv', ['control', *arguments]):
            control.main()

    def test_port_environment_overrides_local_configuration(self):
        with patch.dict(os.environ, {'LOVEPILOT_PORT': '18869'}), contextlib.redirect_stdout(io.StringIO()) as output:
            self.run_control('--port')
        self.assertEqual(output.getvalue().strip(), '18869')

    def test_http_rejection_is_reported_and_watcher_keeps_running(self):
        for status in (401, 404):
            with self.subTest(status=status), patch.object(control.urllib.request, 'urlopen',
                    side_effect=HTTPError('http://localhost', status, 'rejected', {}, None)):
                with self.assertRaisesRegex(RuntimeError, 'HTTP ' + str(status)):
                    self.run_control('--stop')
                self.assertFalse((self.root / 'data/agent.stop').exists())

    def test_unreachable_service_stops_watcher(self):
        with patch.object(control.urllib.request, 'urlopen', side_effect=URLError('connection refused')):
            self.run_control('--stop')
        self.assertTrue((self.root / 'data/agent.stop').exists())

    def test_graceful_shutdown_waits_for_configured_port(self):
        with patch.object(control.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"ok":true}')) as request, \
                patch.object(control.socket, 'create_connection', side_effect=ConnectionRefusedError) as connection:
            self.run_control('--stop')
        self.assertEqual(request.call_args.args[0].full_url, 'http://127.0.0.1:18868/admin/shutdown')
        connection.assert_called_once_with(('127.0.0.1', 18868), timeout=0.3)
        self.assertTrue((self.root / 'data/agent.stop').exists())
