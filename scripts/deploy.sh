#!/usr/bin/env bash
# Despliega Vigía en Google Cloud Run (southamerica-west1) y crea sus dos bases en Supabase.
#
# Requisitos: gcloud autenticado (gcloud auth login), docker, openssl, curl y python.
# Variables:
#   PROJECT_ID             obligatoria
#   ANTHROPIC_API_KEY      la primera vez (se guarda en Secret Manager)
#   SUPABASE_ACCESS_TOKEN  la primera vez: token personal (supabase.com/dashboard/account/tokens) con el
#                          que se crean los proyectos `vigia-operacion` y `vigia-clinica`
#   SUPABASE_ORG           slug de la organizacion de Supabase; solo si la cuenta tiene mas de una
#   DB_OPERACION_URL, DB_CLINICA_URL  opcionales: usar bases ya creadas en lugar de crearlas
#   WEB_ORIGIN             origen(es) del front para CORS en vigia-ptw (por defecto, la URL de vigia-web)
#   LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST  opcionales
#   REGION (southamerica-west1), REPO (vigia), TAG (git sha)  opcionales
#   SOLO_BACKEND=true      despliega solo las bases y los agentes, sin vigia-ui ni vigia-web
#
# Servicios: vigia-nanda, vigia-incidentes, vigia-area, vigia-gemelo, vigia-ptw, vigia-ui y vigia-web.
# Seguridad: una cuenta de servicio por servicio; cada una solo lee sus secretos.
# `vigia-gemelo` NO es publico: solo `vigia-ptw` tiene roles/run.invoker sobre el.
# NANDA: las semillas de las autoridades (vigia-autoridad-sso, vigia-autoridad-salud) no se
# entregan a ningun servicio; solo este script las usa para emitir las credenciales de los
# agentes. Volver a ejecutarlo las renueva (30 dias; 7 para el gemelo).
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Define PROJECT_ID}"
REGION="${REGION:-southamerica-west1}"
REPO="${REPO:-vigia}"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"

# Solo para este proceso: no cambia la configuracion de gcloud. La cuenta es la de la config activa.
export CLOUDSDK_CORE_PROJECT="$PROJECT_ID"
echo "==> ${PROJECT_ID} con la cuenta $(gcloud config get-value account 2>/dev/null)"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

url_de() { echo "https://vigia-$1-${PROJECT_NUMBER}.${REGION}.run.app"; }
cuenta_de() { echo "vigia-$1@${PROJECT_ID}.iam.gserviceaccount.com"; }

echo "==> APIs"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com iamcredentials.googleapis.com cloudbuild.googleapis.com

echo "==> Artifact Registry"
gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 ||
  gcloud artifacts repositories create "$REPO" --repository-format docker --location "$REGION"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "==> Cuentas de servicio"
for s in nanda incidentes area gemelo ptw ui; do
  gcloud iam service-accounts describe "$(cuenta_de "$s")" >/dev/null 2>&1 ||
    gcloud iam service-accounts create "vigia-${s}" --display-name "Vigia ${s}"
done

echo "==> Secretos"
crear_secreto() {
  local nombre="$1" valor="${2:-}"
  if ! gcloud secrets describe "$nombre" >/dev/null 2>&1; then
    [ -n "$valor" ] || { echo "Falta el valor para crear el secreto $nombre" >&2; exit 1; }
    printf '%s' "$valor" | gcloud secrets create "$nombre" --data-file=- --replication-policy=automatic
  fi
}
dar_acceso() {
  gcloud secrets add-iam-policy-binding "$1" --member "serviceAccount:$(cuenta_de "$2")" \
    --role roles/secretmanager.secretAccessor --quiet >/dev/null
}

