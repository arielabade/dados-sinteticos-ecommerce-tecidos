-- Mart do MMM, grão: data. Variáveis de controle que não são mídia:
-- calendário (feriados, datas comerciais, promoções) e preço.
--   indice_preco     = preço pago / preço de tabela nos itens vendidos no dia
--                      (1 = sem desconto de catálogo; 0,90 = 10% abaixo da tabela)
--   desconto_cupom   = desconto de cupom / subtotal dos pedidos pagos do dia
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
