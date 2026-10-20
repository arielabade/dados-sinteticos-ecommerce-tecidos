# Entity-relationship diagrams

The `tecidos` database has **44 tables in 7 areas**. Instead of a single diagram, which inevitably crosses lines, there is
an overview and one diagram per area. They are all generated from `schema.sql` by
[`scripts/gerar_diagramas.py`](../scripts/gerar_diagramas.py).

The whole model on one page is in [`diagramas/modelo_de_dados_one_pager.svg`](diagramas/modelo_de_dados_one_pager.svg)
(also as [PNG](diagramas/modelo_de_dados_one_pager.png) and [PDF](diagramas/modelo_de_dados_one_pager.pdf)).

## How to read them

- **Solid box:** a table of the area, with its main fields (the complete list is in
  [`dicionario_dados.md`](dicionario_dados.md)).
  - **PK**, **FK** and **UK** mark the keys.
  - `field?` is nullable.
  - The MySQL type is on the right.
- **Dashed box:** a table from another area, drawn only to show the link. The note says which diagram details it.
- **Crow's foot at the line ends** (no arrows: the relationship works both ways):

| Symbol | Meaning |
|---|---|
| `──┼┼` | exactly one |
| `──○┼` | zero or one (the FK is nullable) |
| `──┼<` | one or more |
| `──○<` | zero or more |

- **Dashed line:** logical link with no physical FK in the database (e.g. `enderecos.uf` → `regioes`).

The minimums that the DDL does not show were checked against the data. For example:
- every product has at least one variant;
- every order has an item, a payment and exactly one shipment;
- every customer has an address.

### Diagramming rules

| Rule | How it was applied |
|---|---|
| No line crosses another or goes through a table | Checked in code: the build fails if there is a crossing, a line over a table or a label covering another line |
| Horizontal and vertical segments only, one path per relationship | Orthogonal connectors with distinct exit points |
| Parent above or to the left of the child | Read top-down and left-to-right (account → campaign → ad → metric) |
| Large diagrams split into parts | 6 areas of 5 to 11 tables, with white space between boxes |
| Consistent notation | Crow's foot everywhere; each line's label is the verb of the relationship |

Sources: [Ambler, *The Elements of UML 2.0 Style*, chapter "General Diagramming Guidelines"](https://www.cambridge.org/core/books/elements-of-uml-20-style/general-diagramming-guidelines/9C2553636C85C84B03ABCB9311158553),
[Napier University, *Drawing ERDs with draw.io*](https://bdavison.napier.ac.uk/db/Practicals/Drawio/erd/) and
[Utah Tech, *ERD conventions*](https://cs.utahtech.edu/it/4310/Design/Historical-4.pdf).

---

## Overview

![Overview: the 7 areas and the keys that link them](diagramas/00_visao_geral.svg)

The areas are linked by a few keys:
- `variante_id` links the catalog to sales and to events;
- `sessao_id` and `pedido_id` link sales and tracking;
- the ad, ad group, keyword and campaign IDs link the platforms to tracking and attribution.

The MMM layer has no FK to the rest: it links through the state (UF) and the date, and its totals reconcile with each
platform's reports.

## 1. Catalog and inventory

![Catalog and inventory](diagramas/01_catalogo_estoque.svg)

- **Product and variant:** `produtos` is the fabric article; `variantes` is the SKU sold (color, print, sales format).
- **Categories:** they form a hierarchy (`categoria_pai_id`, the loop on `categorias`).
- **Price:** `historico_precos` keeps price and cost with validity periods (SCD type 2); `variantes.preco_atual` is only the
  current snapshot.
- **Inventory:**
  - `estoque` is the current balance (1:1 with the variant);
  - `estoque_diario` is each day's closing, with `em_ruptura` (stockout) and the `demanda_perdida` (lost demand) that
    sales do not show;
  - `movimentacoes_estoque` is the stock ledger, linked to the order, the return or the supplier purchase.

## 2. Customers, orders and after-sales

![Customers, orders and after-sales](diagramas/02_clientes_pedidos.svg)

- **Order:**
  - the customer is mandatory;
  - address, session and coupon may be missing (order via WhatsApp, untracked, or without a coupon).
- **Payment:** `pagamentos` stores each attempt (a declined card followed by an approved one = two rows).
- **Shipping:** `fretes` is 1:1 with the order.
- **Return:** points to the order and to the returned item.
- **Review:** links customer, order and product.

## 3. Website tracking and attribution

![Website tracking and attribution](diagramas/03_tracking_atribuicao.svg)

The chain is **click → session → events → order**:
- **Click:** `cliques_midia` is the click recorded by the platform (fbclid or gclid) and generates at most one session.
- **Session and events:** `eventos` is the GA4 log sent by server-side GTM. A purchase arrives twice (browser and server)
  with the same `event_id`.
- **Sends to Meta and Google:** `envios_conversao` records each send to the Meta CAPI and to Google's Enhanced
  Conversions.
- **Attribution:** `atribuicoes` splits the credit of each order across the touchpoints (sessions) and campaigns, in
  several models.

The imperfections in this area (duplicates, wrong time zone, sessions without UTMs, expired CAPI token) are in
[`imperfeicoes.md`](imperfeicoes.md).

## 4. Meta Ads

![Meta Ads](diagramas/04_meta_ads.svg)

- **Hierarchy:** the same as the Marketing API (account → campaign → ad set → ad).
- **Daily insights:** `meta_metricas_diarias` has one record per ad per day, with reach (only Meta reports it) and
  purchases under the platform's window (7-day click, 1-day view).
- **IDs:** the IDs have 18 digits; read them as text or `Int64`.

## 5. Google Ads

![Google Ads](diagramas/05_google_ads.svg)

- **Hierarchy:** account → campaign (Search, Shopping, PMax, Demand Gen) → ad group (or asset group, in PMax) → keyword.
- **Metrics:** `google_metricas_diarias` has one record per ad group and day, with the Search impression share.
- **Keywords:** `google_palavras_chave_metricas_diarias` only details the Search campaigns, and its sum matches the ad
  group's.

## 6. Regional MMM, geo tests and other channels

![Regional MMM, geo tests and other channels](diagramas/06_mmm_outros_canais.svg)

Tables created for the [marketing-mix-modeling](https://github.com/arielabade/marketing-mix-modeling) project.

- **Media by state:** `midia_regional_diaria` is the geographic report of every platform at the same grain
  (day × channel × state). Its sum by day and platform matches `meta_metricas_diarias`, `google_metricas_diarias`,
  `tiktok_metricas_diarias`, `afiliados_metricas_diarias` and `crm_disparos`.
- **Link to sales:** the state links media to sales through the orders' shipping address, and `calendario_comercial`
  through the date. These are logical links, with no physical FK.
- **Geo tests:** `testes_geo` and `testes_geo_regioes` record the geo-lift tests and the group (treatment or control) of
  each state.
