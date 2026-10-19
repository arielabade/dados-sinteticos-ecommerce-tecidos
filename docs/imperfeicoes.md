# Imperfeições propositais

Dados reais de e-commerce nunca vêm limpos. Cada problema abaixo foi inserido de propósito pelo gerador, com volume parecido com o que se vê em produção, para que a limpeza possa ser demonstrada. A coluna **Como tratar** aponta onde o tratamento já está implementado (modelos dbt em `dbt/models/staging` e consultas em `sql/analises/08_limpeza_tracking.sql`).

## Tracking (GTM server-side)

| # | Imperfeição | Onde | Volume aproximado | Como detectar | Como tratar |
|---|---|---|---|---|---|
| 1 | **Purchase duplicado navegador + servidor.** O purchase sai da página de obrigado (`fonte = 'web'`) e do webhook do backend (`fonte = 'server'`) com o **mesmo `event_id`**. | `eventos` | ~65% dos purchases chegam 2x | `GROUP BY event_id HAVING COUNT(*) > 1` | Manter 1 linha por `event_id` (`stg_eventos`). É a mesma regra de deduplicação da Meta CAPI. |
| 2 | **Retry de rede.** Qualquer evento repetido com o mesmo `event_id` e alguns ms de diferença. | `eventos` | ~0,8% dos eventos | idem | idem |
| 3 | **Recarga da página de obrigado.** Novo purchase com **`event_id` novo**, mas o mesmo `transaction_id`. | `eventos` | ~3% dos purchases vindos do navegador | `COUNT(DISTINCT event_id)` por `transaction_id` | Deduplicar purchase por `transaction_id` (`stg_eventos`, teste dbt `purchase_unico_por_pedido`). |
| 4 | **Fuso horário inconsistente.** O container sGTM `v2.3` (01/03 a 15/06/2024) gravou `event_timestamp` em horário de Brasília em vez de UTC. | `eventos.event_timestamp` | ~1,9 milhão de eventos | Diferença de -3 h entre o 1º evento e `sessoes.iniciada_em` quando `versao_container = 'v2.3'` | Somar 3 h nessas linhas (`stg_eventos.event_timestamp_utc`). |
| 5 | **Fusos diferentes por sistema (por desenho).** Pedidos em horário local, tracking em UTC, mídia no fuso da conta. | `pedidos`, `sessoes`, `*_metricas_diarias` | todas as linhas | Comparar `pedidos.criado_em` com o purchase do mesmo pedido | Converter tudo para um fuso antes de cruzar (macros `para_local`/`para_utc` do dbt). |
| 6 | **Sessões sem atribuição.** ~12% das sessões vindas de anúncios Meta chegam sem UTM e sem `fbclid` (navegador in-app, link sem parâmetro). Metade ainda traz o referrer `l.instagram.com`; a outra metade vira "Direct". ~3% dos cliques Google perdem o `gclid` em redirecionamentos e viram "Organic Search". | `sessoes` | ~150 mil sessões | `clique_id IS NULL` com navegador in-app; sessões sem referrer nem UTM | Não há como recuperar com segurança. Por isso o MMM e a pausa de prospecção (notebook 05) são necessários. |
| 7 | **UTMs com grafias diferentes.** `ig`, `IG`, `instagram`, `Instagram`; `paid_social`, `paid`, `cpc`, `Social`; `newsletter`, `Email`, `rdstation`. | `sessoes.utm_*` | ~10% das sessões com UTM | `GROUP BY LOWER(utm_source)` | `LOWER(TRIM())` mais o mapa de canais (macro `canal_padrao`). |
| 8 | **Troca de template de UTM.** `utm_campaign` da Meta trazia o nome da campanha até mai/2024 e passou a trazer o **ID** depois. | `sessoes.utm_campaign` | todas as sessões Meta | Valores numéricos x textuais | Ligar pela tabela `cliques_midia` → anúncio → campanha, não pela UTM. |
| 9 | **Consentimento (LGPD/Consent Mode v2).** Com `analytics_storage` negado, `client_id` fica nulo; com `ad_storage` negado, não há `fbp`/`fbc` e a Meta CAPI não é chamada. | `sessoes`, `envios_conversao` | ~28% sem consentimento de anúncios | `consent_*`, `status = 'bloqueado_consentimento'` | Tratar como dado ausente por desenho. Explica parte da divergência com as plataformas. |
| 10 | **Incidente na CAPI.** Token expirado após o deploy do container `v3.0`: todos os envios à Meta falharam com HTTP 401 de 14/07 15h a 17/07/2025 11h. | `envios_conversao` | ~3 dias | `http_status = 401` | Monitorar a taxa de erro por dia (alerta). As compras reportadas pela Meta caem nesses dias. |
| 11 | **Pedidos sem rastreio.** ~13% dos pedidos do site não têm sessão (adblock, navegador sem JS) e os pedidos fechados pelo WhatsApp nunca têm. | `pedidos.sessao_id` | ~20% dos pedidos | `sessao_id IS NULL` | Reportar como "(não rastreado)" em vez de redistribuir; o MER não depende disso. |

