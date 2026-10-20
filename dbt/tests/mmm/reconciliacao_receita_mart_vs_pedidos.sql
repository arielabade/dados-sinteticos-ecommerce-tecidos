-- A receita do mart diário (somada nas UFs) tem de bater com a receita dos pedidos pagos.
with mart as (select data, sum(receita) r, sum(pedidos) n from {{ ref('fct_mmm_vendas_regiao_diario') }} group by data),
ped as (select data_pedido data, sum(total) r, count(*) n from {{ ref('fct_pedidos') }} where pago group by data_pedido)
select coalesce(m.data, p.data) as data, m.r as receita_mart, p.r as receita_pedidos, m.n, p.n
from mart m
left join ped p on p.data = m.data
where abs(coalesce(m.r, 0) - coalesce(p.r, 0)) > 0.01 or coalesce(m.n, 0) <> coalesce(p.n, 0)
union all
select p.data, null, p.r, null, p.n from ped p where p.data not in (select data from mart)
