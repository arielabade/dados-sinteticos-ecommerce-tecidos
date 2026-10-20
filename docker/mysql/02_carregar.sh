#!/bin/bash
# Carga dos CSVs gerados por `python -m gerador` (montados em /dados).
# Roda automaticamente na primeira subida do container (volume vazio).
set -euo pipefail

TABELAS=(
  categorias fornecedores produtos variantes historico_precos estoque estoque_diario
  clientes enderecos cupons
  meta_contas meta_campanhas meta_conjuntos meta_anuncios meta_metricas_diarias
  google_contas google_campanhas google_grupos_anuncio google_palavras_chave
  google_metricas_diarias google_palavras_chave_metricas_diarias
  cliques_midia sessoes pedidos itens_pedido pagamentos fretes devolucoes
  movimentacoes_estoque avaliacoes eventos envios_conversao atribuicoes
  canais_midia regioes calendario_comercial testes_geo testes_geo_regioes
  tiktok_campanhas tiktok_metricas_diarias afiliados_parceiros afiliados_metricas_diarias
  crm_disparos midia_regional_diaria
)

if [ ! -f /dados/pedidos.csv ]; then
  echo ">> /dados/pedidos.csv não encontrado. Rode 'make dados' (ou 'python -m gerador') antes de subir o MySQL."
  echo ">> O schema foi criado vazio."
  exit 0
fi

MYSQL=(mysql --protocol=socket -uroot -p"${MYSQL_ROOT_PASSWORD}" --local-infile=0 tecidos)

for t in "${TABELAS[@]}"; do
  f="/dados/${t}.csv"
  if [ ! -f "$f" ]; then
    echo ">> aviso: $f não existe, pulando"
    continue
  fi
  cols=$(head -n1 "$f" | tr -d '\r')
  inicio=$(date +%s)
  "${MYSQL[@]}" <<SQL
SET SESSION foreign_key_checks = 0;
SET SESSION unique_checks = 0;
SET SESSION sql_log_bin = 0;
LOAD DATA INFILE '${f}'
  INTO TABLE ${t}
  CHARACTER SET utf8mb4
  FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '\\\\'
  LINES TERMINATED BY '\n'
  IGNORE 1 LINES
  (${cols});
SQL
  n=$("${MYSQL[@]}" -N -e "SELECT COUNT(*) FROM ${t}")
  echo ">> ${t}: ${n} linhas em $(( $(date +%s) - inicio ))s"
done

"${MYSQL[@]}" -e "CREATE TABLE _carga_concluida (concluida_em DATETIME NOT NULL); INSERT INTO _carga_concluida VALUES (NOW());"
echo ">> carga concluída"
