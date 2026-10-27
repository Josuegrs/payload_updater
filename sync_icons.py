"""Copy icons from matching entries in the official Payload Manager catalog."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent
OFFICIAL = 'https://itsplk.github.io/ps5-payloads-mirror/payloads_v2.json'
DISABLED = {'orbit-store-ps5', 'playtime', 'ps5-dualsense-deadzone-1360', 'elf-arsenal'}

def icons_url(icons):
    content = json.dumps(icons, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return 'icons.json?v=' + hashlib.sha256(content).hexdigest()[:16]


def sync(projects, items, icons, fetch):
    official = fetch(OFFICIAL)
    official_icons = fetch(urljoin(OFFICIAL, official['icons_url']))['icons']
    by_source = {p['source'].rstrip('/').lower(): p for p in official['payloads'] if p.get('source')}
    result = {}
    project_map = {p['id']: p for p in projects}
    for item in items:
        project = project_map[item['id']]
        if item['id'] in DISABLED or project.get('icon') is False:
            item.pop('icon_key', None)
            continue
        old_key = item.get('icon_key', item['id'])
        data = icons.get(old_key) or icons.get(item['id'])
        match = by_source.get((project['base'] + '/releases').rstrip('/').lower())
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
    result = sync(projects, catalog['payloads'], icons, get_json)
    catalog['icons_url'] = icons_url(result)
    icons_path.write_text(json.dumps({'icons': result}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Updated {len(result)} icon references')
