-- =====================================================================
-- Funil GA4 por canal (sessões que atingiram cada etapa)
-- Limpeza aplicada: eventos deduplicados por event_id (o purchase chega do
-- navegador e do servidor com o mesmo event_id). Canal pela regra padrão de
-- agrupamento (UTM normalizada, click id e referrer).
-- Filtre o período em @inicio / @fim (horário UTC das sessões).
-- =====================================================================
SET @inicio = '2025-10-01', @fim = '2026-10-01';

WITH sess AS (
    SELECT s.sessao_id,
           CASE
             WHEN s.gclid IS NOT NULL THEN
               CASE gc.tipo_canal WHEN 'SHOPPING' THEN 'Paid Shopping' WHEN 'PERFORMANCE_MAX' THEN 'Cross-network'
                                  WHEN 'DEMAND_GEN' THEN 'Paid Video' ELSE 'Paid Search' END
             WHEN s.fbclid IS NOT NULL
               OR (LOWER(s.utm_source) IN ('fb','ig','an','facebook','instagram','igshopping')
                   AND LOWER(s.utm_medium) IN ('paid_social','paid','cpc')) THEN 'Paid Social'
             WHEN LOWER(s.utm_source) = 'google' AND LOWER(s.utm_medium) = 'cpc' THEN 'Paid Search'
             WHEN LOWER(s.utm_medium) = 'email' OR LOWER(s.utm_source) IN ('newsletter','email','rdstation') THEN 'Email'
             WHEN LOWER(s.utm_source) IN ('whatsapp','wpp') THEN 'WhatsApp'
             WHEN LOWER(s.utm_medium) IN ('social','bio') OR LOWER(s.utm_source) IN ('ig','instagram','linktree')
               OR s.referrer REGEXP 'instagram\\.com|facebook\\.com|pinterest\\.com|tiktok\\.com|youtube\\.com' THEN 'Organic Social'
             WHEN s.referrer REGEXP 'google\\.|bing\\.com|duckduckgo\\.com|search\\.yahoo' THEN 'Organic Search'
             WHEN s.referrer IS NOT NULL THEN 'Referral'
             WHEN s.utm_source IS NULL AND s.utm_medium IS NULL THEN 'Direct'
             ELSE 'Unassigned'
           END AS canal
    FROM sessoes s
    LEFT JOIN cliques_midia c          ON c.clique_id = s.clique_id
    LEFT JOIN google_grupos_anuncio gg ON gg.grupo_id = c.google_grupo_id
    LEFT JOIN google_campanhas gc      ON gc.campanha_id = gg.campanha_id
    WHERE s.iniciada_em >= @inicio AND s.iniciada_em < @fim
),
ev AS (  -- um registro por (sessão, etapa), já sem duplicatas
    SELECT DISTINCT e.sessao_id, e.event_name
    FROM eventos e JOIN sess USING (sessao_id)
    WHERE e.event_name <> 'page_view'
)
SELECT
    sess.canal,
    COUNT(*)                                                       AS sessoes,
    SUM(ev_vi.sessao_id IS NOT NULL)                               AS view_item,
    SUM(ev_atc.sessao_id IS NOT NULL)                              AS add_to_cart,
    SUM(ev_bc.sessao_id IS NOT NULL)                               AS begin_checkout,
    SUM(ev_api.sessao_id IS NOT NULL)                              AS add_payment_info,
    SUM(ev_p.sessao_id IS NOT NULL)                                AS purchase,
    ROUND(100 * SUM(ev_atc.sessao_id IS NOT NULL) / COUNT(*), 2)   AS taxa_carrinho_pct,
    ROUND(100 * SUM(ev_p.sessao_id IS NOT NULL) / NULLIF(SUM(ev_bc.sessao_id IS NOT NULL), 0), 1) AS conclusao_checkout_pct,
    ROUND(100 * SUM(ev_p.sessao_id IS NOT NULL) / COUNT(*), 2)     AS taxa_conversao_pct
FROM sess
LEFT JOIN ev ev_vi  ON ev_vi.sessao_id  = sess.sessao_id AND ev_vi.event_name  = 'view_item'
LEFT JOIN ev ev_atc ON ev_atc.sessao_id = sess.sessao_id AND ev_atc.event_name = 'add_to_cart'
LEFT JOIN ev ev_bc  ON ev_bc.sessao_id  = sess.sessao_id AND ev_bc.event_name  = 'begin_checkout'
LEFT JOIN ev ev_api ON ev_api.sessao_id = sess.sessao_id AND ev_api.event_name = 'add_payment_info'
LEFT JOIN ev ev_p   ON ev_p.sessao_id   = sess.sessao_id AND ev_p.event_name   = 'purchase'
GROUP BY sess.canal
ORDER BY sessoes DESC;
