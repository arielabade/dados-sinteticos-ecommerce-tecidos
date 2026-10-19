# Atalhos. Rode `make tudo` para o fluxo completo.
PY ?= .venv/bin/python
ESCALA ?= 1.0

.PHONY: ambiente dados mysql dbt validar notebooks dicionario tudo limpar

ambiente:            ## cria o ambiente Python
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

dados:               ## gera os CSVs em data/csv (ESCALA=0.05 para uma amostra rápida)
	ESCALA=$(ESCALA) $(PY) -m gerador

mysql:               ## sobe o MySQL e carrega os CSVs (só na primeira vez; espera ficar saudável)
	docker compose up -d --wait mysql

dbt:                 ## roda os modelos e testes do dbt dentro de um container
	docker compose --profile dbt run --rm -T --build dbt build

validar:             ## integridade referencial, regras de negócio e faixas de métricas
	$(PY) scripts/validar.py

notebooks:           ## executa os 5 notebooks do início ao fim
	cd notebooks && for nb in 0*.ipynb; do OMP_NUM_THREADS=4 POLARS_MAX_THREADS=4 ../.venv/bin/jupyter nbconvert --to notebook --execute --inplace $$nb || exit 1; done

dicionario:          ## regenera docs/dicionario_dados.md a partir do banco
	$(PY) scripts/gerar_dicionario.py

tudo: dados mysql dbt validar notebooks

limpar:              ## derruba o MySQL e apaga o volume (os CSVs ficam)
	docker compose down -v
