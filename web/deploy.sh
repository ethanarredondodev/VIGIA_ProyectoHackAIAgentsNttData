#!/usr/bin/env sh
# Despliega el front en Cloud Run.
#   API real: VITE_API_URL=https://vigia-ptw-xxxxx.southamerica-west1.run.app ./deploy.sh
#   Demo:     VITE_USE_MOCKS=true ./deploy.sh
set -eu
cd "$(dirname "$0")"

VITE_USE_MOCKS="${VITE_USE_MOCKS:-false}"
VITE_API_URL="${VITE_API_URL:-}"
if [ "$VITE_USE_MOCKS" != "true" ] && [ -z "$VITE_API_URL" ]; then
  echo "Define VITE_API_URL o usa VITE_USE_MOCKS=true" >&2
  exit 1
fi

# Vite fija estas variables al compilar, dentro de la imagen.
printf 'VITE_USE_MOCKS=%s\nVITE_API_URL=%s\n' "$VITE_USE_MOCKS" "$VITE_API_URL" > .env.production

gcloud run deploy vigia-web --source . --region southamerica-west1 --allow-unauthenticated --quiet
