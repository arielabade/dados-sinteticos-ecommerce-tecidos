-- =====================================================================
-- Segmentação RFM (recência, frequência, valor) em quintis
-- Data de referência = dia seguinte ao último pedido da base.
-- =====================================================================
WITH ref AS (SELECT DATE(MAX(criado_em)) + INTERVAL 1 DAY AS dia FROM pedidos),
cli AS (
    SELECT p.cliente_id,
           DATEDIFF((SELECT dia FROM ref), MAX(p.criado_em)) AS recencia_dias,
           COUNT(*)                                          AS frequencia,
           SUM(p.total)                                      AS valor
    FROM pedidos p
    WHERE p.pedido_teste = 0 AND p.status IN ('pago', 'enviado', 'entregue', 'devolvido')
    GROUP BY p.cliente_id
),
notas AS (
    SELECT c.*,
           6 - NTILE(5) OVER (ORDER BY recencia_dias)   AS r,  -- 5 = comprou há pouco
           NTILE(5) OVER (ORDER BY frequencia, valor)   AS f,
           NTILE(5) OVER (ORDER BY valor)               AS m
    FROM cli c
),
seg AS (
    SELECT n.*,
           CASE
             WHEN r >= 4 AND f >= 4 THEN 'Campeãs'
             WHEN r >= 3 AND f >= 3 THEN 'Leais'
             WHEN r >= 4 AND f <= 2 THEN 'Novas promissoras'
             WHEN r = 3 AND f <= 2  THEN 'Precisam de atenção'
             WHEN r <= 2 AND f >= 4 THEN 'Não pode perder'
             WHEN r <= 2 AND f = 3  THEN 'Em risco'
             ELSE 'Hibernando'
           END AS segmento
    FROM notas n
)
SELECT
    s.segmento,
    COUNT(*)                                AS clientes,
    ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_clientes,
    ROUND(AVG(s.recencia_dias), 0)          AS recencia_media_dias,
    ROUND(AVG(s.frequencia), 2)             AS pedidos_medios,
    ROUND(AVG(s.valor), 0)                  AS valor_medio,
    ROUND(100 * SUM(s.valor) / SUM(SUM(s.valor)) OVER (), 1) AS pct_receita,
    GROUP_CONCAT(DISTINCT c.tipo_cliente ORDER BY c.tipo_cliente) AS tipos_presentes
FROM seg s JOIN clientes c USING (cliente_id)
GROUP BY s.segmento
ORDER BY SUM(s.valor) DESC;
