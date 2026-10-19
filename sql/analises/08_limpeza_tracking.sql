-- =====================================================================
-- Diagnóstico e limpeza das imperfeições do tracking
-- (as mesmas regras viram modelos no dbt: stg_eventos, stg_sessoes)
-- =====================================================================

-- 1) Duplicatas: mesmo event_id (navegador + servidor, ou retry de rede)
SELECT event_name, fonte, COUNT(*) AS eventos, COUNT(DISTINCT event_id) AS event_ids_unicos,
       COUNT(*) - COUNT(DISTINCT event_id) AS excedentes
FROM eventos GROUP BY event_name, fonte ORDER BY event_name, fonte;

-- 2) purchase recarregado: event_id novo, transaction_id repetido
SELECT COUNT(*) AS transacoes_com_mais_de_um_purchase
FROM (SELECT transaction_id FROM eventos WHERE event_name = 'purchase'
      GROUP BY transaction_id HAVING COUNT(DISTINCT event_id) > 1) x;

-- 3) Fuso: diferença entre o primeiro evento e o início da sessão, por versão do container.
--    Em UTC a mediana fica perto de 0; na v2.3 aparece -3 h (horário local).
SELECT e.versao_container,
       ROUND(AVG(TIMESTAMPDIFF(MINUTE, s.iniciada_em, e.primeiro)), 0) AS dif_media_min,
       COUNT(*) AS sessoes
FROM (SELECT sessao_id, versao_container, MIN(event_timestamp) primeiro FROM eventos GROUP BY 1, 2) e
JOIN sessoes s USING (sessao_id)
GROUP BY e.versao_container ORDER BY e.versao_container;

-- 4) Atribuição perdida: sessões pagas (com clique registrado) sem UTM, e grafias de utm_source
SELECT utm_source, LOWER(TRIM(utm_source)) AS normalizado, COUNT(*) AS sessoes
FROM sessoes WHERE utm_source IS NOT NULL GROUP BY utm_source ORDER BY normalizado, sessoes DESC;

SELECT COUNT(*) AS sessoes_sem_nenhum_sinal_de_origem,
       ROUND(100 * COUNT(*) / (SELECT COUNT(*) FROM sessoes), 1) AS pct
FROM sessoes WHERE utm_source IS NULL AND referrer IS NULL AND gclid IS NULL AND fbclid IS NULL;

-- 5) Consentimento x envio para plataformas
SELECT plataforma, status, http_status, COUNT(*) AS envios, ROUND(AVG(event_match_quality), 1) AS emq_medio
FROM envios_conversao GROUP BY plataforma, status, http_status ORDER BY plataforma, envios DESC;

-- 6) Clientes duplicados (mesmo CPF, e-mails diferentes)
SELECT cpf, COUNT(*) AS contas, GROUP_CONCAT(cliente_id ORDER BY cliente_id) AS ids
FROM clientes WHERE cpf IS NOT NULL GROUP BY cpf HAVING COUNT(*) > 1 LIMIT 20;
