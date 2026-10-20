-- Grain: unified customer (accounts with the same CPF become one).
with pedidos as (
    select * from {{ ref('fct_pedidos') }} where pago
),
agg as (
    select
        cliente_id_unificado,
        min(criado_em_local)  as primeira_compra,
        max(criado_em_local)  as ultima_compra,
        count(*)              as pedidos,
        sum(total)            as receita,
        sum(margem_bruta)     as margem_bruta,
        avg(total)            as ticket_medio
    from pedidos
    group by cliente_id_unificado
),
aquisicao as (
    select cliente_id_unificado, canal_last_click as canal_aquisicao, cupom as cupom_primeira_compra, uf
    from pedidos where seq_cliente = 1
)
select
    c.cliente_id_unificado as cliente_id,
    c.tipo_cliente,
    c.tipo_pessoa,
    c.cadastrado_em,
    c.origem_cadastro,
    c.cliente_legado,
    c.aceita_email_marketing,
    a.uf,
    agg.primeira_compra,
    agg.ultima_compra,
    date_format(agg.primeira_compra, '%Y-%m-01') as coorte_mes,
    coalesce(agg.pedidos, 0)       as pedidos,
    coalesce(agg.receita, 0)       as receita,
    coalesce(agg.margem_bruta, 0)  as margem_bruta,
    agg.ticket_medio,
    a.canal_aquisicao,
    a.cupom_primeira_compra
from {{ ref('stg_clientes') }} c
left join agg       on agg.cliente_id_unificado = c.cliente_id_unificado
left join aquisicao a on a.cliente_id_unificado = c.cliente_id_unificado
where c.cliente_id = c.cliente_id_unificado
