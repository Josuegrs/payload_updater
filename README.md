# PS5 Payload Catalog

Public payload catalog for **PS5 Payload Manager**. It includes 51 projects, their download links, and their icons.

## Disclaimer

This catalog links to third-party projects. I do not create or maintain these projects, and I am not responsible for payload failures, damage, data loss, or any other issues resulting from downloading or using them. Use them at your own risk.

## Files

- [`payloads-extra.json`](payloads-extra.json): catalog to import into PS5 Payload Manager.
- [`icons.json`](icons.json): project icons.
- [`projects.json`](projects.json): list of included projects.
- [`update_payloads.py`](update_payloads.py): updates the catalog from official releases.

## Updating

GitHub Actions updates the catalog automatically every hour.

To update it locally, you need Python 3.12 or later and an internet connection:

```bash
python update_payloads.py
```

The script finds the latest release for each project, retrieves its payload, and updates `payloads-extra.json` with the corresponding version, date, link, and SHA-256 hash.