supabase_api() {
  local cuerpo
  if ! cuerpo="$(curl -sS --fail-with-body -X "$1" "https://api.supabase.com/v1$2" \
    -H "Authorization: Bearer ${SUPABASE_ACCESS_TOKEN}" -H "Content-Type: application/json" ${3:+--data "$3"})"; then
    echo "Supabase $1 $2: ${cuerpo}" >&2
    return 1
  fi
  printf '%s' "$cuerpo"
}
# Sin salto de linea: en Windows python lo escribiria como \r\n.
json() { python -c "import json, sys; d = json.load(sys.stdin); sys.stdout.write(str($1))"; }

# Crea el proyecto Supabase `vigia-<bd>` en sa-east-1 (la region mas cercana a Santiago) y deja su URL
# en DB_<BD>_URL. Usa el session pooler (5432): la conexion directa es solo IPv6, que Cloud Run no
# tiene, y el transaction pooler no admite las sentencias preparadas del checkpointer de LangGraph.
crear_bd_supabase() {
  local nombre="vigia-$1" org="${SUPABASE_ORG:-}" existe clave ref estado host
  : "${SUPABASE_ACCESS_TOKEN:?Define SUPABASE_ACCESS_TOKEN (o DB_${1^^}_URL) para crear la base ${nombre}}"
  existe="$(supabase_api GET /projects | json "any(p['name'] == '${nombre}' for p in d)")"
  if [ "$existe" = True ]; then
    echo "El proyecto Supabase ${nombre} ya existe pero su URL no esta en Secret Manager: borralo o define DB_${1^^}_URL" >&2
    exit 1
  fi
  [ -n "$org" ] || org="$(supabase_api GET /organizations | json "d[0]['slug'] if len(d) == 1 else ''")"
  [ -n "$org" ] || { echo "La cuenta de Supabase tiene varias organizaciones: define SUPABASE_ORG" >&2; exit 1; }
  clave="$(openssl rand -hex 24)"
  echo "==> Supabase: ${nombre} (organizacion ${org})"
  ref="$(supabase_api POST /projects "{\"name\":\"${nombre}\",\"organization_slug\":\"${org}\",\"db_pass\":\"${clave}\",\"region_selection\":{\"type\":\"specific\",\"code\":\"sa-east-1\"}}" | json "d['ref']")"
  estado=COMING_UP
  while [ "$estado" != ACTIVE_HEALTHY ]; do
    echo "  ${nombre}: ${estado}"
    sleep 15
    estado="$(supabase_api GET "/projects/${ref}" | json "d['status']")"
  done
  # Las tablas que crean los servicios en `public` no quedan expuestas a la Data API de Supabase.
  supabase_api POST "/projects/${ref}/database/query" \
    '{"query":"alter default privileges for role postgres in schema public revoke all on tables from anon, authenticated"}' >/dev/null
  host="$(supabase_api GET "/projects/${ref}/config/database/pooler" | json "next(p['db_host'] for p in d if p['database_type'] == 'PRIMARY')")"
  printf -v "DB_${1^^}_URL" '%s' "postgresql://postgres.${ref}:${clave}@${host}:5432/postgres?sslmode=require"
}

crear_secreto vigia-anthropic-api-key "${ANTHROPIC_API_KEY:-}"
for bd in operacion clinica; do
  variable="DB_${bd^^}_URL"
  if ! gcloud secrets describe "vigia-db-${bd}-url" >/dev/null 2>&1 && [ -z "${!variable:-}" ]; then
    crear_bd_supabase "$bd"
  fi
  crear_secreto "vigia-db-${bd}-url" "${!variable:-}"
done
for s in incidentes area gemelo ptw; do
  crear_secreto "vigia-ed25519-${s}" "$(openssl rand -base64 32)"
  dar_acceso "vigia-ed25519-${s}" "$s"
done
dar_acceso vigia-anthropic-api-key incidentes
dar_acceso vigia-anthropic-api-key ptw
dar_acceso vigia-db-operacion-url incidentes
dar_acceso vigia-db-operacion-url area
dar_acceso vigia-db-operacion-url ptw
dar_acceso vigia-db-clinica-url gemelo
crear_secreto vigia-clinica-clave "$(openssl rand -base64 32)"
dar_acceso vigia-clinica-clave gemelo
crear_secreto vigia-autoridad-sso "$(openssl rand -base64 32)"
crear_secreto vigia-autoridad-salud "$(openssl rand -base64 32)"

