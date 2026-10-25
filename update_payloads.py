"""Regenerate the catalog from official GitHub / Forgejo release APIs."""
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent

def get_json(url):
    headers = {'Accept': 'application/json', 'User-Agent': 'PS5-Catalog-Updater'}
    if urlsplit(url).hostname == 'api.github.com' and os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    with urlopen(Request(url, headers=headers), timeout=60) as response:
        return json.load(response)

def asset_hash(asset):
    digest = asset.get('digest') or ''
    if digest.startswith('sha256:'):
        checksum = digest[7:]
    else:
        h = hashlib.sha256()
        with urlopen(asset['browser_download_url'], timeout=120) as response:
            while chunk := response.read(1024 * 1024):
                h.update(chunk)
        checksum = h.hexdigest()
    if not re.fullmatch('[0-9a-f]{64}', checksum):
        raise ValueError('Invalid SHA-256 for ' + asset['name'])
    return checksum

def build(fetch=get_json, hash_asset=asset_hash):
    projects = json.loads((ROOT / 'projects.json').read_text())
    items = []
    for project in projects:
        base = project['base']
        endpoint = ('https://api.github.com/repos/' + project['repo'] if project['host'] == 'github'
                    else 'https://' + urlsplit(base).netloc + '/api/v1/repos/' + project['repo'])
        page = 1
        releases = []
        while True:
            batch = fetch(endpoint + f'/releases?per_page=100&limit=100&page={page}')
            if not isinstance(batch, list):
                raise ValueError('Invalid release response: ' + base)
            releases.extend(r for r in batch if not r.get('draft'))
            if len(batch) < 100:
                break
            page += 1
        if not releases:
            raise ValueError('No releases: ' + base)
        release = max(releases, key=lambda r: r['published_at'])
        assets = [a for a in release['assets'] if re.fullmatch(project['asset_pattern'], a['name'])]
        if len(assets) != 1:
            raise ValueError(f'{base}: expected one matching asset in {release["tag_name"]}; review projects.json')
        asset = assets[0]
        items.append(dict(id=project['id'], name=project['name'], filename=asset['name'],
            url=asset['browser_download_url'], source=base + '/releases', source_direct=asset['browser_download_url'],
            version=release['tag_name'], last_update=release['published_at'][:10],
            category=project['category'], description=project['description'] +
            (' (pre-release / beta)' if release.get('prerelease') else ''), checksum=hash_asset(asset)))
    return dict(name='PS5 Completo — Josué', payloads=items)

if __name__ == '__main__':
    result = build()
    target = ROOT / 'payloads-extra.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(target)
