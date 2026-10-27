"""Regenerate the catalog from official GitHub / Forgejo release APIs."""
import hashlib
import argparse
import json
import os
import re
import sys
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

def report_failures(failures):
    if not failures:
        return
    summary = ['## Payload update warnings', '',
               'Some projects could not be refreshed. Previous catalog entries were kept when available.', '']
    for project, error, retained in failures:
        detail = f"{project['name']} ({project['base']}): {error}"
        detail = detail.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            print(f'::warning title=Payload update failed::{detail}')
        else:
            print(f'WARNING: {detail}', file=sys.stderr)
        status = 'previous entry retained' if retained else 'no previous entry; omitted from catalog'
        clean_error = str(error).replace('\r', ' ').replace('\n', ' ').replace('|', '\\|')
        summary.append(f"- **{project['name']}** (`{project['id']}`): {clean_error} ({status}).")
    summary.append('')
    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_path:
        with open(summary_path, 'a', encoding='utf-8') as output:
            output.write('\n'.join(summary) + '\n')


def build(fetch=get_json, hash_asset=asset_hash, continue_on_error=False):
    projects = json.loads((ROOT / 'projects.json').read_text())
    previous_catalog = json.loads((ROOT / 'payloads-extra.json').read_text())
    icon_catalog_path = ROOT / 'icons.json'
    icon_catalog = json.loads(icon_catalog_path.read_text()) if icon_catalog_path.exists() else {'icons': {}}
    icons = icon_catalog.get('icons', {})
    previous_items = {item['id']: item for item in previous_catalog.get('payloads', [])}
    items = []
    failures = []
    for project in projects:
        try:
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
        except Exception as error:
            if not continue_on_error:
                raise
            retained = project['id'] in previous_items
            if retained:
                items.append(previous_items[project['id']])
            failures.append((project, error, retained))
    from sync_icons import icons_url, sync
    try:
        published_icons = sync(projects, items, icons, fetch)
    except Exception as error:
        print(f'WARNING: official icon sync failed; keeping saved icons: {error}', file=sys.stderr)
        published_icons = sync(projects, items, icons, lambda url: {'payloads': [], 'icons_url': 'icons.json', 'icons': {}})
    icon_catalog_path.write_text(json.dumps({'icons': published_icons}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report_failures(failures)
    return dict(name='PS5 Payload Catalog', icons_url=icons_url(published_icons), payloads=items)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Regenerate the PS5 payload catalog.')
    parser.add_argument('--continue-on-error', action='store_true',
                        help='keep previous entries and continue when an individual project fails')
    args = parser.parse_args()
    result = build(continue_on_error=args.continue_on_error)
    target = ROOT / 'payloads-extra.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(target)