SECRETOS_LANGFUSE=""
if [ -n "${LANGFUSE_PUBLIC_KEY:-}" ] && [ -n "${LANGFUSE_SECRET_KEY:-}" ]; then
  crear_secreto vigia-langfuse-public-key "$LANGFUSE_PUBLIC_KEY"
  crear_secreto vigia-langfuse-secret-key "$LANGFUSE_SECRET_KEY"
  dar_acceso vigia-langfuse-public-key ptw
  dar_acceso vigia-langfuse-secret-key ptw
  SECRETOS_LANGFUSE=",LANGFUSE_PUBLIC_KEY=vigia-langfuse-public-key:latest,LANGFUSE_SECRET_KEY=vigia-langfuse-secret-key:latest"
fi

echo "==> Imagenes (${TAG})"
declare -A DOCKERFILES=(
  [nanda]=nanda_index/Dockerfile
  [incidentes]=agents/incidentes/Dockerfile
  [area]=agents/area/Dockerfile
  [gemelo]=agents/gemelo/Dockerfile
  [ptw]=agents/ptw/Dockerfile
  [ui]=ui/Dockerfile
)
if [ "${SOLO_BACKEND:-false}" = true ]; then
  unset 'DOCKERFILES[ui]'
fi
for s in "${!DOCKERFILES[@]}"; do
  docker build --platform linux/amd64 -f "${DOCKERFILES[$s]}" -t "${REGISTRY}/${s}:${TAG}" .
  docker push "${REGISTRY}/${s}:${TAG}"
done

echo "==> Credenciales NANDA (autoridades SSO y Salud Ocupacional)"
leer_secreto() { gcloud secrets versions access latest --secret "$1"; }
autoridad() {
  docker run --rm -e SEMILLA_SSO -e SEMILLA_SALUD -e SEMILLA_AGENTE "${REGISTRY}/ptw:${TAG}" \
    python -m contracts.agent_facts "$@"
}
SEMILLA_SSO="$(leer_secreto vigia-autoridad-sso)"
SEMILLA_SALUD="$(leer_secreto vigia-autoridad-salud)"
export SEMILLA_SSO SEMILLA_SALUD SEMILLA_AGENTE
NANDA_EMISORES="$(autoridad emisores)"
declare -A CREDENCIAL
for s in incidentes area gemelo ptw; do
  SEMILLA_AGENTE="$(leer_secreto "vigia-ed25519-${s}")"
  if [ "$s" = gemelo ]; then
    CREDENCIAL[$s]="$(autoridad emitir "vigia-${s}" --zona-clinica)"
  else
    CREDENCIAL[$s]="$(autoridad emitir "vigia-${s}")"
  fi
done
unset SEMILLA_SSO SEMILLA_SALUD SEMILLA_AGENTE

# desplegar <servicio> <--allow-unauthenticated|--no-allow-unauthenticated> <env> <secretos> [flags extra]
desplegar() {
  local s="$1" acceso="$2" env="AGENT_URL=$(url_de "$1")${3:+,$3}" secretos="$4"
  shift 4
  local args=(--image "${REGISTRY}/${s}:${TAG}" --region "$REGION" --service-account "$(cuenta_de "$s")"
    "$acceso" --set-env-vars "$env" --quiet "$@")
  [ -n "$secretos" ] && args+=(--set-secrets "$secretos")
  echo "==> vigia-${s}"
  gcloud run deploy "vigia-${s}" "${args[@]}"
}

NANDA_URL="$(url_de nanda)"

