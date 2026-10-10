"""Check real MCP stdio endpoints using pipes (no local sockets required)."""
import json
from pathlib import Path
import select
import subprocess

ROOT = Path(__file__).resolve().parent
APPLE_BOOTSTRAP = '''
import { McpServer } from './src/appleii-agent-git/src/mcp-server.js';
import { HttpServer } from './src/appleii-agent-git/src/http-server.js';
await new McpServer(new HttpServer(3033)).start();
'''


def exchange(proc, message):
    proc.stdin.write((json.dumps(message) + '\n').encode())
    proc.stdin.flush()
    if 'id' not in message:
        return
    while True:
        if not select.select([proc.stdout], [], [], 15)[0]:
            raise TimeoutError(message['method'])
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError('MCP server exited')
        reply = json.loads(line)
        if reply.get('id') == message['id']:
            if 'error' in reply:
                raise RuntimeError(reply['error'])
            return reply['result']


results = []
for name, args, tool, arguments in [
    ('vice', ['src/vice-mcp/dist/index.js'], 'status', {}),
    ('apple2-protocol-only', ['--input-type=module', '-e', APPLE_BOOTSTRAP], 'server_control', {'action': 'status'}),
]:
    with (ROOT / 'logs' / f'{name}-protocol.log').open('w') as errors:
        proc = subprocess.Popen(['node', *args], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, bufsize=0)
        try:
            init = exchange(proc, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
                'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'wizardry-install-check', 'version': '1.0'}}})
            exchange(proc, {'jsonrpc': '2.0', 'method': 'notifications/initialized'})
            tools = exchange(proc, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
            status = exchange(proc, {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': tool, 'arguments': arguments}})
            assert not status.get('isError'), status
            results.append({'name': name, 'server': init['serverInfo'], 'tools': [t['name'] for t in tools['tools']], 'status': status})
            print(f"{name}: initialize, {len(tools['tools'])} tools, {tool} OK")
        finally:
            proc.terminate()
            proc.wait(timeout=10)

(ROOT / '../../test-artifacts/emulators/mcp-protocol.json').resolve().write_text(json.dumps(results, indent=2) + '\n')
