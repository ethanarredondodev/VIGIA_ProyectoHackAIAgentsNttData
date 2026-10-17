# Vigía

PETAR / IPERC continuo **dinámico** con gemelos digitales para minería peruana (Reto M1),
según el DS 024-2016-EM. Antes de autorizar una tarea, un orquestador consulta en paralelo a
tres agentes, calcula el riesgo con **reglas con base legal** (nunca con el LLM) y decide:

| Nivel | Qué pasa | ¿Llega al supervisor? |
|---|---|---|
| Verde | Se emite el PETAR automáticamente con su checklist IPERC | No |
| Ámbar | Espera la firma del supervisor: aceptar, ajustar o rechazar | Sí, como **revisión** |
| Rojo | La tarea se bloquea; se propone reasignar o esperar | Sí, como **aviso** (sin firma) |
| Verde con trabajo de alto riesgo | Si algún control aplicable tiene `trabajo_alto_riesgo = si` (DS 024-2016-EM arts. 129-130), `requiere_supervisor = true` y va a firma | Sí, como **revisión** |

Al terminar la tarea, el resultado vuelve al historial de incidentes.

## Arquitectura

```
                       ┌──────────────┐  AgentFacts + credencial de la autoridad (Ed25519)
                       │ vigia-nanda  │◄──────────────────────────────┐
                       └──────┬───────┘                               │
  UI / web ──► vigia-ptw ─────┘ resolve                               │
     (CORS)    LangGraph ──┬──► vigia-incidentes ── Postgres `operacion` (incidentes)
               checkpoints │──► vigia-area ──────── Postgres `operacion` (labores, condiciones, clima)
               en Postgres └──► vigia-gemelo (IAM) ─ Postgres `clinica` (solo el gemelo)
```

Grafo de `vigia-ptw` (`agents/ptw/grafo.py`):

```
recibir_solicitud → resolver_agentes (NANDA) → [incidentes ‖ area ‖ gemelo]
→ calcular_riesgo (reglas) → armar_checklist (controles_iperc) → redactar_explicacion (Claude Sonnet)
→ enrutar_por_nivel: verde sin alto riesgo → emitir_petar
                     ámbar o requiere_supervisor → esperar_firma (interrupt)
                     rojo → bloquear_y_avisar → fin
→ registrar_resultado (interrupt hasta que llega el resultado)
```

- **Zona clínica aislada**: `vigia-gemelo` tiene su propia BD y red, no publica puerto, no recibe la
  clave de Claude y en Cloud Run solo lo invoca `vigia-ptw` vía IAM. Solo devuelve
  `apto | apto_con_observaciones | no_apto` con un motivo visible; `diagnostico` es siempre `null`.
  El avatar tampoco trae datos clínicos ni fotos. En su BD cada fila se guarda **seudonimizada**
  (clave primaria = HMAC del `trabajador_id`) y **cifrada con AES-GCM** (identidad, sueño y datos
  clínicos), con la clave `CLINICA_CLAVE` que solo lee `vigia-gemelo`. Fuera de la zona clínica,
  Claude no recibe el trabajador ni el motivo de su aptitud, Langfuse recibe las trazas enmascaradas,
  los logs no incluyen motivos y el texto libre del cierre de un PETAR no se envía a Claude.
- **Claude**: `claude-sonnet-5-5` resume el patrón de incidentes y redacta la explicación;
  `claude-haiku-5-5` etiqueta reportes por lotes (Message Batches API). Sin `ANTHROPIC_API_KEY`
  todo funciona con textos de respaldo deterministas. Las llamadas de Sonnet usan
  `fallbacks: "default"`: si un clasificador de seguridad rechaza, la API reintenta en el modelo recomendado.
