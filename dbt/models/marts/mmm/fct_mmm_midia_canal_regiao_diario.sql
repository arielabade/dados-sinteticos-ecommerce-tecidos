-- MMM mart, grain: date x channel x state.
-- Spend, impressions, clicks and click-through conversions, as the platforms'
-- geographic report delivers them. It is the only media source the modeling
-- repository reads. The true effects of each channel are NOT in the
-- database (they live in data/ground_truth/, outside MySQL).
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
