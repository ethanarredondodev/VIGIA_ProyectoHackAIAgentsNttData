PY ?= python

.PHONY: up down logs test demo schemas sinteticos etiquetar deploy

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f vigia-ptw vigia-incidentes vigia-area vigia-gemelo vigia-nanda

test:
	$(PY) -m pytest

# Levanta el stack y corre los casos ambar, verde y rojo de punta a punta.
demo: up
	$(PY) scripts/demo.py

schemas:
	$(PY) -m contracts.exportar_schemas

sinteticos:
	$(PY) data/synthetic/generar.py

etiquetar:
	$(PY) scripts/etiquetar_incidentes.py --entrada data/synthetic/incidentes_raw.csv --salida data/synthetic/incidentes_claude.json

deploy:
	bash scripts/deploy.sh
