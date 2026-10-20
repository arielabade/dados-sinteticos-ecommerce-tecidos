-- Mart do MMM, grão: data x UF (grade completa: UF sem venda no dia = 0).
-- Receita = total dos pedidos pagos (sem pedidos de teste), pela data local de
-- criação, a mesma definição de fct_kpis_diarios. A UF é a do endereço de
-- entrega; retirada na loja (sem endereço) conta para SP, onde fica a loja.
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
