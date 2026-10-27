"""Regenerate the catalog from official GitHub / Forgejo release APIs."""
import hashlib
import argparse
import base64
import io
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent

def get_json(url):
    headers = {'Accept': 'application/json', 'User-Agent': 'PS5-Catalog-Updater'}
    if urlsplit(url).hostname == 'api.github.com' and os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    with urlopen(Request(url, headers=headers), timeout=60) as response:
        return json.load(response)

def get_bytes(url, limit=2 * 1024 * 1024):
    headers = {'User-Agent': 'PS5-Catalog-Updater'}
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Icon source exceeds 2 MiB')
    return data

def image_data_uri(data, path):
    suffix = Path(path).suffix.lower()
    mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml'}.get(suffix)
    if not mime:
        return None
    if mime == 'image/png' and not data.startswith(b'\x89PNG\r\n\x1a\n'):
        return None
    if mime == 'image/jpeg' and not data.startswith(b'\xff\xd8\xff'):
        return None
    if mime == 'image/svg+xml':
        if (b'<svg' not in data[:2048].lower() or re.search(
                br'<\s*(script|foreignObject)\b|\bon\w+\s*=|javascript:|\bhref\s*=|url\s*\(', data, re.I)):
            return None
    encoded = base64.b64encode(data).decode('ascii')
    value = f'data:{mime};base64,{encoded}'
    if len(value) <= 12288:
        return value
    if mime not in {'image/png', 'image/jpeg'}:
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        image = Image.open(io.BytesIO(data))
        image.thumbnail((128, 128), Image.Resampling.LANCZOS)
        for size in (128, 96, 64, 48, 32, 16):
            if image.width > size or image.height > size:
                image.thumbnail((size, size), Image.Resampling.LANCZOS)
            variants = [image]
            if mime == 'image/png' and image.mode not in ('P', 'L'):
                for colors in (128, 64, 32, 16):
                    variants.append(image.quantize(colors=colors, method=Image.Quantize.FASTOCTREE))
            for variant in variants:
                output = io.BytesIO()
                if mime == 'image/jpeg':
                    variant.convert('RGB').save(output, format='JPEG', quality=72, optimize=True)
                else:
                    variant.save(output, format='PNG', optimize=True)
                encoded = base64.b64encode(output.getvalue()).decode('ascii')
                value = f'data:{mime};base64,{encoded}'
                if len(value) <= 12288:
                    return value
    except Exception:
        return None
    return None

def compress_data_uri(value):
    if not isinstance(value, str) or ',' not in value:
        return None
    prefix, encoded = value.split(',', 1)
    if len(value) <= 12288:
        return value
    suffix = {'data:image/png;base64': '.png', 'data:image/jpeg;base64': '.jpg'}.get(prefix)
    if not suffix:
        return None
    try:
        return image_data_uri(base64.b64decode(encoded, validate=True), suffix)
    except Exception:
        return None

def fetch_explicit_icon(url):
    """Fetch an explicitly configured image, including GitHub blob URLs."""
    parsed = urlsplit(url)
    path = parsed.path
    parts = path.split('/')
    if parsed.netloc.lower() == 'github.com' and len(parts) >= 6 and parts[3] == 'blob':
        repo = '/'.join(parts[1:3])
        branch = parts[4]
        file_path = '/'.join(parts[5:])
        url = f'https://raw.githubusercontent.com/{repo}/{quote(branch, safe="")}/{quote(file_path, safe="/")}'
        path = file_path
    data = image_data_uri(get_bytes(url), path)
    if not data:
        raise ValueError(f'Unsupported or oversized icon image: {urlsplit(url).path}')
    return data

def discover_icon(project, fetch=get_json):
    """Find a small icon image in the payload's own repository."""
    if project.get('icon') is False:
        return None
    if project.get('icon_url'):
        return fetch_explicit_icon(project['icon_url'])
    base = project['base']
    host = urlsplit(base).netloc
    repo = project['repo']
    api = ('https://api.github.com/repos/' + repo if project['host'] == 'github'
           else f'https://{host}/api/v1/repos/{repo}')
    metadata = fetch(api)
    branch = metadata.get('default_branch') or 'main'
    tree_url = (f'{api}/git/trees/{quote(branch, safe="")}?recursive=1')
    tree = fetch(tree_url)
    entries = tree.get('tree', []) if isinstance(tree, dict) else []
    candidates = []
    for entry in entries:
        path = entry.get('path', '')
        name = Path(path).name.lower()
        if Path(path).suffix.lower() not in {'.png', '.jpg', '.jpeg', '.svg'}:
            continue
        if any(word in name for word in ('badge', 'screenshot', 'screen-shot', 'banner', 'background', 'cover')):
            continue
        score = 0
        if any(word in name for word in ('icon', 'logo', 'app-icon', 'app_icon')):
            score += 100
        if any(word in path.lower() for word in ('/icon', '/logo', 'icons/')):
            score += 30
        if name in {'icon.png', 'logo.png', 'icon.svg', 'logo.svg', 'app.png'}:
            score += 20
        if path.count('/') == 0:
            score += 5
        candidates.append((score, path))
    candidates.sort(key=lambda item: (-item[0], len(item[1]), item[1].lower()))
    for _, path in candidates[:6]:
        if project['host'] == 'github':
            url = f'https://raw.githubusercontent.com/{repo}/{quote(branch, safe="")}/{quote(path, safe="/")}'
        else:
            url = f'https://{host}/{repo}/raw/branch/{quote(branch, safe="")}/{quote(path, safe="/")}'
        try:
            icon = image_data_uri(get_bytes(url), path)
            if icon:
                return icon
        except Exception:
            continue
    return None

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
    # Keep stable payload IDs as icon keys. Changing keys invalidates Payload
    # Manager's per-source icon cache and is unnecessary for catalog lookup.
    published_icons = {}
    previous_items = {item['id']: item for item in previous_catalog.get('payloads', [])}
    icon_by_project = {}
    for project in projects:
        previous = previous_items.get(project['id'], {})
        previous_key = previous.get('icon_key', project['id'])
        previous_data = compress_data_uri(icons.get(previous_key) or icons.get(project['id']))
        if project.get('keep_icon'):
            icon_by_project[project['id']] = previous_data
            continue
        if project.get('icon') is False:
            icon_by_project[project['id']] = None
            continue
        try:
            icon_by_project[project['id']] = discover_icon(project) or previous_data
        except Exception as error:
            icon_by_project[project['id']] = previous_data
            print(f"WARNING: icon lookup failed for {project['name']}: {error}", file=sys.stderr)
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
    for item in items:
        data = icon_by_project.get(item['id'])
        if data:
            published_icons[item['id']] = data
            item['icon_key'] = item['id']
        else:
            item.pop('icon_key', None)
    icon_catalog_path.write_text(json.dumps({'icons': published_icons}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report_failures(failures)
    # Bump the icon catalog URL to invalidate Payload Manager's separate icon cache.
    return dict(name='PS5 Payload Catalog', icons_url='icons.json?v=2', payloads=items)

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
