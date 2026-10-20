# Atalhos. `make` (alvo padrão `banco`) gera os dados, recria o MySQL do zero,
# carrega tudo (inclusive a camada de MMM), roda o dbt e as validações.
PY ?= .venv/bin/python
ESCALA ?= 1.0

.DEFAULT_GOAL := banco
.PHONY: banco ambiente dados mysql recarregar dbt validar notebooks dicionario tudo limpar

banco: dados recarregar dbt validar   ## do zero: gera, carrega, transforma e valida

ambiente:            ## cria o ambiente Python
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

dados:               ## gera os CSVs em data/csv e o ground truth em data/ground_truth (ESCALA=0.05 para amostra)
	ESCALA=$(ESCALA) $(PY) -m gerador

mysql:               ## sobe o MySQL e carrega os CSVs (só na primeira vez; espera ficar saudável)
	docker compose up -d --wait mysql

recarregar:          ## apaga o volume do MySQL e carrega os CSVs atuais do zero
	docker compose down -v
	docker compose up -d --wait mysql

dbt:                 ## roda os modelos e testes do dbt dentro de um container
	docker compose --profile dbt run --rm -T --build dbt build

validar:             ## integridade, regras de negócio, reconciliações do MMM e distribuições preservadas
	ESCALA=$(ESCALA) $(PY) scripts/validar.py

notebooks:           ## executa os 5 notebooks do início ao fim
	cd notebooks && for nb in 0*.ipynb; do OMP_NUM_THREADS=4 POLARS_MAX_THREADS=4 ../.venv/bin/jupyter nbconvert --to notebook --execute --inplace $$nb || exit 1; done

dicionario:          ## regenera docs/dicionario_dados.md a partir do banco
	$(PY) scripts/gerar_dicionario.py

tudo: banco notebooks

limpar:              ## derruba o MySQL e apaga o volume (os CSVs ficam)
	docker compose down -v
