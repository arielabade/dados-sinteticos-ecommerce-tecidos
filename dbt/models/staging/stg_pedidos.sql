-- Real orders (no test orders), with local time and UTC side by side.
-- The platform writes in America/Sao_Paulo; tracking writes in UTC.
select
    p.pedido_id,
    p.numero_pedido,
    p.cliente_id,
    c.cliente_id_unificado,
    p.endereco_entrega_id,
    p.sessao_id,
    p.cupom_id,
    p.canal_venda,
    p.status,
    p.status in ('pago', 'enviado', 'entregue', 'devolvido')  as pago,
    p.criado_em                                              as criado_em_local,
    {{ para_utc('p.criado_em') }}                            as criado_em_utc,
    date(p.criado_em)                                        as data_pedido,
    p.pago_em,
    p.cancelado_em,
    p.subtotal,
    p.desconto,
    p.frete,
    p.total,
    p.sessao_id is not null                                  as rastreado
from {{ source('raw', 'pedidos') }} p
join {{ ref('stg_clientes') }} c on c.cliente_id = p.cliente_id
where p.pedido_teste = 0