- **Sin embeddings**: el agente de incidentes filtra por columnas que Claude generó al etiquetar.
- **NANDA, zona de confianza** (modelo de "Beyond DNS", secciones V y VII): una ficha no se
  autocertifica. La autoridad **SSO** firma una credencial que une el id del agente con su clave
  pública y su vigencia (30 días; 7 para el gemelo, por ser de salud), y la del gemelo la co-firma
  **Salud Ocupacional** certificando la zona clínica. Cada agente publica fichas de vida corta (10 min)
  en `GET /.well-known/agent-facts` y se registra en `vigia-nanda`; el índice y `vigia-ptw` solo
  aceptan credenciales de las autoridades de `NANDA_EMISORES`, así que un suplantador no se registra ni
  antes ni después de un reinicio. SSO puede **revocar** agentes con una lista firmada
  (`POST /revocaciones`; no se acepta una lista anterior a la vigente). `vigia-ptw` no consulta a un agente
  sin credencial válida y exige que **cada respuesta venga firmada** con la clave certificada sobre un
  nonce nuevo; la firma queda en el PTW como evidencia (`consultas.<agente>.evidencia`). Si el índice no
  responde, `vigia-ptw` verifica la ficha que entrega el propio agente. `nanda_index/adaptador.py`
  publica y resuelve en el registry oficial (`projnanda/adapter`) si defines `NANDA_OFICIAL_URL`.
  Simplificación: la credencial sigue la estructura de W3C VC 2.0 sin JSON-LD, y el índice guarda las
  revocaciones en memoria (`vigia-ptw` conserva la última lista válida; tras reiniciar el índice, vuelve
  a publicarla).

## Correr en local

Requisitos: Docker. Opcional: `make` y Python 3.11 para los tests.

```bash
cp .env.example .env            # opcional: ANTHROPIC_API_KEY, Langfuse, Sheets
docker compose up -d --build
make demo                       # o, sin make: python scripts/demo.py [--revocacion]
```

En local no hacen falta claves: los agentes usan credenciales y claves de desarrollo (lo avisan en el
log). `make demo` corre los casos de punta a punta:

1. **Ámbar** — Juan (perforista contratista, 4210 msnm, día 12 de 14, durmió 5.1 h, sílice alta)
   pide perforación de frente en NV-3820 TJ-12 de noche: ruido 91 dBA, desatado hace 26 h y 3
   incidentes de desprendimiento de roca. → revisión → firma → ejecución → cierre.
2. **Verde** — Juan descansado (7.5 h, día 3, energía 85), galería con desatado hace 2 h, sin
   incidentes cercanos. → PETAR emitido solo → ejecución → cierre.
3. **Rojo** — chimenea NV-3700 CH-02 con O2 18.2 % y ventilación detenida. → bloqueada + aviso.
4. **NANDA** — una ficha del gemelo redirigida a un atacante: el índice la rechaza (403).
5. **Revocación** (con `--revocacion`) — SSO revoca `vigia-area` en vivo: el PETAR se bloquea por no
   poder verificar la atmósfera; luego se restaura. A mano:
   `docker compose exec vigia-ptw python -m contracts.agent_facts revocar vigia-area` (sin ids, restaura).

| Servicio | URL local |
|---|---|
| UI Streamlit (trabajador, supervisor, fuentes) | http://localhost:8501 |
| API `vigia-ptw` (Swagger) | http://localhost:8000/docs |
| Índice NANDA | http://localhost:8010/agents |
| `vigia-incidentes` / `vigia-area` | http://localhost:8011/docs, http://localhost:8012/docs |
| `vigia-gemelo` | sin puerto publicado (zona clínica) |

`MOCK_MODE=true` en `.env` hace que `vigia-ptw` use los mocks de `contracts/mocks/` (caso Juan).