## Mídia paga

| # | Imperfeição | Onde | Como detectar | Como tratar |
|---|---|---|---|---|
| 12 | **Conversões reportadas ≠ pedidos reais.** A Meta conta 7 dias após o clique + 1 dia após a visualização, inclui conversões modeladas e conta pedidos depois cancelados. O Google usa janela de 30 dias, crédito fracionado, conversões por *engaged view* (PMax/Demand Gen) e registra na data do clique. A soma das plataformas passa da metade da receita real. | `meta_metricas_diarias`, `google_metricas_diarias` | `sql/analises/06` e `07` | Ler ROAS da plataforma como indicador de tendência, não de causalidade. Comparar com last click (site), MER e MMM. |
| 13 | **Cliques da plataforma > sessões.** Só 70% dos cliques da Meta e 88% dos do Google viram sessão registrada. | `cliques_midia` x métricas | Razão cliques/sessões por plataforma | Normal; acompanhar a taxa como saúde do tracking. |
| 14 | **IDs de 18 dígitos.** IDs da Meta não cabem em `float64` sem perder precisão. | `meta_*` | IDs que "mudam" ao passar pelo pandas | Ler como `Int64`/texto. |

## Cadastro e transações

| # | Imperfeição | Onde | Volume | Como tratar |
|---|---|---|---|---|
| 15 | Mesma pessoa com **duas contas** (e-mails diferentes, mesmo CPF e nome) | `clientes` | ~0,6% das contas | Unificar pelo CPF (`stg_clientes.cliente_id_unificado`), essencial para LTV, RFM e churn. |
| 16 | **Pedidos de teste** da equipe, alguns com status `pago` e total de R$ 1,00 | `pedidos.pedido_teste = 1` | 12 pedidos | Filtrar `pedido_teste = 0`. |
| 17 | **Base legada:** clientes importados da plataforma anterior. A 1ª compra deles no período não é a 1ª de verdade. | `clientes.origem_cadastro = 'importacao_legado'` | ~3.200 clientes | Excluir das coortes de aquisição (`sql/analises/02`). |
| 18 | E-mail com maiúsculas ou espaço à esquerda | `clientes.email` | ~1,5% | `LOWER(TRIM())`. |
| 19 | Telefone em formatos diferentes (`(11) 9...`, `+55 11 ...`, só dígitos) e ~17% nulo | `clientes.telefone` | — | Extrair dígitos e padronizar em E.164 (`stg_clientes.telefone_e164`). |
| 20 | CEP sem hífen; cidade sem acento ou em maiúsculas | `enderecos` | ~12% / ~6% | Normalizar antes de agrupar por cidade. |
| 21 | Nulos de cadastro: data de nascimento (~45%), gênero (~60%), complemento (~55%), descrição de produto (~12%), gramatura (~4%), bandeira do cartão (~6%) | várias | — | Tratar como ausentes; não imputar gênero. |
| 22 | **Entregue sem data de entrega:** rastreio sem baixa | `fretes.entregue_em` | ~2% dos entregues | Excluir do cálculo de prazo médio ou estimar pelo prazo prometido. |
| 23 | **Mudança de política de frete grátis** em mar/2025 (limite sobe de R$ 149/249 para R$ 199/299) | `fretes.frete_gratis` | — | É mudança real de negócio, não erro: controle por ela antes de comparar ticket médio entre períodos. |
| 24 | **Demanda censurada.** Vendas não mostram a demanda quando o SKU está sem estoque. | `estoque_diario` | ~3% dos SKU-dias | Usar `demanda_perdida` / `em_ruptura` ao treinar previsão por SKU (notebook 01). |
