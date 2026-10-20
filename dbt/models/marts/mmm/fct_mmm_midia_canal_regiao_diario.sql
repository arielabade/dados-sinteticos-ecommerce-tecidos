-- Mart do MMM, grão: data x canal x UF.
-- Investimento, impressões, cliques e conversões reportadas por clique, como o
-- relatório geográfico das plataformas entrega. É a única fonte de mídia que o
-- repositório de modelagem lê. Os efeitos verdadeiros de cada canal NÃO estão
-- no banco (ficam em data/ground_truth/, fora do MySQL).
select
    m.data,
    m.uf,
    r.macrorregiao,
    m.canal_id,
    m.canal,
    m.canal_mmm,
    m.tipo_investimento,
    m.investimento,
    m.impressoes,
    m.cliques,
    m.conversoes_plataforma
from {{ ref('stg_midia_regional_diaria') }} m
join {{ ref('stg_regioes') }} r on r.uf = m.uf
