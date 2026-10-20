# Diagramas entidade-relacionamento

O banco `tecidos` tem **44 tabelas em 7 áreas**. Em vez de um diagrama único, que inevitavelmente cruza linhas, há uma
visão geral e um diagrama por área. Todos são gerados do `schema.sql` por
[`scripts/gerar_diagramas.py`](../scripts/gerar_diagramas.py).

O modelo inteiro numa página está em [`diagramas/modelo_de_dados_one_pager.svg`](diagramas/modelo_de_dados_one_pager.svg)
(também em [PNG](diagramas/modelo_de_dados_one_pager.png) e [PDF](diagramas/modelo_de_dados_one_pager.pdf)).

## Como ler

- **Caixa cheia:** uma tabela da área, com os campos principais (o dicionário completo está em
  [`dicionario_dados.md`](dicionario_dados.md)).
  - **PK**, **FK** e **UK** marcam as chaves.
  - `campo?` aceita nulo.
  - À direita fica o tipo no MySQL.
- **Caixa tracejada:** tabela de outra área, desenhada só para mostrar a ligação. O número indica o diagrama onde ela está
  detalhada.
- **Pé de galinha nas pontas** (sem setas: o relacionamento vale nos dois sentidos):

| Símbolo | Leitura |
|---|---|
| `──┼┼` | exatamente um |
| `──○┼` | zero ou um (a FK aceita nulo) |
| `──┼<` | um ou mais |
| `──○<` | zero ou mais |

- **Linha tracejada:** ligação lógica, sem FK física no banco (ex.: `enderecos.uf` → `regioes`).

Os mínimos que o DDL não mostra foram conferidos nos dados. Por exemplo:
- todo produto tem pelo menos uma variante;
- todo pedido tem item, pagamento e exatamente um frete;
- todo cliente tem endereço.

### Regras de diagramação

| Regra | Como foi aplicada |
|---|---|
| Nenhuma linha cruza outra ou atravessa uma tabela | Verificado por código: a geração falha se houver cruzamento, linha sobre tabela ou rótulo cobrindo outra linha |
| Só segmentos horizontais e verticais, um traçado por relacionamento | Conectores ortogonais com pontos de saída distintos |
| Pai acima ou à esquerda do filho | Leitura de cima para baixo e da esquerda para a direita (conta → campanha → anúncio → métrica) |
| Diagrama grande quebrado em partes | 6 áreas de 5 a 11 tabelas, com espaço em branco entre as caixas |
| Notação consistente | Pé de galinha em todos; o rótulo de cada linha é o verbo da relação |

