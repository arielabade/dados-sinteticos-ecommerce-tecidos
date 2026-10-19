-- =====================================================================
-- Investimento ao lado de conversões e valor de conversão, por campanha
-- (Meta e Google). Compara o reportado pela plataforma com os pedidos
-- pagos atribuídos pelo site (last click e data-driven).
-- =====================================================================
WITH midia AS (
    SELECT 'meta' AS plataforma, cp.campanha_id, cp.nome AS campanha, cp.estrategia AS tipo,
           SUM(m.investimento) inv, SUM(m.impressoes) imp, SUM(m.cliques_link) cliques,
           SUM(m.compras) conv_plat, SUM(m.valor_compras) valor_plat
    FROM meta_metricas_diarias m
    JOIN meta_anuncios a   ON a.anuncio_id = m.anuncio_id
    JOIN meta_conjuntos cj ON cj.conjunto_id = a.conjunto_id
    JOIN meta_campanhas cp ON cp.campanha_id = cj.campanha_id
    GROUP BY cp.campanha_id, cp.nome, cp.estrategia
    UNION ALL
    SELECT 'google', c.campanha_id, c.nome, IF(c.campanha_marca, 'SEARCH_MARCA', c.tipo_canal),
           SUM(g.investimento), SUM(g.impressoes), SUM(g.cliques), SUM(g.conversoes), SUM(g.valor_conversao)
    FROM google_metricas_diarias g
    JOIN google_grupos_anuncio gr ON gr.grupo_id = g.grupo_id
    JOIN google_campanhas c       ON c.campanha_id = gr.campanha_id
    GROUP BY c.campanha_id, c.nome, c.tipo_canal, c.campanha_marca
),
site AS (
    SELECT COALESCE(a.meta_campanha_id, a.google_campanha_id) AS campanha_id,
           SUM(CASE WHEN modelo = 'last_click'  THEN peso END)              AS pedidos_lc,
           SUM(CASE WHEN modelo = 'last_click'  THEN receita_atribuida END) AS receita_lc,
           SUM(CASE WHEN modelo = 'data_driven' THEN receita_atribuida END) AS receita_dd
    FROM atribuicoes a
    JOIN pedidos p ON p.pedido_id = a.pedido_id AND p.status IN ('pago', 'enviado', 'entregue', 'devolvido')
    WHERE a.meta_campanha_id IS NOT NULL OR a.google_campanha_id IS NOT NULL
    GROUP BY 1
)
SELECT
    m.plataforma, m.campanha, m.tipo,
    ROUND(m.inv, 0)                            AS investimento,
    m.imp                                      AS impressoes,
    m.cliques,
    ROUND(100 * m.cliques / m.imp, 2)          AS ctr_pct,
    ROUND(m.inv / m.cliques, 2)                AS cpc,
    ROUND(m.conv_plat, 0)                      AS conversoes_plataforma,
    ROUND(m.valor_plat, 0)                     AS valor_conversao_plataforma,
    ROUND(m.valor_plat / m.inv, 2)             AS roas_plataforma,
    ROUND(COALESCE(s.pedidos_lc, 0), 0)        AS pedidos_last_click,
    ROUND(COALESCE(s.receita_lc, 0), 0)        AS receita_last_click,
    ROUND(COALESCE(s.receita_lc, 0) / m.inv, 2) AS roas_last_click,
    ROUND(COALESCE(s.receita_dd, 0) / m.inv, 2) AS roas_data_driven,
    ROUND(m.conv_plat / NULLIF(s.pedidos_lc, 0), 2) AS razao_plataforma_vs_site
FROM midia m
LEFT JOIN site s ON s.campanha_id = m.campanha_id
ORDER BY m.plataforma, m.inv DESC;
