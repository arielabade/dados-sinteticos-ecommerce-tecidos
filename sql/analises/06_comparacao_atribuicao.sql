-- =====================================================================
-- Comparação entre modelos de atribuição (receita de pedidos pagos)
-- e o que cada plataforma reporta no mesmo período.
-- Pedidos sem rastreio (adblock, WhatsApp) não entram em nenhum modelo:
-- aparecem na linha "(não rastreado)" para fechar a conta com a receita real.
-- =====================================================================
SET @inicio = '2025-10-01', @fim = '2026-10-14';

WITH pagos AS (
    SELECT pedido_id, total, sessao_id FROM pedidos
    WHERE pedido_teste = 0 AND status IN ('pago', 'enviado', 'entregue', 'devolvido')
      AND criado_em >= @inicio AND criado_em < @fim
),
por_modelo AS (
    SELECT a.canal,
           SUM(CASE WHEN a.modelo = 'last_click'  THEN a.receita_atribuida END) AS last_click,
           SUM(CASE WHEN a.modelo = 'first_click' THEN a.receita_atribuida END) AS first_click,
           SUM(CASE WHEN a.modelo = 'linear'      THEN a.receita_atribuida END) AS `linear`,
           SUM(CASE WHEN a.modelo = 'data_driven' THEN a.receita_atribuida END) AS data_driven
    FROM atribuicoes a JOIN pagos p USING (pedido_id)
    GROUP BY a.canal
    UNION ALL
    SELECT '(não rastreado)', SUM(total), SUM(total), SUM(total), SUM(total)
    FROM pagos WHERE sessao_id IS NULL
)
SELECT
    canal,
    ROUND(last_click, 0)  AS last_click,
    ROUND(first_click, 0) AS first_click,
    ROUND(`linear`, 0)    AS `linear`,
    ROUND(data_driven, 0) AS data_driven,
    ROUND(100 * (first_click - last_click) / NULLIF(last_click, 0), 1) AS dif_first_vs_last_pct,
    ROUND(100 * last_click / SUM(last_click) OVER (), 1)               AS share_last_click_pct,
    ROUND(100 * data_driven / SUM(data_driven) OVER (), 1)             AS share_data_driven_pct
FROM por_modelo
ORDER BY last_click DESC;

-- O que as plataformas dizem no mesmo período (some com a receita real para ver a sobreposição)
SELECT 'Meta (7d clique + 1d view)' AS fonte, ROUND(SUM(valor_compras), 0) AS receita_reportada
FROM meta_metricas_diarias WHERE data >= @inicio AND data < @fim
UNION ALL
SELECT 'Google Ads (DDA, 30d clique)', ROUND(SUM(valor_conversao), 0)
FROM google_metricas_diarias WHERE data >= @inicio AND data < @fim
UNION ALL
SELECT 'Receita real paga (todos os canais)', ROUND(SUM(total), 0)
FROM pedidos WHERE pedido_teste = 0 AND status IN ('pago', 'enviado', 'entregue', 'devolvido')
  AND criado_em >= @inicio AND criado_em < @fim;
