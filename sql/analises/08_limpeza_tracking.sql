-- =====================================================================
-- Diagnosis and cleanup of the tracking imperfections
-- (the same rules become dbt models: stg_eventos, stg_sessoes)
-- =====================================================================

-- 1) Duplicates: same event_id (browser + server, or network retry)
SELECT event_name, fonte, COUNT(*) AS eventos, COUNT(DISTINCT event_id) AS event_ids_unicos,
       COUNT(*) - COUNT(DISTINCT event_id) AS excedentes
FROM eventos GROUP BY event_name, fonte ORDER BY event_name, fonte;

-- 2) Reloaded purchase: new event_id, repeated transaction_id
SELECT COUNT(*) AS transacoes_com_mais_de_um_purchase
FROM (SELECT transaction_id FROM eventos WHERE event_name = 'purchase'
      GROUP BY transaction_id HAVING COUNT(DISTINCT event_id) > 1) x;

-- 3) Time zone: gap between the first event and the session start, by container version.
--    In UTC the median is close to 0; in v2.3 it shows -3 h (local time).
SELECT e.versao_container,
       ROUND(AVG(TIMESTAMPDIFF(MINUTE, s.iniciada_em, e.primeiro)), 0) AS dif_media_min,
       COUNT(*) AS sessoes
FROM (SELECT sessao_id, versao_container, MIN(event_timestamp) primeiro FROM eventos GROUP BY 1, 2) e
JOIN sessoes s USING (sessao_id)
GROUP BY e.versao_container ORDER BY e.versao_container;

-- 4) Lost attribution: paid sessions (with a recorded click) without UTMs, and utm_source spellings
SELECT utm_source, LOWER(TRIM(utm_source)) AS normalizado, COUNT(*) AS sessoes
FROM sessoes WHERE utm_source IS NOT NULL GROUP BY utm_source ORDER BY normalizado, sessoes DESC;

SELECT COUNT(*) AS sessoes_sem_nenhum_sinal_de_origem,
       ROUND(100 * COUNT(*) / (SELECT COUNT(*) FROM sessoes), 1) AS pct
FROM sessoes WHERE utm_source IS NULL AND referrer IS NULL AND gclid IS NULL AND fbclid IS NULL;

-- 5) Consent vs. sends to the platforms
SELECT plataforma, status, http_status, COUNT(*) AS envios, ROUND(AVG(event_match_quality), 1) AS emq_medio
FROM envios_conversao GROUP BY plataforma, status, http_status ORDER BY plataforma, envios DESC;

-- 6) Duplicate customers (same CPF, different e-mails)
SELECT cpf, COUNT(*) AS contas, GROUP_CONCAT(cliente_id ORDER BY cliente_id) AS ids
FROM clientes WHERE cpf IS NOT NULL GROUP BY cpf HAVING COUNT(*) > 1 LIMIT 20;