Fontes: [Ambler, *The Elements of UML 2.0 Style*, cap. "General Diagramming Guidelines"](https://www.cambridge.org/core/books/elements-of-uml-20-style/general-diagramming-guidelines/9C2553636C85C84B03ABCB9311158553),
[Napier University, *Drawing ERDs with draw.io*](https://bdavison.napier.ac.uk/db/Practicals/Drawio/erd/) e
[Utah Tech, *ERD conventions*](https://cs.utahtech.edu/it/4310/Design/Historical-4.pdf).

---

## Visão geral

![Visão geral: as 7 áreas e as chaves que as ligam](diagramas/00_visao_geral.svg)

As áreas se ligam por poucas chaves:
- `variante_id` liga o catálogo às vendas e aos eventos;
- `sessao_id` e `pedido_id` ligam vendas e tracking;
- os IDs de anúncio, grupo, palavra-chave e campanha ligam as plataformas ao tracking e à atribuição.

A camada de MMM não tem FK para o resto: ela se liga pela UF e pela data, e seus totais reconciliam com os relatórios de
cada plataforma.

## 1. Catálogo e estoque

![Catálogo e estoque](diagramas/01_catalogo_estoque.svg)

- **Produto e variante:** `produtos` é o tecido; `variantes` é o SKU vendido (cor, estampa, formato de venda).
- **Categorias:** têm hierarquia (`categoria_pai_id`, o laço em `categorias`).
- **Preço:** `historico_precos` guarda preço e custo com vigência (SCD tipo 2); `variantes.preco_atual` é só a foto atual.
- **Estoque:**
  - `estoque` é o saldo atual (1:1 com a variante);
  - `estoque_diario` é o fechamento de cada dia, com `em_ruptura` e a `demanda_perdida` que as vendas não mostram;
  - `movimentacoes_estoque` é o livro de entradas e saídas, ligado ao pedido, à devolução ou à compra do fornecedor.

## 2. Clientes, pedidos e pós-venda

![Clientes, pedidos e pós-venda](diagramas/02_clientes_pedidos.svg)

- **Pedido:**
  - o cliente é obrigatório;
  - endereço, sessão e cupom podem faltar (pedido pelo WhatsApp, sem rastreio ou sem cupom).
- **Pagamento:** `pagamentos` guarda cada tentativa (cartão recusado e depois aprovado = duas linhas).
- **Frete:** `fretes` é 1:1 com o pedido.
- **Devolução:** aponta para o pedido e para o item devolvido.
- **Avaliação:** liga cliente, pedido e produto.

## 3. Tracking do site e atribuição

![Tracking do site e atribuição](diagramas/03_tracking_atribuicao.svg)

A cadeia é **clique → sessão → eventos → pedido**:
- **Clique:** `cliques_midia` é o clique registrado pela plataforma (fbclid ou gclid) e gera no máximo uma sessão.
- **Sessão e eventos:** `eventos` é o log GA4 enviado pelo GTM server-side. Um purchase chega duas vezes (navegador e
  servidor) com o mesmo `event_id`.
- **Envios à Meta e ao Google:** `envios_conversao` registra cada envio à Meta CAPI e às Enhanced Conversions do Google.
- **Atribuição:** `atribuicoes` distribui o crédito de cada pedido entre os toques (sessões) e as campanhas, em vários
  modelos.

As imperfeições desta área (duplicatas, fuso trocado, sessões sem UTM, token da CAPI expirado) estão em
[`imperfeicoes.md`](imperfeicoes.md).

## 4. Meta Ads

![Meta Ads](diagramas/04_meta_ads.svg)

- **Hierarquia:** a mesma da API de Marketing (conta → campanha → conjunto → anúncio).
- **Insights diários:** `meta_metricas_diarias` traz um registro por anúncio por dia, com alcance (só a Meta reporta) e
  compras pela janela da plataforma (7 dias após o clique, 1 dia após a visualização).
- **IDs:** os IDs têm 18 dígitos; leia como texto ou `Int64`.

## 5. Google Ads

![Google Ads](diagramas/05_google_ads.svg)

- **Hierarquia:** conta → campanha (Search, Shopping, PMax, Demand Gen) → grupo de anúncio (ou asset group, no PMax) →
  palavra-chave.
- **Métricas:** `google_metricas_diarias` traz um registro por grupo e dia, com a parcela de impressões em Search.
- **Palavras-chave:** `google_palavras_chave_metricas_diarias` detalha só as campanhas de Search, e sua soma bate com a do
  grupo.

## 6. MMM regional, testes geográficos e outros canais

![MMM regional, testes geográficos e outros canais](diagramas/06_mmm_outros_canais.svg)

Tabelas criadas para o projeto [marketing-mix-modeling](https://github.com/arielabade/marketing-mix-modeling).

- **Mídia por UF:** `midia_regional_diaria` é o relatório geográfico de todas as plataformas no mesmo grão
  (dia × canal × UF). A soma por dia e plataforma bate com `meta_metricas_diarias`, `google_metricas_diarias`,
  `tiktok_metricas_diarias`, `afiliados_metricas_diarias` e `crm_disparos`.
- **Ligação com as vendas:** a UF liga a mídia às vendas pelo endereço de entrega dos pedidos, e o `calendario_comercial`
  pela data. São ligações lógicas, sem FK física.
- **Testes geográficos:** `testes_geo` e `testes_geo_regioes` registram os testes geo-lift e o grupo (tratamento ou
  controle) de cada UF.
