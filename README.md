# PS5 Payload Catalog

Catálogo público de payloads para **PS5 Payload Manager**. Reúne los datos de lanzamiento y descarga de 37 proyectos en un formato JSON, junto con sus iconos.

## Archivos

| Archivo | Contenido |
| --- | --- |
| [`payloads-extra.json`](payloads-extra.json) | Catálogo generado para importar en PS5 Payload Manager. |
| [`icons.json`](icons.json) | Iconos asociados a los payloads mediante `icon_key`. |
| [`projects.json`](projects.json) | Proyectos incluidos y selectores que identifican sus archivos de lanzamiento. |
| [`update_payloads.py`](update_payloads.py) | Generador que consulta las API oficiales de GitHub y Forgejo. |

## Datos del catálogo

Cada elemento de `payloads-extra.json` incluye:

- `id` y `name`: identificador y nombre del payload.
- `filename`: nombre del archivo descargable.
- `url` y `source_direct`: URL directa al archivo del lanzamiento seleccionado.
- `source`: página de lanzamientos del proyecto de origen.
- `version` y `last_update`: etiqueta y fecha de publicación del lanzamiento.
- `category` y `description`: clasificación y resumen del proyecto.
- `checksum`: SHA-256 del archivo descargable, en hexadecimal minúsculo.
- `icon_key`: clave del icono correspondiente en `icons.json`.

El generador contempla lanzamientos estables y pre-releases, omite borradores y selecciona el lanzamiento publicado más recientemente. Los archivos y el soporte de cada payload dependen de sus respectivos proyectos de origen.

## Actualización automática

GitHub Actions ejecuta la actualización cada hora y también permite iniciarla manualmente desde la pestaña **Actions**. Cuando detecta cambios, actualiza `payloads-extra.json` en la rama `main` mediante una confirmación del bot de GitHub Actions.

## Actualización local

Se requiere Python 3.12 o posterior y acceso a Internet para consultar los lanzamientos y descargar los archivos cuando la API no proporciona su SHA-256.

```bash
python update_payloads.py
```

El comando lee `projects.json` y reemplaza `payloads-extra.json` con el resultado. Para que un proyecto aparezca en el catálogo, añade o ajusta su entrada y selector en `projects.json`, y asegúrate de que haya exactamente un archivo coincidente en el lanzamiento más reciente.

## Contribuciones

Antes de proponer cambios, verifica que:

1. `projects.json`, `payloads-extra.json` e `icons.json` contengan los mismos 37 identificadores únicos.
2. Cada `icon_key` coincida con el identificador del proyecto y exista en `icons.json`.
3. Cada selector encuentre un solo archivo en el lanzamiento elegido.
4. La versión, fecha, nombre de archivo, URL y SHA-256 correspondan al mismo activo oficial.

Consulta [`AGENTS.md`](AGENTS.md) para las instrucciones de mantenimiento del repositorio.
