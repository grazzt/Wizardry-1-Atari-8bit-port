"""Install pinned npm archives offline after downloading the emitted curl config."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parent
REPOS = [ROOT / 'src/vice-mcp', ROOT / 'src/appleii-agent-git']
CACHE = ROOT / 'downloads/npm'
MANIFEST = ROOT / 'downloads/npm-install.json'

if sys.argv[1] == 'prepare':
    CACHE.mkdir(exist_ok=True)
    entries = []
    for repo in REPOS:
        lock = json.loads((repo / 'package-lock.json').read_text())
        for name, item in lock['packages'].items():
            if not name or not item.get('resolved'):
                continue
            if item.get('os') and 'linux' not in item['os']:
                continue
            if item.get('cpu') and 'x64' not in item['cpu']:
                continue
            url = item['resolved']
            assert url.startswith('https://registry.npmjs.org/'), url
            archive = CACHE / (hashlib.sha256(url.encode()).hexdigest() + '.tgz')
            entries.append(dict(repo=str(repo), path=name, url=url, archive=str(archive), integrity=item['integrity']))
    MANIFEST.write_text(json.dumps(entries, indent=2) + '\n')
    unique = {e['url']: e for e in entries}
    config = '\nnext\n'.join('fail\nlocation\nsilent\nshow-error\nconnect-timeout = 15\nmax-time = 120\nurl = ' + json.dumps(e['url']) + '\noutput = ' + json.dumps(e['archive']) for e in unique.values())
    (ROOT / 'downloads/npm.curl').write_text(config)
    print(f'{len(entries)} installed packages; {len(unique)} downloads')
elif sys.argv[1] == 'install':
    entries = json.loads(MANIFEST.read_text())
    for entry in entries:
        archive = Path(entry['archive'])
        algo, expected = entry['integrity'].split('-', 1)
        actual = base64.b64encode(hashlib.new(algo, archive.read_bytes()).digest()).decode()
        assert actual == expected, f'Integrity failure: {archive}'
        dest = Path(entry['repo']) / entry['path']
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as tf:
            members = []
            for member in tf.getmembers():
                parts = Path(member.name).parts
                if len(parts) < 2:
                    continue
                member.name = str(Path(*parts[1:]))
                members.append(member)
            tf.extractall(dest, members=members, filter='data')
        pkg = json.loads((dest / 'package.json').read_text())
        bins = pkg.get('bin', {})
        if isinstance(bins, str):
            bins = {pkg['name'].split('/')[-1]: bins}
        modules = dest.parent.parent if dest.parent.name.startswith('@') else dest.parent
        for name, target in bins.items():
            bindir = modules / '.bin'
            bindir.mkdir(exist_ok=True)
            link = bindir / name
            if link.is_symlink():
                link.unlink()
            link.symlink_to(os.path.relpath(dest / target, bindir))
            (dest / target).chmod((dest / target).stat().st_mode | 0o111)
    print(f'Installed {len(entries)} packages; all archive integrity checks passed; lifecycle scripts not run.')
