-- MMM mart, grain: date. Control variables that are not media:
-- calendar (holidays, retail dates, promotions) and price.
--   indice_preco     = price paid / list price of the items sold on the day
--                      (1 = no catalog discount; 0.90 = 10% below list price)
--   desconto_cupom   = coupon discount / subtotal of the day's paid orders
with itens as (
    select p.data_pedido as data,
           sum(i.total_item) / nullif(sum(i.quantidade * i.preco_tabela), 0) as indice_preco,
           avg(i.em_promocao)                                                as share_itens_promocao
    from {{ ref('stg_itens_pedido') }} i
    join {{ ref('stg_pedidos') }} p on p.pedido_id = i.pedido_id and p.pago
    group by 1
),
cupom as (
    select data_pedido as data, sum(desconto) / nullif(sum(subtotal), 0) as desconto_cupom
    from {{ ref('stg_pedidos') }}
    where pago
    group by 1
)
select
    c.data,
    c.dia_semana,
    c.feriado_nacional,
    c.nome_feriado,
    c.evento_comercial,
    c.evento_black_friday,
    c.evento_natal,
    c.evento_dia_das_maes,
    c.evento_qualquer,
    c.promocao_loja,
    c.nome_promocao,
    coalesce(i.indice_preco, 1)          as indice_preco,
    coalesce(i.share_itens_promocao, 0)  as share_itens_promocao,
    coalesce(k.desconto_cupom, 0)        as desconto_cupom
from {{ ref('stg_calendario_comercial') }} c
left join itens i on i.data = c.data
left join cupom k on k.data = c.data
