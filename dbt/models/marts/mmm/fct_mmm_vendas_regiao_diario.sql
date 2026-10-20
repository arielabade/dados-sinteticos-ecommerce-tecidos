-- MMM mart, grain: date x state (complete grid: a state with no sales on the day = 0).
-- Revenue = total of paid orders (no test orders), by local creation
-- date, the same definition as fct_kpis_diarios. The state is the shipping
-- address's; store pickup (no address) counts for SP, where the store is.
with vendas as (
    select
        data_pedido                as data,
        coalesce(uf, 'SP')         as uf,
        count(*)                   as pedidos,
        sum(total)                 as receita,
        sum(primeira_compra)       as novos_clientes
    from {{ ref('fct_pedidos') }}
    where pago
    group by 1, 2
)
select
    c.data,
    r.uf,
    r.macrorregiao,
    coalesce(v.pedidos, 0)         as pedidos,
    coalesce(v.receita, 0)         as receita,
    coalesce(v.novos_clientes, 0)  as novos_clientes
from {{ ref('stg_calendario_comercial') }} c
cross join {{ ref('stg_regioes') }} r
left join vendas v on v.data = c.data and v.uf = r.uf
