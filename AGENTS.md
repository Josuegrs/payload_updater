# Repository instructions

This repository publishes a public PS5 Payload Manager catalog. Keep all public content free of the repository owner's personal name or identifying attribution. Automated commits may use the GitHub Actions bot identity.

## Sources of truth

- `projects.json` is the source of truth for the 37 catalog entries and their release selectors. Preserve the entry count, stable unique `id` values, repository coordinates, asset patterns, descriptions, and categories unless the task explicitly changes them.
- `update_payloads.py` fetches official GitHub or Forgejo releases and regenerates `payloads-extra.json`. Prefer changing the selectors or generator and then regenerating the catalog over hand-editing generated rows.
- `payloads-extra.json` is generated output. It must contain one row per project, with matching `id`, version/tag, official asset URLs, publication date, SHA-256 checksum, and `icon_key` equal to the project `id`.
- `icons.json` maps the 37 project IDs to their embedded icons. Keep icon IDs aligned with `projects.json` and catalog `icon_key` values.

## Release selection and catalog integrity

- Include pre-releases as well as stable releases. Exclude draft releases. Select the newest published release by `published_at` among eligible releases.
- Asset patterns in `projects.json` must select exactly one downloadable asset from each selected release. Do not weaken a selector just to make a failed update pass; investigate the upstream release and adjust the selector deliberately.
- Keep each catalog `url` and `source_direct` tied to the selected official release asset, and `source` tied to the project's releases page. Keep `version` and `last_update` tied to that same release.
- Store lowercase, 64-character hexadecimal SHA-256 checksums for the exact selected asset. Use the upstream SHA-256 digest when supplied; otherwise calculate it from the downloaded asset.
- Preserve the catalog's established JSON shape and encoding. Do not add personal names or attribution to public descriptions or metadata.

## GitHub Actions and local changes

- `.github/workflows/main.yml` runs hourly and supports manual dispatch. It runs `update_payloads.py` and stages only `payloads-extra.json` for its automated commit.
- The workflow uses the `payload-catalog` concurrency group to serialize workflow runs, then rebases its generated commit on `origin/main` before pushing. It does not serialize against a developer's local edits or push.
- Avoid concurrent edits to `payloads-extra.json` while the workflow is running. Changes to `projects.json`, `update_payloads.py`, or `icons.json` should be pushed before starting a catalog workflow run, so its checkout and generated output use the intended definitions. If a rebase or push fails, reconcile against the latest `main`, regenerate, and review the complete diff before retrying.
- Before changing the workflow or generated files, inspect `git status` and the branch/upstream state. Preserve unrelated local work.
- After completing a requested change and passing its relevant checks, if the user's request mentions the word `push`, commit and push the task's changes to `origin main`. Include only changes belonging to that task; leave unrelated local changes untouched. Integrate remote changes before pushing, and never use force push.

## Validation expectations

For catalog or selector changes, check that there are 37 unique project IDs, all 37 appear exactly once in `payloads-extra.json`, and all 37 have matching icon entries and `icon_key` values. Check that every checksum is valid SHA-256 hex and each catalog row's version, URLs, filename, and date refer to the same selected release asset.
