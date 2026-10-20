# Intentional imperfections

Real e-commerce data never comes clean. Each problem below was inserted on purpose by the generator, at volumes similar to what shows up in production, so that the cleaning can be demonstrated. The **How to handle** column points to where the treatment is already implemented (dbt models in `dbt/models/staging` and queries in `sql/analises/08_limpeza_tracking.sql`).

## Tracking (server-side GTM)

| # | Imperfection | Where | Approximate volume | How to detect | How to handle |
|---|---|---|---|---|---|
| 1 | **Purchase duplicated by browser + server.** The purchase fires from the thank-you page (`fonte = 'web'`) and from the backend webhook (`fonte = 'server'`) with the **same `event_id`**. | `eventos` | ~65% of purchases arrive twice | `GROUP BY event_id HAVING COUNT(*) > 1` | Keep 1 row per `event_id` (`stg_eventos`). It is the same deduplication rule as the Meta CAPI. |
| 2 | **Network retry.** Any event repeated with the same `event_id` a few ms apart. | `eventos` | ~0.8% of events | same | same |
| 3 | **Thank-you page reload.** New purchase with a **new `event_id`**, but the same `transaction_id`. | `eventos` | ~3% of browser purchases | `COUNT(DISTINCT event_id)` per `transaction_id` | Deduplicate purchases by `transaction_id` (`stg_eventos`, dbt test `purchase_unico_por_pedido`). |
| 4 | **Inconsistent time zone.** sGTM container `v2.3` (Mar 1 to Jun 15, 2024) wrote `event_timestamp` in Brasília time instead of UTC. | `eventos.event_timestamp` | ~1.9 million events | A -3 h gap between the 1st event and `sessoes.iniciada_em` when `versao_container = 'v2.3'` | Add 3 h to those rows (`stg_eventos.event_timestamp_utc`). |
| 5 | **Different time zones per system (by design).** Orders in local time, tracking in UTC, media in the account time zone. | `pedidos`, `sessoes`, `*_metricas_diarias` | all rows | Compare `pedidos.criado_em` with the purchase of the same order | Convert everything to one time zone before joining (dbt macros `para_local`/`para_utc`). |
| 6 | **Sessions without attribution.** ~12% of sessions from Meta ads arrive without UTMs and without `fbclid` (in-app browser, link without parameters). Half still carry the `l.instagram.com` referrer; the other half becomes "Direct". ~3% of Google clicks lose the `gclid` in redirects and become "Organic Search". | `sessoes` | ~150k sessions | `clique_id IS NULL` with an in-app browser; sessions with neither referrer nor UTMs | It cannot be recovered safely. That is why the MMM and the prospecting pause (notebook 05) are needed. |
| 7 | **UTMs with different spellings.** `ig`, `IG`, `instagram`, `Instagram`; `paid_social`, `paid`, `cpc`, `Social`; `newsletter`, `Email`, `rdstation`. | `sessoes.utm_*` | ~10% of sessions with UTMs | `GROUP BY LOWER(utm_source)` | `LOWER(TRIM())` plus the channel map (macro `canal_padrao`). |
| 8 | **UTM template change.** Meta's `utm_campaign` carried the campaign name until May/2024 and the campaign **ID** afterwards. | `sessoes.utm_campaign` | all Meta sessions | Numeric vs. text values | Join through `cliques_midia` → ad → campaign, not through the UTM. |
| 9 | **Consent (LGPD / Consent Mode v2).** With `analytics_storage` denied, `client_id` is null; with `ad_storage` denied, there is no `fbp`/`fbc` and the Meta CAPI is not called. | `sessoes`, `envios_conversao` | ~28% without ad consent | `consent_*`, `status = 'bloqueado_consentimento'` | Treat as missing by design. It explains part of the gap with the platforms. |
| 10 | **CAPI incident.** Token expired after the deploy of container `v3.0`: every send to Meta failed with HTTP 401 from Jul 14, 3 pm to Jul 17, 2025, 11 am. | `envios_conversao` | ~3 days | `http_status = 401` | Monitor the daily error rate (alert). Meta's reported purchases drop on those days. |
| 11 | **Untracked orders.** ~13% of website orders have no session (ad blocker, browser without JS), and orders closed over WhatsApp never have one. | `pedidos.sessao_id` | ~20% of orders | `sessao_id IS NULL` | Report as "(não rastreado)" (untracked) instead of redistributing; MER does not depend on it. |

## Paid media

| # | Imperfection | Where | How to detect | How to handle |
|---|---|---|---|---|
| 12 | **Reported conversions ≠ real orders.** Meta counts 7-day click + 1-day view, includes modeled conversions and counts orders later canceled. Google uses a 30-day window, fractional credit, *engaged-view* conversions (PMax/Demand Gen) and records them on the click date. The platforms' total exceeds half of the real revenue. | `meta_metricas_diarias`, `google_metricas_diarias` | `sql/analises/06` and `07` | Read platform ROAS as a trend indicator, not as causality. Compare with last click (website), MER and MMM. |
| 13 | **Platform clicks > sessions.** Only 70% of Meta clicks and 88% of Google clicks become a recorded session. | `cliques_midia` vs. metrics | Clicks/sessions ratio per platform | Normal; track the rate as a tracking health metric. |
| 14 | **18-digit IDs.** Meta IDs do not fit in `float64` without losing precision. | `meta_*` | IDs that "change" when they pass through pandas | Read as `Int64`/text. |

## Registration and transactions

| # | Imperfection | Where | Volume | How to handle |
|---|---|---|---|---|
| 15 | Same person with **two accounts** (different e-mails, same CPF and name) | `clientes` | ~0.6% of accounts | Unify by CPF (`stg_clientes.cliente_id_unificado`), essential for LTV, RFM and churn. |
| 16 | **Team test orders**, some with status `pago` and a total of R$ 1.00 | `pedidos.pedido_teste = 1` | 12 orders | Filter `pedido_teste = 0`. |
| 17 | **Legacy base:** customers imported from the previous platform. Their first order in the period is not their real first order. | `clientes.origem_cadastro = 'importacao_legado'` | ~3,200 customers | Exclude from acquisition cohorts (`sql/analises/02`). |
| 18 | E-mail with uppercase letters or a leading space | `clientes.email` | ~1.5% | `LOWER(TRIM())`. |
| 19 | Phone numbers in different formats (`(11) 9...`, `+55 11 ...`, digits only) and ~17% null | `clientes.telefone` | — | Extract digits and standardize to E.164 (`stg_clientes.telefone_e164`). |
| 20 | Postal code without the hyphen; city without accents or in uppercase | `enderecos` | ~12% / ~6% | Normalize before grouping by city. |
| 21 | Registration nulls: birth date (~45%), gender (~60%), address complement (~55%), product description (~12%), fabric weight (~4%), card brand (~6%) | several | — | Treat as missing; do not impute gender. |
| 22 | **Delivered without a delivery date:** tracking never closed | `fretes.entregue_em` | ~2% of delivered orders | Exclude from the average delivery time or estimate from the promised time. |
| 23 | **Free shipping policy change** in Mar/2025 (threshold goes from R$ 149/249 to R$ 199/299) | `fretes.frete_gratis` | — | A real business change, not an error: control for it before comparing average order value across periods. |
| 24 | **Censored demand.** Sales do not show demand when the SKU is out of stock. | `estoque_diario` | ~3% of SKU-days | Use `demanda_perdida` / `em_ruptura` when training SKU-level forecasts (notebook 01). |