### Tests

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # Linux/macOS: .venv/bin/pip
.venv/Scripts/python -m pytest     # o make test
```

Los tests no necesitan Docker: sin `DATABASE_URL` cada servicio usa memoria con los datos sintéticos.

## API pública de `vigia-ptw`

| Método | Ruta | Respuesta |
|---|---|---|
| POST | `/ptw/solicitud` | `{ptw_id, estado: "procesando"}` (202); evalúa en segundo plano |
| GET | `/ptw/{id}` | `{ptw_id, estado, solicitud, consultas, nanda, propuesta?, petar?, explicacion?}`; `consultas` se actualiza a medida que responde cada agente |
| GET | `/ptw/bandeja` | revisiones (ámbar o alto riesgo) y avisos (rojo); los verdes no aparecen |
| POST | `/ptw/{id}/firma` | `{accion: aceptar\|ajustar\|rechazar, supervisor, controles_finales}` solo en `en_revision` |
| POST | `/ptw/{id}/inicio` | `emitido`/`autorizado_con_controles` → `en_ejecucion` |
| POST | `/ptw/{id}/resultado` | `{resultado, controles_cumplidos, observacion}` → `cerrado` |
| GET | `/trabajadores/{id}/avatar` | avatar del gemelo (reenviado desde `vigia-gemelo`) |
| GET | `/ptw?trabajador_id=` | historial (lo usa la UI de Streamlit) |

Estados: `procesando → emitido | en_revision | bloqueado`; `en_revision → autorizado_con_controles | rechazado`;
`emitido | autorizado_con_controles → en_ejecucion → cerrado`. Al ajustar, los controles base del
checklist siempre se mantienen y `controles_finales` reemplaza a los controles extra.

Todos los contratos están en `contracts/modelos.py` y exportados como JSON Schema en
`contracts/schemas/` (`make schemas`; un test falla si quedan desactualizados).

## Reglas y datos

`data/sheets/*.csv` son las filas de ejemplo de las hojas de Google Sheets (mismas columnas). Para usar
las hojas reales, publícalas como CSV y define `SHEETS_<NOMBRE>_URL`; se recargan cada 5 minutos.

- `limites_area.csv` → `tipo`: `max_rojo`, `max_ambar`, `min_rojo`, `min_ambar`, `igual_rojo`;
  `tipo_mineria`: `subterranea`, `tajo_abierto` o `todas`.
- `controles_iperc.csv` → `disparador`: `siempre` o `variable operador valor` (`==`, `!=`, `<`, `<=`,
  `>`, `>=`, `in a|b`). Si el disparador es `siempre` o solo depende de `tipo_tarea`, el control es
  **base**; si no, es **extra**. `trabajo_alto_riesgo`: `si`/`no`.
- `reglas_zona_clinica.csv` → la evalúa solo `vigia-gemelo`; gana el resultado más grave.
- Variables permitidas: `sueno_h, dia_rotacion, regimen_turno, altitud_msnm, tipo_mineria, empleador,
  exposicion_silice, co_ppm, o2_pct, ruido_dBA, ultimo_desatado_h, ventilacion, turno, tipo_tarea`.
  En `disparador` también se aceptan las señales de otros agentes: `apto_para_tarea`,
  `casos_similares`, `riesgo_potencial_max`. Las filas con otras variables se ignoran con un aviso.
- La energía del avatar sale de reglas en `agents/gemelo/energia.py` (puntos por horas de sueño
  menos un descuento según el avance de la rotación).
- `data/synthetic/generar.py` regenera el padrón de trabajadores, sus gemelos con avatar, labores con su
  ficha geotécnica, historial de trabajos, solicitudes e incidentes etiquetados. `clima.json` y `trabajos.json`
  son copia de las hojas CLIMA y TRABAJO de `base_datos_mineria.xlsx`. `data/raw/README.md` explica cómo bajar Kaggle, MINEM y MTPE y etiquetarlos.

Las citas legales de los CSV se verificaron contra el texto consolidado del MINEM (ver
`data/sheets/fuentes.csv`). Los umbrales marcados como "criterio técnico" (horas de sueño, día de
rotación, 12 h desde el último desatado) **no** salen de la norma y deben validarse con el médico
ocupacional y el área de seguridad.

## Despliegue en Google Cloud Run (`southamerica-west1`)

1. Crea un token personal en Supabase (https://supabase.com/dashboard/account/tokens).
2. Ejecuta:

```bash
export PROJECT_ID=mi-proyecto
export ANTHROPIC_API_KEY=... SUPABASE_ACCESS_TOKEN=sbp_...   # solo la primera vez
make deploy                                                  # o: bash scripts/deploy.sh
```

La primera vez, el script crea en Supabase los proyectos `vigia-operacion` y `vigia-clinica`
(`sa-east-1`, contraseña aleatoria), quita a `anon` y `authenticated` el acceso a las tablas que
crearán los servicios en `public` y guarda la URL del *session pooler* en Secret Manager. Usa el
session pooler porque la conexión directa es solo IPv6 y el checkpointer de LangGraph usa sentencias
preparadas, que el *transaction pooler* no admite. Los servicios crean sus tablas y cargan los datos
sintéticos al arrancar. Si la cuenta tiene varias organizaciones, define `SUPABASE_ORG` (slug). Para
usar bases ya creadas, define `DB_OPERACION_URL` y `DB_CLINICA_URL` en lugar del token.

El script crea el Artifact Registry, una cuenta de servicio por servicio, los secretos en Secret
Manager (cada cuenta solo lee los suyos; solo `vigia-gemelo` lee la URL de la BD clínica), construye
las imágenes y despliega `vigia-nanda`, `vigia-incidentes`, `vigia-area`, `vigia-gemelo` (privado,
`roles/run.invoker` solo para `vigia-ptw`), `vigia-ptw`, `vigia-ui` y el front `vigia-web` (con
`web/deploy.sh`, apuntando a `vigia-ptw`; `vigia-ptw` acepta CORS desde su URL salvo que definas
`WEB_ORIGIN`). `vigia-ptw` se despliega con CPU siempre asignada y una instancia mínima porque evalúa
en segundo plano después de responder 202. `vigia-incidentes`, `vigia-area` y `vigia-ptw` usan una
sola instancia para no pasar el límite de conexiones del session pooler.

NANDA y zona clínica: el script crea las semillas de las autoridades (`vigia-autoridad-sso`,
`vigia-autoridad-salud`), que **no se entregan a ningún servicio**, y con ellas emite la credencial de
cada agente (`AGENT_CREDENCIAL`) y la lista blanca `NANDA_EMISORES`; también crea `vigia-clinica-clave`
(solo para `vigia-gemelo`). Volver a ejecutarlo renueva las credenciales. Al final imprime el comando
para revocar un agente.

### Plan B: Render o Railway

Cada carpeta con `Dockerfile` es un servicio web (contexto: la raíz del repo; ruta del Dockerfile:
`agents/<agente>/Dockerfile`, `nanda_index/Dockerfile`, `ui/Dockerfile`). Declara `vigia-gemelo` como
*private service* (Render) o sin dominio público (Railway, red privada) y define las mismas variables
que `docker-compose.yml` (`DATABASE_URL`, `NANDA_URL`, `AGENT_URL`, `*_URL`, `WEB_ORIGIN`), más
`NANDA_EMISORES`, `AGENT_CREDENCIAL` (emítelas con `python -m contracts.agent_facts emisores|emitir`)
y `CLINICA_CLAVE` en el gemelo.

## Estructura

```
contracts/      modelos Pydantic, JSON Schema, AgentFacts y credenciales NANDA (CLI de la autoridad), mocks
nanda_index/    índice NANDA + adaptador al registry oficial
agents/ptw/     orquestador LangGraph (reglas de riesgo, grafo, API)
agents/incidentes/  agents/area/  agents/gemelo/ (zona clínica)
agents/comun/   carga de Sheets, evaluador de reglas, cliente de Claude, publicación NANDA
data/raw/  data/sheets/  data/synthetic/
scripts/        etiquetar_incidentes.py, deploy.sh, demo.py
ui/             Streamlit
```
