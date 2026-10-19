select
    i.item_pedido_id,
    i.pedido_id,
    i.variante_id,
    v.produto_id,
    pr.categoria_id,
    cat.categoria_pai_id                          as familia_id,
    v.formato_venda,
    i.quantidade,
    i.quantidade * v.metros_por_unidade           as metros,
    i.preco_unitario,
    i.preco_tabela,
    i.preco_unitario < i.preco_tabela             as em_promocao,
    i.custo_unitario,
    i.total_item,
    i.total_item - i.quantidade * i.custo_unitario as margem_bruta_item
from {{ source('raw', 'itens_pedido') }} i
join {{ source('raw', 'variantes') }} v   on v.variante_id = i.variante_id
join {{ source('raw', 'produtos') }} pr   on pr.produto_id = v.produto_id
join {{ source('raw', 'categorias') }} cat on cat.categoria_id = pr.categoria_id