# El indice guarda las AgentFacts y las revocaciones en memoria: una sola instancia siempre encendida.
desplegar nanda --allow-unauthenticated "NANDA_EMISORES=${NANDA_EMISORES}" "" --min-instances 1 --max-instances 1
# incidentes, area y ptw comparten usuario en el session pooler de Supabase y cada instancia abre 4
# conexiones: una instancia por servicio para no pasar el pool size del pooler.
desplegar incidentes --allow-unauthenticated "NANDA_URL=${NANDA_URL},AGENT_CREDENCIAL=${CREDENCIAL[incidentes]}" \
  "DATABASE_URL=vigia-db-operacion-url:latest,ANTHROPIC_API_KEY=vigia-anthropic-api-key:latest,AGENT_ED25519_KEY=vigia-ed25519-incidentes:latest" \
  --max-instances 1
desplegar area --allow-unauthenticated "NANDA_URL=${NANDA_URL},AGENT_CREDENCIAL=${CREDENCIAL[area]}" \
  "DATABASE_URL=vigia-db-operacion-url:latest,AGENT_ED25519_KEY=vigia-ed25519-area:latest" --max-instances 1
desplegar gemelo --no-allow-unauthenticated \
  "NANDA_URL=${NANDA_URL},AGENT_AUTH=google_iam_id_token,AGENT_CREDENCIAL=${CREDENCIAL[gemelo]}" \
  "DATABASE_URL=vigia-db-clinica-url:latest,AGENT_ED25519_KEY=vigia-ed25519-gemelo:latest,CLINICA_CLAVE=vigia-clinica-clave:latest"
gcloud run services add-iam-policy-binding vigia-gemelo --region "$REGION" \
  --member "serviceAccount:$(cuenta_de ptw)" --role roles/run.invoker --quiet >/dev/null
# POST /ptw/solicitud responde 202 y evalua en segundo plano: la CPU debe seguir asignada tras responder.
# WEB_ORIGIN puede llevar comas: se pasa con el delimitador alternativo ^@^ de gcloud.
gcloud run deploy vigia-ptw --image "${REGISTRY}/ptw:${TAG}" --region "$REGION" \
  --service-account "$(cuenta_de ptw)" --allow-unauthenticated --quiet \
  --no-cpu-throttling --min-instances 1 --max-instances 1 --timeout 300 \
  --set-env-vars "^@^AGENT_URL=$(url_de ptw)@NANDA_URL=${NANDA_URL}@INCIDENTES_URL=$(url_de incidentes)@AREA_URL=$(url_de area)@GEMELO_URL=$(url_de gemelo)@GEMELO_IAM=true@MOCK_MODE=false@LANGFUSE_HOST=${LANGFUSE_HOST:-https://cloud.langfuse.com}@WEB_ORIGIN=${WEB_ORIGIN:-$(url_de web)}@NANDA_EMISORES=${NANDA_EMISORES}@AGENT_CREDENCIAL=${CREDENCIAL[ptw]}" \
  --set-secrets "DATABASE_URL=vigia-db-operacion-url:latest,ANTHROPIC_API_KEY=vigia-anthropic-api-key:latest,AGENT_ED25519_KEY=vigia-ed25519-ptw:latest${SECRETOS_LANGFUSE}"
if [ "${SOLO_BACKEND:-false}" != true ]; then
  desplegar ui --allow-unauthenticated "PTW_URL=$(url_de ptw)" ""
  echo "==> vigia-web"
  VITE_API_URL="$(url_de ptw)" sh web/deploy.sh
fi

echo
if [ "${SOLO_BACKEND:-false}" != true ]; then
  echo "Front:       $(url_de web)"
  echo "UI:          $(url_de ui)"
fi
echo "PTW (API):   $(url_de ptw)/docs"
echo "Indice NANDA: ${NANDA_URL}/agents"
echo "Gemelo:      privado (solo vigia-ptw vía IAM)"
echo
echo "Revocar un agente (sin ids restaura):"
echo "  SEMILLA_SSO=\"\$(gcloud secrets versions access latest --secret vigia-autoridad-sso)\" \\"
echo "    docker run --rm -e SEMILLA_SSO ${REGISTRY}/ptw:${TAG} python -m contracts.agent_facts revocar vigia-area --nanda ${NANDA_URL}"
