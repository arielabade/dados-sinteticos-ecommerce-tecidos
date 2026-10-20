# Shortcuts. `make` (default target `banco`) generates the data, recreates MySQL from scratch,
# loads everything (including the MMM layer), runs dbt and the validations.
PY ?= .venv/bin/python
ESCALA ?= 1.0

.DEFAULT_GOAL := banco
.PHONY: banco ambiente dados mysql recarregar dbt validar notebooks dicionario diagramas tudo limpar

banco: dados recarregar dbt validar   ## from scratch: generate, load, transform and validate

ambiente:            ## creates the Python environment
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

dados:               ## generates the CSVs in data/csv and the ground truth in data/ground_truth (ESCALA=0.05 for a sample)
	ESCALA=$(ESCALA) $(PY) -m gerador

mysql:               ## starts MySQL and loads the CSVs (first time only; waits until healthy)
	docker compose up -d --wait mysql

recarregar:          ## deletes the MySQL volume and loads the current CSVs from scratch
	docker compose down -v
	docker compose up -d --wait mysql

dbt:                 ## runs the dbt models and tests inside a container
	docker compose --profile dbt run --rm -T --build dbt build

validar:             ## integrity, business rules, MMM reconciliations and preserved distributions
	ESCALA=$(ESCALA) $(PY) scripts/validar.py

notebooks:           ## runs the 5 notebooks from start to finish
	cd notebooks && for nb in 0*.ipynb; do OMP_NUM_THREADS=4 POLARS_MAX_THREADS=4 ../.venv/bin/jupyter nbconvert --to notebook --execute --inplace $$nb || exit 1; done

dicionario:          ## regenerates docs/dicionario_dados.md from the database (--parquet DIR works without it)
	$(PY) scripts/gerar_dicionario.py

diagramas:           ## regenerates docs/diagramas/*.svg from schema.sql (fails if any line crosses)
	$(PY) scripts/gerar_diagramas.py

tudo: banco notebooks

limpar:              ## stops MySQL and deletes the volume (the CSVs stay)
	docker compose down -v
