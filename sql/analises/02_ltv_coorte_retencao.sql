-- =====================================================================
-- LTV por coorte e retenção
-- Coorte = mês da primeira compra paga. Clientes unificados pelo CPF
-- (contas duplicadas da mesma pessoa contam como uma).
-- A base legada (origem_cadastro = 'importacao_legado') fica de fora: a
-- primeira compra dela no período não é a primeira compra de verdade.
-- Saída: para cada coorte, % de clientes ativos e receita acumulada por
-- cliente nos meses 0, 1, 2, 3, 6 e 12 após a primeira compra.
-- =====================================================================
WITH clientes_unif AS (
    SELECT cliente_id, IF(cpf IS NULL, cliente_id, MIN(cliente_id) OVER (PARTITION BY cpf)) AS cliente_unif,
           origem_cadastro
    FROM clientes
),
pp AS (
    SELECT cu.cliente_unif, p.criado_em, p.total
    FROM pedidos p JOIN clientes_unif cu USING (cliente_id)
    WHERE p.pedido_teste = 0 AND p.status IN ('pago', 'enviado', 'entregue', 'devolvido')
      AND cu.cliente_unif NOT IN (SELECT cliente_id FROM clientes WHERE origem_cadastro = 'importacao_legado')
),
primeira AS (
    SELECT cliente_unif, MIN(criado_em) AS primeira_compra FROM pp GROUP BY cliente_unif
),
base AS (
    SELECT pr.cliente_unif,
           DATE_FORMAT(pr.primeira_compra, '%Y-%m') AS coorte,
           TIMESTAMPDIFF(MONTH, DATE_FORMAT(pr.primeira_compra, '%Y-%m-01'), DATE_FORMAT(pp.criado_em, '%Y-%m-01')) AS mes_vida,
           pp.total
    FROM pp JOIN primeira pr USING (cliente_unif)
),
tam AS (
    SELECT coorte, COUNT(DISTINCT cliente_unif) AS clientes FROM base GROUP BY coorte
),
idade AS (  -- meses observáveis de cada coorte até o fim dos dados
    SELECT coorte, TIMESTAMPDIFF(MONTH, CONCAT(coorte, '-01'), (SELECT DATE_FORMAT(MAX(criado_em), '%Y-%m-01') FROM pedidos)) AS meses_obs
    FROM tam
)
SELECT
    t.coorte,
    t.clientes,
    ROUND(100 * COUNT(DISTINCT CASE WHEN b.mes_vida = 1  THEN b.cliente_unif END) / t.clientes, 1) AS ret_m1_pct,
    ROUND(100 * COUNT(DISTINCT CASE WHEN b.mes_vida = 3  THEN b.cliente_unif END) / t.clientes, 1) AS ret_m3_pct,
    CASE WHEN i.meses_obs >= 6  THEN ROUND(100 * COUNT(DISTINCT CASE WHEN b.mes_vida = 6  THEN b.cliente_unif END) / t.clientes, 1) END AS ret_m6_pct,
    CASE WHEN i.meses_obs >= 12 THEN ROUND(100 * COUNT(DISTINCT CASE WHEN b.mes_vida = 12 THEN b.cliente_unif END) / t.clientes, 1) END AS ret_m12_pct,
    ROUND(SUM(CASE WHEN b.mes_vida = 0  THEN b.total ELSE 0 END) / t.clientes, 2) AS ltv_m0,
    ROUND(SUM(CASE WHEN b.mes_vida <= 3 THEN b.total ELSE 0 END) / t.clientes, 2) AS ltv_m3,
    CASE WHEN i.meses_obs >= 6  THEN ROUND(SUM(CASE WHEN b.mes_vida <= 6  THEN b.total ELSE 0 END) / t.clientes, 2) END AS ltv_m6,
    CASE WHEN i.meses_obs >= 12 THEN ROUND(SUM(CASE WHEN b.mes_vida <= 12 THEN b.total ELSE 0 END) / t.clientes, 2) END AS ltv_m12,
    CASE WHEN i.meses_obs >= 24 THEN ROUND(SUM(CASE WHEN b.mes_vida <= 24 THEN b.total ELSE 0 END) / t.clientes, 2) END AS ltv_m24
FROM tam t
JOIN base b USING (coorte)
JOIN idade i USING (coorte)
GROUP BY t.coorte, t.clientes, i.meses_obs
ORDER BY t.coorte;
