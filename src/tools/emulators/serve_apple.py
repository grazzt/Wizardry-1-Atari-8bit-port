"""Serve the pinned Apple emulator snapshot and working disks on loopback."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'local/web-a2e'), **kwargs)

    def translate_path(self, path):
        route = unquote(urlsplit(path).path)
        if route.startswith('/wizardry/'):
            name = route.removeprefix('/wizardry/')
            if name in ('wizardry_i_boot.dsk', 'wizardry_i_scenario.dsk'):
                return str(ROOT / 'state/appleII-disks' / name)
            return str(ROOT / 'state/nonexistent')
        return super().translate_path(path)

    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8088)
    args = parser.parse_args()
    with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
        print(f'Apple II: http://127.0.0.1:{args.port}/?disk1=/wizardry/wizardry_i_boot.dsk&disk2=/wizardry/wizardry_i_scenario.dsk&autostart', flush=True)
        print('Select Apple II Plus, enable boot-disk write protection, and connect the agent from its toolbar. Ctrl-C stops the web server.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
