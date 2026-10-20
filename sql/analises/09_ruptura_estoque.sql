-- =====================================================================
-- Stockouts: days without stock and lost demand by subcategory
-- and month. Shows the effect of the unreliable chita supplier during the June festivals.
-- =====================================================================
SELECT
    DATE_FORMAT(ed.data, '%Y-%m')             AS mes,
    cat.nome                                  AS subcategoria,
    COUNT(*)                                  AS sku_dias,
    SUM(ed.em_ruptura)                        AS sku_dias_ruptura,
    ROUND(100 * AVG(ed.em_ruptura), 1)        AS pct_ruptura,
    ROUND(SUM(ed.demanda_perdida * v.metros_por_unidade), 0) AS metros_perdidos,
    ROUND(SUM(ed.demanda_perdida * v.preco_atual), 0)        AS receita_perdida_estimada
FROM estoque_diario ed
JOIN variantes v    ON v.variante_id = ed.variante_id
JOIN produtos p     ON p.produto_id = v.produto_id
JOIN categorias cat ON cat.categoria_id = p.categoria_id
GROUP BY 1, 2
HAVING sku_dias_ruptura > 0
ORDER BY receita_perdida_estimada DESC
LIMIT 40;
