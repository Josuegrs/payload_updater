# PS5 Payload Catalog

Catálogo público de payloads para **PS5 Payload Manager**. Incluye 44 proyectos, sus enlaces de descarga y sus iconos.

## Archivos

- [`payloads-extra.json`](payloads-extra.json): catálogo para importar en PS5 Payload Manager.
- [`icons.json`](icons.json): iconos de los proyectos.
- [`projects.json`](projects.json): lista de proyectos incluidos.
- [`update_payloads.py`](update_payloads.py): actualiza el catálogo desde las releases oficiales.

## Actualización

GitHub Actions actualiza el catálogo automáticamente cada hora. También se puede ejecutar manualmente desde la pestaña **Actions**.

Para actualizarlo localmente, necesitas Python 3.12 o posterior y conexión a Internet:

```bash
python update_payloads.py
```

El script busca la release más reciente de cada proyecto, obtiene su payload y actualiza `payloads-extra.json` con la versión, fecha, enlace y SHA-256 correspondientes.
