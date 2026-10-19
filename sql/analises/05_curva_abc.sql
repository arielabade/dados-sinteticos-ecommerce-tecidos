-- =====================================================================
-- Curva ABC de produtos (receita dos últimos 12 meses)
-- A = até 80% da receita acumulada, B = 80-95%, C = resto.
-- =====================================================================
WITH ult12 AS (
    SELECT i.variante_id, i.total_item, i.quantidade, i.custo_unitario
    FROM itens_pedido i
    JOIN pedidos p ON p.pedido_id = i.pedido_id
    WHERE p.pedido_teste = 0 AND p.status IN ('pago', 'enviado', 'entregue', 'devolvido')
      AND p.criado_em >= (SELECT MAX(criado_em) FROM pedidos) - INTERVAL 12 MONTH
),
prod AS (
    SELECT pr.produto_id, pr.nome, cat.nome AS subcategoria, fam.nome AS familia,
           SUM(u.total_item)                                AS receita,
           SUM(u.total_item - u.quantidade * u.custo_unitario) AS margem_bruta,
           SUM(u.quantidade * v.metros_por_unidade)          AS metros
    FROM ult12 u
    JOIN variantes v    ON v.variante_id = u.variante_id
    JOIN produtos pr    ON pr.produto_id = v.produto_id
    JOIN categorias cat ON cat.categoria_id = pr.categoria_id
    JOIN categorias fam ON fam.categoria_id = cat.categoria_pai_id
    GROUP BY pr.produto_id, pr.nome, cat.nome, fam.nome
),
acum AS (
    SELECT p.*,
           SUM(receita) OVER (ORDER BY receita DESC, produto_id ROWS UNBOUNDED PRECEDING) / SUM(receita) OVER () AS pct_acumulado,
           ROW_NUMBER() OVER (ORDER BY receita DESC, produto_id) AS ranking
    FROM prod p
)
SELECT
    ranking, produto_id, nome, familia, subcategoria,
    ROUND(receita, 0)            AS receita,
    ROUND(100 * margem_bruta / receita, 1) AS margem_pct,
    ROUND(metros, 0)             AS metros_vendidos,
    ROUND(100 * pct_acumulado, 1) AS pct_receita_acumulada,
    CASE WHEN pct_acumulado <= 0.80 THEN 'A' WHEN pct_acumulado <= 0.95 THEN 'B' ELSE 'C' END AS classe
FROM acum
ORDER BY ranking;

-- Resumo por classe (rode separadamente):
-- SELECT classe, COUNT(*) produtos, SUM(receita) receita FROM (<consulta acima>) x GROUP BY classe;
