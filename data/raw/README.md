# data/raw: fuentes sin procesar

Esta carpeta va vacía en el repositorio (`.gitignore`). Descarga aquí los archivos y luego
etiquétalos una sola vez con `scripts/etiquetar_incidentes.py` (Claude Haiku, Message Batches API).

| Fuente | Qué aporta | Cómo descargar |
|---|---|---|
| Kaggle: Industrial Safety and Health Analytics Database (IHM Stefanini, CC0) | ~400 descripciones de accidentes con riesgo crítico y nivel potencial. **No son datos de Perú**: sirven para poblar el historial y probar el etiquetado. | `kaggle datasets download -d ihmstefanini/industrial-safety-and-health-analytics-database -p data/raw --unzip` (requiere `pip install kaggle` y token en `~/.kaggle/kaggle.json`) o descarga manual desde https://www.kaggle.com/datasets/ihmstefanini/industrial-safety-and-health-analytics-database |
| MINEM: estadística de accidentes mortales en minería | Accidentes mortales por año (2000-2023), por tipo y titular | Descarga manual (PDF/XLSX) desde https://www.minem.gob.pe/_estadistica.php?idSector=1&idEstadistica=12464 |
| MTPE: notificaciones de accidentes de trabajo mortales (SAT) | CSV 2012-2024 con diccionario de datos | https://www.datosabiertos.gob.pe/dataset/notificaciones-de-accidentes-de-trabajo-mortales-fuente-sistema-inform%C3%A1tico-de-accidentes-de |

## Etiquetar

```bash
export ANTHROPIC_API_KEY=...
# Kaggle: solo el sector minero, sin columna id (se numeran las filas)
python scripts/etiquetar_incidentes.py \
  --entrada data/raw/IHMStefanini_industrial_safety_and_health_database_with_accidents_description.csv \
  --columna-texto Description --columna-id "" --columna-fecha Data \
  --filtro "Industry Sector=Mining" --origen kaggle \
  --database-url postgresql://vigia:vigia_local@localhost:5433/operacion
```

Revisa los nombres exactos de columnas del CSV descargado antes de correrlo: la ficha de Kaggle
lista `Data, Countries, Local, Industry Sector, Accident Level, Potential Accident Level, Genre,
Employee or Third Party, Critical Risk, Description`.
