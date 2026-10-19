-- =====================================================================
-- CAC, ROAS e MER por mês
-- * MER  = receita paga total / investimento total (visão "blended", não
--          depende de atribuição).
-- * ROAS plataforma = valor de conversão reportado / investimento.
-- * ROAS last click = receita atribuída pelo site (último clique não direto)
--          / investimento.
-- * CAC blended = investimento total / clientes novos no mês.
-- Pedidos de teste excluídos; receita só de pedidos pagos.
-- =====================================================================
WITH pedidos_pagos AS (
    SELECT p.pedido_id, p.cliente_id, p.total, DATE_FORMAT(p.criado_em, '%Y-%m') AS mes,
           ROW_NUMBER() OVER (PARTITION BY p.cliente_id ORDER BY p.criado_em, p.pedido_id) AS seq
    FROM pedidos p
    WHERE p.pedido_teste = 0 AND p.status IN ('pago', 'enviado', 'entregue', 'devolvido')
),
receita AS (
    SELECT mes, SUM(total) AS receita, COUNT(*) AS pedidos, SUM(seq = 1) AS clientes_novos
    FROM pedidos_pagos GROUP BY mes
),
invest AS (
    SELECT DATE_FORMAT(data, '%Y-%m') AS mes,
           SUM(investimento) AS inv_meta, 0 AS inv_google,
           SUM(valor_compras) AS valor_meta, 0 AS valor_google
    FROM meta_metricas_diarias GROUP BY 1
    UNION ALL
    SELECT DATE_FORMAT(data, '%Y-%m'), 0, SUM(investimento), 0, SUM(valor_conversao)
    FROM google_metricas_diarias GROUP BY 1
),
invest_mes AS (
    SELECT mes, SUM(inv_meta) inv_meta, SUM(inv_google) inv_google,
           SUM(valor_meta) valor_meta, SUM(valor_google) valor_google
    FROM invest GROUP BY mes
),
last_click AS (
    SELECT DATE_FORMAT(p.criado_em, '%Y-%m') AS mes,
           SUM(CASE WHEN a.meta_campanha_id   IS NOT NULL THEN a.receita_atribuida END) AS receita_lc_meta,
           SUM(CASE WHEN a.google_campanha_id IS NOT NULL THEN a.receita_atribuida END) AS receita_lc_google
    FROM atribuicoes a
    JOIN pedidos p ON p.pedido_id = a.pedido_id
    WHERE a.modelo = 'last_click' AND p.status IN ('pago', 'enviado', 'entregue', 'devolvido')
    GROUP BY 1
)
SELECT
    r.mes,
    r.pedidos,
    ROUND(r.receita, 0)                                   AS receita,
    r.clientes_novos,
    ROUND(i.inv_meta + i.inv_google, 0)                   AS investimento_total,
    ROUND(i.inv_meta, 0)                                  AS investimento_meta,
    ROUND(i.inv_google, 0)                                AS investimento_google,
    ROUND(r.receita / (i.inv_meta + i.inv_google), 2)     AS mer,
    ROUND((i.inv_meta + i.inv_google) / r.clientes_novos, 2) AS cac_blended,
    ROUND(i.valor_meta / i.inv_meta, 2)                   AS roas_meta_plataforma,
    ROUND(lc.receita_lc_meta / i.inv_meta, 2)             AS roas_meta_last_click,
    ROUND(i.valor_google / i.inv_google, 2)               AS roas_google_plataforma,
    ROUND(lc.receita_lc_google / i.inv_google, 2)         AS roas_google_last_click
FROM receita r
JOIN invest_mes i USING (mes)
LEFT JOIN last_click lc USING (mes)
ORDER BY r.mes;
