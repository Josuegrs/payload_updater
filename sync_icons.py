"""Copy icons from matching entries in the official Payload Manager catalog."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parent
OFFICIAL = 'https://itsplk.github.io/ps5-payloads-mirror/payloads_v2.json'
DISABLED = {'playtime', 'ps5-dualsense-deadzone-1360'}
EXCLUDED_OFFICIAL_SOURCES = {'github.com/itsplk/pldmgr'}
EXCLUDED_OFFICIAL_IDS = {'pldmgr'}

def icons_url(icons):
    content = json.dumps(icons, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return 'icons.json?v=' + hashlib.sha256(content).hexdigest()[:16]


def source_key(url):
    parsed = urlsplit(url if '://' in url else 'https://' + url)
    path = parsed.path.rstrip('/')
    if path.lower().endswith('/releases'):
        path = path[:-len('/releases')]
    if path.lower().endswith('.git'):
        path = path[:-4]
    return (parsed.hostname or '').lower() + path.lower()


def add_missing_payloads(projects, items, official):
    """Append official catalog entries whose source repository is not present locally."""
    known_sources = {source_key(p['base']) for p in projects}
    known_sources.update(source_key(item['source']) for item in items if item.get('source'))
    known_ids = {item['id'] for item in items}
    added = []
    for source_item in official.get('payloads', []):
        source = source_item.get('source')
        if not source:
            continue
        source_id = source_key(source)
        if source_id in known_sources:
            continue
        name = source_item.get('name', '').strip()
        payload_id = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        if (not payload_id or payload_id in known_ids or source_id in EXCLUDED_OFFICIAL_SOURCES
                or payload_id in EXCLUDED_OFFICIAL_IDS):
            continue
        item = dict(source_item)
        item['id'] = payload_id
        item.pop('icon_key', None)
        added.append(item)
        known_ids.add(payload_id)
        known_sources.add(source_key(source))
    items.extend(added)
    return added


def update_readme(items):
    path = ROOT / 'README.md'
    content = path.read_text(encoding='utf-8')
    before, marker, _ = content.partition('## Projects\n')
    if not marker:
        raise ValueError('README.md has no Projects section')
    before = re.sub(r'(?ms)^## Updating\s*\n.*?(?=^## |\Z)', '', before).rstrip()
    rows = []
    for item in items:
        source = item.get('source', '')
        if not source:
            continue
        repo_url = source.rstrip('/')
        if repo_url.lower().endswith('/releases'):
            repo_url = repo_url[:-len('/releases')]
        repo = urlsplit(repo_url).path.strip('/')
        if not repo:
            continue
        name = item.get('name') or item.get('id')
        rows.append((name.casefold(), f'- [{repo.replace("/", " / ")}]({repo_url}) - **{name}**'))
    rows.sort(key=lambda row: (row[0], row[1].casefold()))
    path.write_text(before + '\n\n## Projects\n\n' + '\n'.join(row for _, row in rows) + '\n', encoding='utf-8')


def sync(projects, items, icons, fetch):
    official = fetch(OFFICIAL)
    official_icons = fetch(urljoin(OFFICIAL, official['icons_url']))['icons']
    by_source = {source_key(p['source']): p for p in official['payloads'] if p.get('source')}
    result = {}
    project_map = {p['id']: p for p in projects}
    for item in items:
        project = project_map.get(item['id'], {})
        if item['id'] in DISABLED or project.get('icon') is False:
            item.pop('icon_key', None)
            continue
        old_key = item.get('icon_key', item['id'])
        data = icons.get(old_key) or icons.get(item['id'])
        source = project.get('base')
        match = by_source.get(source_key(source + '/releases')) if source else by_source.get(source_key(item.get('source', '')))
        if match and match.get('icon_key') in official_icons:
            data = official_icons[match['icon_key']]
        if data:
            result[item['id']] = data
            item['icon_key'] = item['id']
        else:
            item.pop('icon_key', None)
    return result


if __name__ == '__main__':
    from update_payloads import get_json
    projects = json.loads((ROOT / 'projects.json').read_text(encoding='utf-8'))
    catalog_path = ROOT / 'payloads-extra.json'
    icons_path = ROOT / 'icons.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    icons = json.loads(icons_path.read_text(encoding='utf-8'))['icons']
    official = get_json(OFFICIAL)
    added = add_missing_payloads(projects, catalog['payloads'], official)
    if added:
        print('Added official payloads: ' + ', '.join(x['name'] for x in added))
    result = sync(projects, catalog['payloads'], icons, lambda url: official if url == OFFICIAL else get_json(url))
    catalog['icons_url'] = icons_url(result)
    icons_path.write_text(json.dumps({'icons': result}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    update_readme(catalog['payloads'])
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Updated {len(result)} icon references')
