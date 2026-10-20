-- Nenhum investimento em UF onde a loja não entrega (venda impossível).
select m.*
from {{ ref('fct_mmm_midia_canal_regiao_diario') }} m
join {{ ref('stg_regioes') }} r on r.uf = m.uf
where m.investimento > 0 and not r.entrega_disponivel
