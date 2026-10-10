"""Download and verify reference files that are not stored in Git.

PDFs are listed in each library's SOURCES.json with their original URL and
SHA-256 but are ignored by Git. This restores any that are missing and checks
the hash of every catalogued file. Run from anywhere:

    python3 tools/fetch_refs.py            # fetch missing files, verify all
    python3 tools/fetch_refs.py --check    # verify only; download nothing

The two C64 book transcriptions are retained in the catalog for provenance
but excluded from both download and verification in the public source tree.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
LIBRARIES = ['common', 'appleII', 'atari', 'c64']
EXCLUDED = {
    'c64/manuals/Commodore_64_Programmers_Reference_Guide.txt',
    'c64/manuals/Mapping_the_Commodore_64.txt',
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def download(url, dest, expected):
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'wizardry-port-fetch/1.0'})
    with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as tmp:
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                while chunk := response.read(1 << 20):
                    tmp.write(chunk)
            tmp.close()
            actual = sha256(tmp.name)
            if actual != expected:
                raise ValueError(f'hash mismatch: got {actual}')
            Path(tmp.name).replace(dest)
        finally:
            Path(tmp.name).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--check', action='store_true', help='verify only; do not download')
    args = parser.parse_args()

    failures = fetched = ok = 0
    for library in LIBRARIES:
        sources = json.loads((ROOT / library / 'SOURCES.json').read_text())
        for entry in sources['documents'] + sources.get('supporting_assets', []):
            if entry['path'] in EXCLUDED:
                continue
            path = ROOT / entry['path']
            if path.exists():
                if sha256(path) == entry['sha256']:
                    ok += 1
                else:
                    print(f'MODIFIED {entry["path"]}')
                    failures += 1
                continue
            # Only unmodified downloads can be restored from their source URL;
            # repaired HTML and other edited files live in Git.
            if entry.get('download_sha256', entry['sha256']) != entry['sha256']:
                print(f'MISSING  {entry["path"]} (locally modified; restore it from Git)')
                failures += 1
            elif args.check:
                print(f'MISSING  {entry["path"]}')
                failures += 1
            else:
                print(f'FETCH    {entry["path"]}', flush=True)
                try:
                    download(entry['url'], path, entry['sha256'])
                    fetched += 1
                except Exception as error:  # report every failure, then exit non-zero
                    print(f'  FAILED: {error}')
                    failures += 1
    print(f'{ok} verified, {fetched} downloaded, {failures} problems')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
