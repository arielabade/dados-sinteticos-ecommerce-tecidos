-- Grão: pedido. Inclui sequência do cliente (novo x recorrente), coorte,
-- margem bruta e canal de last click (atribuição).
with itens as (
    select pedido_id,
           count(*)                as linhas,
           sum(metros)             as metros,
           sum(margem_bruta_item)  as margem_bruta_itens,
           max(em_promocao)        as tem_item_em_promocao
    from {{ ref('stg_itens_pedido') }}
    group by pedido_id
),
seq as (
    select pedido_id,
           row_number() over (partition by cliente_id_unificado order by criado_em_local, pedido_id) as seq_cliente,
           min(criado_em_local) over (partition by cliente_id_unificado) as primeira_compra_cliente
    from {{ ref('stg_pedidos') }}
    where pago
),
lc as (
    select pedido_id, canal as canal_last_click, meta_campanha_id, google_campanha_id
    from {{ source('raw', 'atribuicoes') }}
    where modelo = 'last_click'
)
select
    p.*,
    c.tipo_cliente,
    e.uf,
    seq.seq_cliente,
    seq.seq_cliente = 1                                         as primeira_compra,
    date_format(seq.primeira_compra_cliente, '%Y-%m-01')        as coorte_mes,
    i.linhas,
    i.metros,
    i.tem_item_em_promocao,
    i.margem_bruta_itens - p.desconto                           as margem_bruta,
    f.frete_gratis,
    f.custo_real                                                as custo_frete,
    coalesce(lc.canal_last_click, case when p.rastreado then 'Direct' else '(não rastreado)' end) as canal_last_click,
    lc.meta_campanha_id                                         as meta_campanha_id_last_click,
    lc.google_campanha_id                                       as google_campanha_id_last_click,
    cu.codigo                                                   as cupom
from {{ ref('stg_pedidos') }} p
join {{ ref('stg_clientes') }} c         on c.cliente_id = p.cliente_id
left join {{ source('raw', 'enderecos') }} e on e.endereco_id = p.endereco_entrega_id
left join seq                            on seq.pedido_id = p.pedido_id
left join itens i                        on i.pedido_id = p.pedido_id
left join {{ source('raw', 'fretes') }} f on f.pedido_id = p.pedido_id
left join lc                             on lc.pedido_id = p.pedido_id
left join {{ source('raw', 'cupons') }} cu on cu.cupom_id = p.cupom_id
