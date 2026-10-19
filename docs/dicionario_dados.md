# Dicionário de dados

Banco `tecidos` (MySQL 8.4). Gerado por `scripts/gerar_dicionario.py` a partir do banco carregado: tipos, chaves e % de nulos são lidos do MySQL. Imperfeições propositais estão marcadas e explicadas em [imperfeicoes.md](imperfeicoes.md).

**Fusos:** transacional em horário local (America/Sao_Paulo); tracking em UTC; métricas de mídia no fuso da conta.

## Índice

- **Catálogo:** [categorias](#categorias), [fornecedores](#fornecedores), [produtos](#produtos), [variantes](#variantes), [historico_precos](#historico_precos)
- **Estoque:** [estoque](#estoque), [estoque_diario](#estoque_diario), [movimentacoes_estoque](#movimentacoes_estoque)
- **Clientes:** [clientes](#clientes), [enderecos](#enderecos)
- **Pedidos:** [cupons](#cupons), [pedidos](#pedidos), [itens_pedido](#itens_pedido), [pagamentos](#pagamentos), [fretes](#fretes), [devolucoes](#devolucoes), [avaliacoes](#avaliacoes)
- **Mídia - Meta:** [meta_contas](#meta_contas), [meta_campanhas](#meta_campanhas), [meta_conjuntos](#meta_conjuntos), [meta_anuncios](#meta_anuncios), [meta_metricas_diarias](#meta_metricas_diarias)
- **Mídia - Google:** [google_contas](#google_contas), [google_campanhas](#google_campanhas), [google_grupos_anuncio](#google_grupos_anuncio), [google_palavras_chave](#google_palavras_chave), [google_metricas_diarias](#google_metricas_diarias), [google_palavras_chave_metricas_diarias](#google_palavras_chave_metricas_diarias)
- **Tracking:** [cliques_midia](#cliques_midia), [sessoes](#sessoes), [eventos](#eventos), [envios_conversao](#envios_conversao)
- **Atribuição:** [atribuicoes](#atribuicoes)

## categorias

Árvore de 2 níveis: família de fibra (Algodão, Linho, Viscose, Malha, Sintéticos, Jeans) e subcategoria.

*Domínio:* Catálogo · *Grão:* 1 linha por categoria · *Linhas:* 29

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `categoria_id` | smallint unsigned | PK | — | Identificador. Famílias usam 1-6; subcategorias 100+. |
| `categoria_pai_id` | smallint unsigned | FK → categorias.categoria_id | 20,7% | Família à qual a subcategoria pertence. Nulo nas famílias. |
| `nome` | varchar(60) |  | — | Nome exibido na loja. |
| `slug` | varchar(80) | UK | — | Trecho de URL da categoria (/categoria/<slug>). |

## fornecedores

Tecelagens e distribuidoras (fictícias).

*Domínio:* Catálogo · *Grão:* 1 linha por fornecedor · *Linhas:* 14

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `fornecedor_id` | smallint unsigned | PK | — | Identificador. |
| `razao_social` | varchar(120) |  | — | Razão social fictícia. |
| `nome_fantasia` | varchar(80) |  | — | Nome comercial. |
| `cnpj` | char(18) | UK | — | CNPJ sintético (dígitos verificadores válidos, gerado pelo Faker). |
| `uf` | char(2) |  | — | UF da sede. |
| `cidade` | varchar(80) |  | — | Cidade da sede. |
| `prazo_reposicao_dias` | tinyint unsigned |  | — | Prazo médio de entrega de reposição. |
| `confiabilidade` | decimal(3,2) |  | — | Probabilidade de entregar no prazo. Fornecedores com valor baixo causam rupturas (ex.: chita no São João). |
| `ativo` | tinyint(1) |  | — | 1 = fornecedor ativo. |

## produtos

Artigo (ex.: 'Linho Misto Liso Coleção Natural'). Cor, estampa e formato ficam nas variantes.

*Domínio:* Catálogo · *Grão:* 1 linha por artigo de tecido · *Linhas:* 225

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `produto_id` | int unsigned | PK | — | Identificador. |
| `sku_base` | varchar(20) | UK | — | Prefixo de SKU do artigo. |
| `nome` | varchar(120) |  | — | Nome do artigo. |
| `categoria_id` | smallint unsigned | FK → categorias.categoria_id | — | Subcategoria (FK categorias). |
| `fornecedor_id` | smallint unsigned | FK → fornecedores.fornecedor_id | — | Fornecedor principal. |
| `composicao` | varchar(80) |  | — | Composição da fibra (ex.: 55% linho 45% viscose). |
| `largura_cm` | smallint unsigned |  | — | Largura útil do tecido em cm. |
| `descricao` | varchar(400) |  | 16,4% | Texto da vitrine. Nulo em ~12% (imperfeição: cadastro incompleto). |
| `lancado_em` | date |  | — | Data de lançamento na loja. |
| `ativo` | tinyint(1) |  | — | 0 = descontinuado durante o período. |

## variantes

SKU vendável: cor x estampa x formato. Venda por metro (múltiplos de 0,5 m) ou por rolo (25 m malha, 50 m planos).

*Domínio:* Catálogo · *Grão:* 1 linha por SKU · *Linhas:* 2.079

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `variante_id` | int unsigned | PK | — | Identificador. |
| `produto_id` | int unsigned | FK → produtos.produto_id | — | Artigo. |
| `sku` | varchar(32) | UK | — | Código do SKU; sufixo -R indica rolo. |
| `cor` | varchar(40) |  | — | Cor predominante. 'Colorido' em estampas multicoloridas. |
| `estampa` | varchar(40) |  | — | 'Liso' quando não há estampa. |
| `gramatura_gm2` | smallint unsigned |  | 4,6% | Gramatura em g/m². Nula em ~4% (imperfeição). |
| `formato_venda` | enum('metro','rolo') |  | — | metro ou rolo. |
| `metros_por_unidade` | decimal(6,2) |  | — | 1 para venda por metro; tamanho do rolo em metros. |
| `preco_atual` | decimal(12,2) |  | — | Preço de tabela vigente no fim do período (por unidade de venda). |
| `custo_atual` | decimal(12,2) |  | — | Custo vigente no fim do período. |
| `ativo` | tinyint(1) |  | — | 0 = fora de linha. |
| `criado_em` | date |  | — | Data de criação do SKU. |

## historico_precos

Mudanças de preço de tabela, promoção e custo ao longo do tempo.

*Domínio:* Catálogo · *Grão:* 1 linha por período de preço de um SKU (SCD tipo 2) · *Linhas:* 37.490

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `historico_preco_id` | int unsigned | PK | — | Identificador. |
| `variante_id` | int unsigned | FK → variantes.variante_id | — | SKU. |
| `preco` | decimal(12,2) |  | — | Preço de tabela no período. |
| `preco_promocional` | decimal(12,2) |  | 71,3% | Preço promocional (nulo = sem promoção). |
| `custo` | decimal(12,2) |  | — | Custo de compra no período. |
| `vigente_de` | date |  | — | Início da vigência. |
| `vigente_ate` | date |  | 5,5% | Fim da vigência (nulo = vigente hoje). |
| `motivo` | enum('lancamento','reajuste_fornecedor','promocao','fim_promocao','queima_estoque') |  | — | lancamento, reajuste_fornecedor, promocao, fim_promocao ou queima_estoque. |

## estoque

Posição de estoque no fim do período.

*Domínio:* Estoque · *Grão:* 1 linha por SKU · *Linhas:* 2.079

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `variante_id` | int unsigned | PK · FK → variantes.variante_id | — | SKU. |
| `saldo_unidades` | decimal(10,2) |  | — | Saldo em metros (formato metro) ou rolos (formato rolo). |
| `ponto_reposicao` | decimal(10,2) |  | — | Saldo que dispara pedido ao fornecedor. |
| `lote_reposicao` | decimal(10,2) |  | — | Quantidade típica do pedido de compra. |
| `atualizado_em` | datetime |  | — | Momento do snapshot. |

## estoque_diario

Fechamento diário de estoque. Base para estudar ruptura e demanda censurada.

*Domínio:* Estoque · *Grão:* 1 linha por SKU e dia em que o SKU existia · *Linhas:* 2.276.067

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `variante_id` | int unsigned | PK · FK → variantes.variante_id | — | SKU. |
| `data` | date | PK | — | Dia (horário local). |
| `saldo_inicial` | decimal(10,2) |  | — | Saldo na abertura do dia (após chegadas de reposição). |
| `entradas` | decimal(10,2) |  | — | Entradas de compra no dia. |
| `saidas` | decimal(10,2) |  | — | Vendas pagas no dia. |
| `saldo_final` | decimal(10,2) |  | — | saldo_inicial + entradas - saidas. |
| `em_ruptura` | tinyint(1) |  | — | 1 = o SKU zerou em algum momento do dia ou recusou venda por falta de saldo. |
| `demanda_perdida` | decimal(10,2) |  | — | Unidades que clientes tentaram comprar sem estoque (não viraram venda). |

## movimentacoes_estoque

Kardex: compras, vendas, devoluções, ajustes de inventário e avarias.

*Domínio:* Estoque · *Grão:* 1 linha por movimento · *Linhas:* 267.389

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `movimentacao_id` | bigint unsigned | PK | — | Identificador (ordem cronológica). |
| `variante_id` | int unsigned | FK → variantes.variante_id | — | SKU. |
| `tipo` | enum('entrada_compra','saida_venda','entrada_devolucao','ajuste_inventario','perda_avaria') |  | — | entrada_compra, saida_venda, entrada_devolucao, ajuste_inventario ou perda_avaria. |
| `quantidade` | decimal(10,2) |  | — | Positiva = entrada; negativa = saída. Unidade de venda do SKU. |
| `ocorrido_em` | datetime |  | — | Momento (horário local). |
| `pedido_id` | int unsigned | FK → pedidos.pedido_id | 5,6% | Pedido relacionado (vendas e devoluções). |
| `devolucao_id` | int unsigned | FK → devolucoes.devolucao_id | 99,2% | Devolução relacionada. |
| `fornecedor_id` | smallint unsigned | FK → fornecedores.fornecedor_id | 95,0% | Fornecedor (entradas de compra). |

## clientes

Dados pessoais 100% sintéticos. E-mails só em domínios reservados (example.com, *.example, *.test).

*Domínio:* Clientes · *Grão:* 1 linha por conta de cliente · *Linhas:* 50.140

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `cliente_id` | int unsigned | PK | — | Identificador. |
| `tipo_cliente` | enum('hobby','costureira','atelie','confeccao') | índice | — | hobby, costureira, atelie ou confeccao (autodeclarado). |
| `tipo_pessoa` | enum('PF','PJ') |  | — | PF ou PJ. |
| `nome` | varchar(120) |  | — | Nome fictício. |
| `razao_social` | varchar(160) |  | 89,5% | Razão social (PJ). |
| `email` | varchar(160) | UK | — | E-mail fictício. ~1,5% com maiúsculas ou espaço à esquerda (imperfeição). |
| `telefone` | varchar(25) |  | 16,7% | Celular fictício com DDD da UF. Formatos inconsistentes e ~17% nulo (imperfeição). |
| `cpf` | char(14) |  | 17,4% | CPF sintético. Repetido em ~0,6% das contas: mesma pessoa com dois cadastros (imperfeição). |
| `cnpj` | char(18) |  | 89,5% | CNPJ sintético (PJ). |
| `data_nascimento` | date |  | 45,0% | Nula em ~45%. |
| `genero` | enum('F','M','O') |  | 59,9% | F, M ou O. Nulo em ~60%. |
| `cadastrado_em` | datetime | índice | — | Data de cadastro (horário local). |
| `origem_cadastro` | enum('checkout','newsletter','whatsapp','importacao_legado') |  | — | checkout, newsletter, whatsapp ou importacao_legado (base trazida da plataforma anterior; a 1ª compra no período não é a 1ª de verdade). |
| `aceita_email_marketing` | tinyint(1) |  | — | Opt-in de e-mail (LGPD). |
| `aceita_whatsapp` | tinyint(1) |  | — | Opt-in de WhatsApp. |

## enderecos

Endereços de entrega e cobrança.

*Domínio:* Clientes · *Grão:* 1 linha por endereço · *Linhas:* 54.598

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `endereco_id` | int unsigned | PK | — | Identificador. |
| `cliente_id` | int unsigned | FK → clientes.cliente_id | — | Cliente. |
| `tipo` | enum('entrega','cobranca') |  | — | entrega ou cobranca. |
| `destinatario` | varchar(120) |  | — | Nome do destinatário. |
| `cep` | varchar(9) |  | — | CEP coerente com a UF; ~12% sem hífen (imperfeição). |
| `logradouro` | varchar(160) |  | — | Rua fictícia. |
| `numero` | varchar(10) |  | — | Número. |
| `complemento` | varchar(60) |  | 55,1% | Nulo em ~55%. |
| `bairro` | varchar(80) |  | — | Bairro fictício. |
| `cidade` | varchar(80) |  | — | Cidade real da UF; ~6% sem acento ou em maiúsculas (imperfeição). |
| `uf` | char(2) | índice | — | UF. |
| `principal` | tinyint(1) |  | — | 1 = endereço principal. |
| `criado_em` | datetime |  | — | Data de criação. |

## cupons

Cupons de desconto (sazonais, primeira compra, criadoras de conteúdo fictícias, e-mail, WhatsApp, atacado).

*Domínio:* Pedidos · *Grão:* 1 linha por cupom · *Linhas:* 15

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `cupom_id` | smallint unsigned | PK | — | Identificador. |
| `codigo` | varchar(30) | UK | — | Código digitado no checkout. |
| `descricao` | varchar(120) |  | — | Descrição interna. |
| `tipo_desconto` | enum('percentual','valor_fixo','frete_gratis') |  | — | percentual, valor_fixo ou frete_gratis. |
| `valor_desconto` | decimal(10,2) |  | — | % ou R$, conforme o tipo. |
| `pedido_minimo` | decimal(10,2) |  | 33,3% | Subtotal mínimo. |
| `canal` | enum('geral','primeira_compra','influenciador','email','whatsapp','sazonal','recuperacao_carrinho') |  | — | Origem do cupom. |
| `valido_de` | date |  | — | Início da validade. |
| `valido_ate` | date |  | 73,3% | Fim da validade (nulo = sem fim). |
| `limite_usos` | int unsigned |  | 93,3% | Limite de usos (nulo = ilimitado). |

## pedidos

Pedidos da loja. Valores em R$. Horário local (America/Sao_Paulo).

*Domínio:* Pedidos · *Grão:* 1 linha por pedido · *Linhas:* 143.633

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `pedido_id` | int unsigned | PK | — | Identificador. |
| `numero_pedido` | varchar(12) | UK | — | Número exibido ao cliente; vira transaction_id no tracking. |
| `cliente_id` | int unsigned | FK → clientes.cliente_id | — | Cliente. |
| `endereco_entrega_id` | int unsigned | FK → enderecos.endereco_id | 2,7% | Endereço de entrega. Nulo = retirada na loja. |
| `sessao_id` | bigint unsigned | FK → sessoes.sessao_id | 17,5% | Sessão em que a compra aconteceu. Nulo = sem rastreio (adblock, navegador sem JS, pedido via WhatsApp). |
| `cupom_id` | smallint unsigned | FK → cupons.cupom_id | 82,6% | Cupom aplicado. |
| `canal_venda` | enum('site','whatsapp') |  | — | site ou whatsapp (pedido montado pelo atendimento). |
| `status` | enum('aguardando_pagamento','pago','enviado','entregue','cancelado','devolvido') | índice | — | aguardando_pagamento, pago, enviado, entregue, cancelado ou devolvido. Receita = pago, enviado, entregue e devolvido. |
| `criado_em` | datetime | índice | — | Criação do pedido (local). |
| `pago_em` | datetime |  | 6,7% | Aprovação do pagamento. |
| `cancelado_em` | datetime |  | 93,1% | Cancelamento (pagamento recusado/expirado, estorno). |
| `subtotal` | decimal(12,2) |  | — | Soma dos itens. |
| `desconto` | decimal(12,2) |  | — | Desconto de cupom. |
| `frete` | decimal(12,2) |  | — | Frete cobrado do cliente (0 = grátis). |
| `total` | decimal(12,2) |  | — | subtotal - desconto + frete (garantido por CHECK). |
| `pedido_teste` | tinyint(1) |  | — | 1 = pedido de teste da equipe (excluir das análises; alguns aparecem como pagos). |

## itens_pedido

Itens comprados.

*Domínio:* Pedidos · *Grão:* 1 linha por SKU no pedido · *Linhas:* 268.214

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `item_pedido_id` | int unsigned | PK | — | Identificador. |
| `pedido_id` | int unsigned | FK → pedidos.pedido_id | — | Pedido. |
| `variante_id` | int unsigned | FK → variantes.variante_id | — | SKU. |
| `quantidade` | decimal(10,2) |  | — | Metros (formato metro) ou rolos. |
| `preco_unitario` | decimal(12,2) |  | — | Preço praticado (com promoção de vitrine). |
| `preco_tabela` | decimal(12,2) |  | — | Preço de tabela no dia. |
| `custo_unitario` | decimal(12,2) |  | — | Custo no dia. |
| `total_item` | decimal(12,2) |  | — | quantidade x preco_unitario. |

## pagamentos

Tentativas de pagamento: cartão recusado seguido de nova tentativa gera 2 linhas.

*Domínio:* Pedidos · *Grão:* 1 linha por tentativa de pagamento · *Linhas:* 147.389

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `pagamento_id` | int unsigned | PK | — | Identificador. |
| `pedido_id` | int unsigned | FK → pedidos.pedido_id | — | Pedido. |
| `tentativa` | tinyint unsigned |  | — | Ordem da tentativa. |
| `metodo` | enum('pix','cartao_credito','boleto') |  | — | pix, cartao_credito ou boleto. |
| `bandeira` | varchar(20) |  | 45,9% | Bandeira do cartão (nula em ~6% dos cartões). |
| `parcelas` | tinyint unsigned |  | — | 1 a 12 (só cartão parcela). |
| `valor` | decimal(12,2) |  | — | Valor cobrado. |
| `status` | enum('aprovado','recusado','pendente','expirado','estornado') |  | — | aprovado, recusado, pendente, expirado ou estornado. |
| `gateway` | varchar(30) |  | — | Gateway de pagamento. |
| `transacao_gateway` | varchar(40) | UK | — | ID da transação no gateway. |
| `criado_em` | datetime |  | — | Criação (local). |
| `atualizado_em` | datetime |  | 0,0% | Última atualização de status. |

## fretes

Envio do pedido.

*Domínio:* Pedidos · *Grão:* 1 linha por pedido · *Linhas:* 143.633

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `frete_id` | int unsigned | PK | — | Identificador. |
| `pedido_id` | int unsigned | UK · FK → pedidos.pedido_id | — | Pedido. |
| `transportadora` | varchar(30) |  | — | Correios, Jadlog, Loggi ou Retirada na loja. |
| `servico` | varchar(30) |  | — | PAC, SEDEX, Jadlog .Package, Loggi Expresso ou Retirada. |
| `peso_kg` | decimal(8,3) |  | — | Peso estimado (metros x gramatura x largura). |
| `valor_cobrado` | decimal(10,2) |  | — | Frete cobrado do cliente. |
| `custo_real` | decimal(10,2) |  | — | Custo pago à transportadora. |
| `frete_gratis` | tinyint(1) |  | — | 1 = frete grátis (política por região e valor; limite subiu em mar/2025). |
| `prazo_estimado_dias` | tinyint unsigned |  | — | Prazo prometido. |
| `postado_em` | datetime |  | 9,6% | Postagem. |
| `entregue_em` | datetime |  | 9,8% | Entrega. Nulo em ~2% de pedidos entregues (imperfeição: rastreio sem baixa). |
| `codigo_rastreio` | varchar(20) |  | 9,6% | Código de rastreio fictício. |

## devolucoes

Trocas e devoluções.

*Domínio:* Pedidos · *Grão:* 1 linha por item devolvido · *Linhas:* 3.321

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `devolucao_id` | int unsigned | PK | — | Identificador. |
| `pedido_id` | int unsigned | FK → pedidos.pedido_id | — | Pedido. |
| `item_pedido_id` | int unsigned | FK → itens_pedido.item_pedido_id | — | Item devolvido. |
| `motivo` | enum('cor_diferente_da_foto','defeito_no_tecido','metragem_incorreta','gramatura_diferente','desistencia','atraso_na_entrega') |  | — | Motivo informado. |
| `quantidade` | decimal(10,2) |  | — | Quantidade devolvida. |
| `valor_reembolsado` | decimal(12,2) |  | — | Reembolso (0 se recusada). |
| `status` | enum('solicitada','aprovada','recusada','concluida') |  | — | solicitada, aprovada, recusada ou concluida. |
| `solicitada_em` | datetime |  | — | Solicitação. |
| `concluida_em` | datetime |  | 8,5% | Conclusão. |

## avaliacoes

Avaliações de produto após a entrega.

*Domínio:* Pedidos · *Grão:* 1 linha por pedido avaliado · *Linhas:* 22.285

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `avaliacao_id` | int unsigned | PK | — | Identificador. |
| `pedido_id` | int unsigned | FK → pedidos.pedido_id | — | Pedido. |
| `cliente_id` | int unsigned | FK → clientes.cliente_id | — | Cliente. |
| `produto_id` | int unsigned | FK → produtos.produto_id | — | Produto avaliado. |
| `nota` | tinyint unsigned |  | — | 1 a 5 (cai com atraso e devolução). |
| `titulo` | varchar(80) |  | 26,9% | Título (pode ser nulo). |
| `comentario` | varchar(400) |  | 34,4% | Comentário (pode ser nulo). |
| `criada_em` | datetime |  | — | Data da avaliação. |

## meta_contas

Contas de anúncio.

*Domínio:* Mídia - Meta · *Grão:* 1 linha por conta · *Linhas:* 1

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `conta_id` | varchar(24) | PK | — | ID da conta (act_...). |
| `nome` | varchar(80) |  | — | Nome. |
| `moeda` | char(3) |  | — | BRL. |
| `fuso_horario` | varchar(40) |  | — | Fuso das métricas diárias. |

## meta_campanhas

Campanhas: prospecção, Advantage+, remarketing, catálogo, sazonais e testes.

*Domínio:* Mídia - Meta · *Grão:* 1 linha por campanha · *Linhas:* 18

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `campanha_id` | bigint unsigned | PK | — | ID da campanha (18 dígitos; use BIGINT, não float). |
| `conta_id` | varchar(24) | FK → meta_contas.conta_id | — | Conta. |
| `nome` | varchar(120) |  | — | Nome com prefixo [PROSP], [RMKT], [SAZ] ou [TESTE]. |
| `objetivo` | enum('OUTCOME_SALES','OUTCOME_TRAFFIC','OUTCOME_AWARENESS','OUTCOME_ENGAGEMENT') |  | — | Objetivo ODAX. |
| `estrategia` | enum('prospeccao','remarketing','advantage_plus','catalogo','sazonal','teste') |  | — | Classificação interna da campanha. |
| `status` | enum('ACTIVE','PAUSED','ARCHIVED') |  | — | ACTIVE, PAUSED ou ARCHIVED. |
| `orcamento_diario` | decimal(12,2) |  | 27,8% | Orçamento de campanha (CBO); nulo quando o orçamento fica no conjunto. |
| `inicio` | date |  | — | Início. |
| `fim` | date |  | 27,8% | Fim (nulo = ativa). |

## meta_conjuntos

Públicos e otimização.

*Domínio:* Mídia - Meta · *Grão:* 1 linha por conjunto de anúncios · *Linhas:* 29

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `conjunto_id` | bigint unsigned | PK | — | ID. |
| `campanha_id` | bigint unsigned | FK → meta_campanhas.campanha_id | — | Campanha. |
| `nome` | varchar(140) |  | — | Nome. |
| `publico` | varchar(200) |  | — | Descrição do público. |
| `otimizacao` | enum('OFFSITE_CONVERSIONS','VALUE','LINK_CLICKS','LANDING_PAGE_VIEWS','REACH') |  | — | Evento de otimização. |
| `posicionamentos` | varchar(120) |  | — | Posicionamentos. |
| `status` | enum('ACTIVE','PAUSED','ARCHIVED') |  | — | Status. |

## meta_anuncios

Criativos. Anúncios entram e saem ao longo do tempo (renovação criativa e fadiga).

*Domínio:* Mídia - Meta · *Grão:* 1 linha por anúncio · *Linhas:* 117

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `anuncio_id` | bigint unsigned | PK | — | ID. |
| `conjunto_id` | bigint unsigned | FK → meta_conjuntos.conjunto_id | — | Conjunto. |
| `nome` | varchar(140) |  | — | Nome. |
| `formato` | enum('imagem','video','carrossel','catalogo','reels') |  | — | imagem, video, carrossel, catalogo ou reels. |
| `tema_criativo` | varchar(80) |  | — | Tema do criativo. |
| `url_destino` | varchar(300) |  | — | URL com template de UTMs. |
| `status` | enum('ACTIVE','PAUSED','ARCHIVED') |  | — | Status. |

## meta_metricas_diarias

Insights diários como na API de Marketing.

*Domínio:* Mídia - Meta · *Grão:* 1 linha por anúncio e dia com entrega · *Linhas:* 17.603

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `data` | date | PK | — | Dia no fuso da conta. |
| `anuncio_id` | bigint unsigned | PK · FK → meta_anuncios.anuncio_id | — | Anúncio. |
| `investimento` | decimal(12,2) |  | — | Valor gasto (R$). |
| `impressoes` | int unsigned |  | — | Impressões. |
| `alcance` | int unsigned |  | — | Pessoas alcançadas no dia. |
| `cliques_todos` | int unsigned |  | — | Todos os cliques. |
| `cliques_link` | int unsigned |  | — | Cliques no link. |
| `visualizacoes_pagina_destino` | int unsigned |  | — | Landing page views reportadas. |
| `adicoes_carrinho` | int unsigned |  | — | Add to cart reportados. |
| `compras` | int unsigned |  | — | Compras reportadas (7 dias após clique + 1 dia após visualização, inclui modeladas e pedidos depois cancelados). |
| `valor_compras` | decimal(12,2) |  | — | Valor das compras reportadas. |

## google_contas

Contas Google Ads.

*Domínio:* Mídia - Google · *Grão:* 1 linha por conta · *Linhas:* 1

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `conta_id` | varchar(12) | PK | — | Customer ID. |
| `nome` | varchar(80) |  | — | Nome. |
| `moeda` | char(3) |  | — | BRL. |
| `fuso_horario` | varchar(40) |  | — | Fuso. |

## google_campanhas

Search (marca, genérica, concorrentes), Shopping, Performance Max e Demand Gen.

*Domínio:* Mídia - Google · *Grão:* 1 linha por campanha · *Linhas:* 7

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `campanha_id` | bigint unsigned | PK | — | ID. |
| `conta_id` | varchar(12) | FK → google_contas.conta_id | — | Conta. |
| `nome` | varchar(120) |  | — | Nome. |
| `tipo_canal` | enum('SEARCH','SHOPPING','PERFORMANCE_MAX','DEMAND_GEN') |  | — | SEARCH, SHOPPING, PERFORMANCE_MAX ou DEMAND_GEN. |
| `estrategia_lance` | enum('MAXIMIZE_CONVERSIONS','MAXIMIZE_CONVERSION_VALUE','TARGET_ROAS','TARGET_CPA','MANUAL_CPC') |  | — | Estratégia de lance. |
| `roas_alvo` | decimal(6,2) |  | 57,1% | tROAS (quando aplicável). |
| `campanha_marca` | tinyint(1) |  | — | 1 = Search de marca. |
| `orcamento_diario` | decimal(12,2) |  | — | Orçamento diário de referência (escala 1). |
| `status` | enum('ENABLED','PAUSED','REMOVED') |  | — | ENABLED, PAUSED ou REMOVED. |
| `inicio` | date |  | — | Início. |
| `fim` | date |  | 42,9% | Fim (nulo = ativa). |

## google_grupos_anuncio

Grupos de anúncios; em PMax representam asset groups.

*Domínio:* Mídia - Google · *Grão:* 1 linha por grupo (ou asset group) · *Linhas:* 18

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `grupo_id` | bigint unsigned | PK | — | ID. |
| `campanha_id` | bigint unsigned | FK → google_campanhas.campanha_id | — | Campanha. |
| `nome` | varchar(140) |  | — | Nome. |
| `tipo` | enum('SEARCH_STANDARD','SHOPPING_PRODUCT_ADS','ASSET_GROUP','DEMAND_GEN') |  | — | Tipo de grupo. |
| `status` | enum('ENABLED','PAUSED','REMOVED') |  | — | Status. |

## google_palavras_chave

Palavras-chave das campanhas Search.

*Domínio:* Mídia - Google · *Grão:* 1 linha por palavra-chave · *Linhas:* 33

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `palavra_chave_id` | bigint unsigned | PK | — | ID. |
| `grupo_id` | bigint unsigned | FK → google_grupos_anuncio.grupo_id | — | Grupo. |
| `texto` | varchar(120) |  | — | Palavra-chave. |
| `tipo_correspondencia` | enum('EXACT','PHRASE','BROAD') |  | — | EXACT, PHRASE ou BROAD. |
| `indice_qualidade` | tinyint unsigned |  | 21,2% | 1-10; nulo quando sem dados suficientes. |
| `status` | enum('ENABLED','PAUSED','REMOVED') |  | — | Status. |

## google_metricas_diarias

Métricas diárias por grupo.

*Domínio:* Mídia - Google · *Grão:* 1 linha por grupo e dia com entrega · *Linhas:* 12.815

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `data` | date | PK | — | Dia no fuso da conta. |
| `grupo_id` | bigint unsigned | PK · FK → google_grupos_anuncio.grupo_id | — | Grupo. |
| `investimento` | decimal(12,2) |  | — | Custo (R$). |
| `impressoes` | int unsigned |  | — | Impressões. |
| `cliques` | int unsigned |  | — | Cliques. |
| `conversoes` | decimal(10,2) |  | — | Conversões reportadas (fracionadas, modelo da plataforma, janela 30 dias, por data do clique; inclui engaged-view em PMax/Demand Gen). |
| `valor_conversao` | decimal(12,2) |  | — | Valor reportado. |
| `parcela_impressoes` | decimal(5,4) |  | 27,2% | Search impression share (só Search). |

## google_palavras_chave_metricas_diarias

Métricas diárias de palavras-chave (Search). A soma de investimento bate com o grupo.

*Domínio:* Mídia - Google · *Grão:* 1 linha por palavra-chave e dia · *Linhas:* 31.299

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `data` | date | PK | — | Dia. |
| `palavra_chave_id` | bigint unsigned | PK · FK → google_palavras_chave.palavra_chave_id | — | Palavra-chave. |
| `investimento` | decimal(12,2) |  | — | Custo. |
| `impressoes` | int unsigned |  | — | Impressões. |
| `cliques` | int unsigned |  | — | Cliques. |
| `conversoes` | decimal(10,2) |  | — | Conversões atribuídas a cliques da palavra (o grupo pode ter mais, vindas de PMax/engaged-view). |
| `valor_conversao` | decimal(12,2) |  | — | Valor. |

## cliques_midia

Elo entre a plataforma de mídia e a sessão. Plataformas reportam mais cliques do que chegam aqui (perda entre clique e carregamento).

*Domínio:* Tracking · *Grão:* 1 linha por click id capturado na entrada do site · *Linhas:* 2.381.715

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `clique_id` | bigint unsigned | PK | — | Identificador. |
| `plataforma` | enum('meta','google') |  | — | meta ou google. |
| `click_id` | varchar(120) | UK | — | fbclid ou gclid. |
| `meta_anuncio_id` | bigint unsigned | FK → meta_anuncios.anuncio_id | 66,6% | Anúncio Meta. |
| `google_grupo_id` | bigint unsigned | FK → google_grupos_anuncio.grupo_id | 33,4% | Grupo Google. |
| `google_palavra_chave_id` | bigint unsigned | FK → google_palavras_chave.palavra_chave_id | 71,0% | Palavra-chave (Search). |
| `clicado_em` | datetime(3) | índice | — | Momento do clique (UTC). |

## sessoes

Sessões reconstruídas pelo GTM server-side (padrão GA4). Horário em UTC.

*Domínio:* Tracking · *Grão:* 1 linha por sessão · *Linhas:* 5.232.413

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `sessao_id` | bigint unsigned | PK | — | Identificador. |
| `ga_session_id` | int unsigned |  | — | ID de sessão GA4 (timestamp unix do início). |
| `client_id` | varchar(40) | índice | 17,0% | Cookie _ga. Nulo quando analytics_storage foi negado (cookieless ping). |
| `cliente_id` | int unsigned | FK → clientes.cliente_id | 89,0% | user_id: cliente logado/identificado na sessão. |
| `iniciada_em` | datetime(3) | índice | — | Início (UTC). |
| `duracao_seg` | int unsigned |  | — | Duração. |
| `dispositivo` | enum('mobile','desktop','tablet') |  | 0,8% | mobile, desktop ou tablet (nulo em ~1%). |
| `sistema_operacional` | varchar(20) |  | 0,8% | SO. |
| `navegador` | varchar(30) |  | 1,2% | Navegador; inclui navegadores in-app (Instagram/Facebook). |
| `uf` | char(2) |  | 6,9% | UF por IP (nula em ~7%). |
| `landing_page` | varchar(200) |  | — | URL de entrada. |
| `referrer` | varchar(200) |  | 39,2% | Página de origem. |
| `utm_source` | varchar(60) |  | 56,3% | Origem. Grafias inconsistentes (ig, IG, Instagram, instagram). |
| `utm_medium` | varchar(40) |  | 56,8% | Meio (paid_social, paid, cpc, Social, email...). |
| `utm_campaign` | varchar(120) |  | 56,3% | Campanha: nome antes de jun/2024, ID da campanha depois (troca de template). |
| `utm_content` | varchar(120) |  | 84,7% | ID do anúncio (Meta). |
| `utm_term` | varchar(120) |  | 77,5% | ID do conjunto (Meta) ou palavra-chave (Google com UTM manual). |
| `gclid` | varchar(120) |  | 69,8% | Google click id (auto-tagging). |
| `fbclid` | varchar(120) |  | 84,7% | Meta click id. Ausente em ~12% das sessões vindas de anúncio Meta (imperfeição). |
| `fbp` | varchar(60) |  | 27,9% | Cookie _fbp (só com ad_storage concedido). |
| `fbc` | varchar(160) |  | 89,0% | Cookie _fbc derivado do fbclid. |
| `clique_id` | bigint unsigned | FK → cliques_midia.clique_id | 54,5% | Clique de mídia que originou a sessão. |
| `consent_analytics_storage` | enum('granted','denied') |  | — | Consent Mode v2. |
| `consent_ad_storage` | enum('granted','denied') |  | — | Consent Mode v2. |
| `consent_ad_user_data` | enum('granted','denied') |  | — | Consent Mode v2 (envio de dados do usuário para anúncios). |
| `consent_ad_personalization` | enum('granted','denied') |  | — | Consent Mode v2 (personalização). |
| `primeira_visita` | tinyint(1) |  | — | 1 = primeira visita do client_id. |
| `engajada` | tinyint(1) |  | — | Critério GA4: >10 s, 2+ page views ou conversão. |

## eventos

Log de eventos GA4 do GTM server-side: page_view, view_item, add_to_cart, begin_checkout, add_payment_info, purchase.

*Domínio:* Tracking · *Grão:* 1 linha por hit recebido pelo servidor (há duplicatas) · *Linhas:* 15.715.906

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `evento_id` | bigint unsigned | PK | — | Chave surrogate da linha. |
| `event_id` | char(36) | índice | — | ID de deduplicação. O purchase chega do navegador e do backend com o mesmo event_id; retries de rede repetem o event_id. |
| `sessao_id` | bigint unsigned | FK → sessoes.sessao_id | — | Sessão. |
| `cliente_id` | int unsigned | FK → clientes.cliente_id | 85,2% | user_id no momento do evento (em compras de cliente novo, só a partir do checkout). |
| `event_name` | enum('page_view','view_item','add_to_cart','begin_checkout','add_payment_info','purchase') | índice | — | Nome do evento GA4. |
| `event_timestamp` | datetime(3) |  | — | Momento em UTC, EXCETO versao_container = 'v2.3' (01/03 a 15/06/2024), gravado em horário local (UTC-3). Imperfeição documentada. |
| `page_location` | varchar(200) |  | — | URL da página. |
| `variante_id` | int unsigned | FK → variantes.variante_id | 64,5% | Item do evento (view_item, add_to_cart). |
| `quantidade` | decimal(10,2) |  | 64,5% | Quantidade do item. |
| `valor` | decimal(12,2) |  | 60,8% | value do evento (R$). |
| `moeda` | char(3) |  | 60,8% | currency. |
| `transaction_id` | varchar(12) |  | 98,8% | numero_pedido (purchase). Recargas da página de obrigado repetem o transaction_id com event_id novo. |
| `pedido_id` | int unsigned | FK → pedidos.pedido_id | 98,8% | Pedido (purchase). |
| `fonte` | enum('web','server') |  | — | web = tag no navegador; server = webhook do backend. |
| `versao_container` | varchar(8) |  | — | Versão do container sGTM (v2.1, v2.3, v2.4, v3.0, v3.1). |

## envios_conversao

Log dos envios server-side: Meta Conversions API (add_to_cart, begin_checkout, add_payment_info, purchase) e Google Ads Enhanced Conversions (purchase).

*Domínio:* Tracking · *Grão:* 1 linha por envio a uma plataforma · *Linhas:* 1.335.554

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `envio_id` | bigint unsigned | PK | — | Identificador. |
| `evento_id` | bigint unsigned | FK → eventos.evento_id | — | Evento enviado. |
| `plataforma` | enum('meta_capi','google_ads_ec') | índice | — | meta_capi ou google_ads_ec. |
| `status` | enum('enviado','erro','bloqueado_consentimento','deduplicado') |  | — | enviado, erro, bloqueado_consentimento ou deduplicado. |
| `http_status` | smallint unsigned |  | 28,3% | Resposta HTTP. 401 = token expirado (incidente de 14 a 17/07/2025). |
| `enviado_em` | datetime(3) |  | 28,3% | Envio (UTC). |
| `email_hash_enviado` | tinyint(1) |  | — | 1 = e-mail com SHA-256 enviado. |
| `telefone_hash_enviado` | tinyint(1) |  | — | 1 = telefone com hash enviado. |
| `fbp_enviado` | tinyint(1) |  | — | 1 = _fbp enviado. |
| `fbc_enviado` | tinyint(1) |  | — | 1 = _fbc enviado. |
| `gclid_enviado` | tinyint(1) |  | — | 1 = gclid enviado. |
| `event_match_quality` | decimal(3,1) |  | 38,6% | EMQ estimado da Meta (0-10). |
| `mensagem_erro` | varchar(120) |  | 98,5% | Mensagem de erro. |

## atribuicoes

Crédito de cada sessão (toque) na jornada de até 30 dias antes da compra. Só pedidos rastreados.

*Domínio:* Atribuição · *Grão:* 1 linha por pedido x modelo x toque · *Linhas:* 669.012

| Coluna | Tipo | Chave | Nulos | Descrição |
|---|---|---|---|---|
| `atribuicao_id` | int unsigned | PK | — | Identificador. |
| `pedido_id` | int unsigned | FK → pedidos.pedido_id | — | Pedido. |
| `modelo` | enum('last_click','first_click','linear','data_driven') | índice | — | last_click (último clique não direto), first_click, linear ou data_driven (simplificado: lift do canal x decaimento de 7 dias x bônus de primeiro/último toque). |
| `sessao_id` | bigint unsigned | FK → sessoes.sessao_id | — | Sessão (toque). |
| `posicao` | tinyint unsigned |  | — | Ordem do toque (1 = primeiro). |
| `total_toques` | tinyint unsigned |  | — | Toques na jornada. |
| `canal` | varchar(30) |  | — | Agrupamento de canais padrão pelo que é observável na sessão. |
| `meta_campanha_id` | bigint unsigned | FK → meta_campanhas.campanha_id | 84,9% | Campanha Meta do toque (quando o clique foi capturado). |
| `google_campanha_id` | bigint unsigned | FK → google_campanhas.campanha_id | 77,9% | Campanha Google do toque. |
| `peso` | decimal(7,6) |  | — | Crédito do toque (soma 1 por pedido e modelo). |
| `receita_atribuida` | decimal(12,2) |  | — | peso x total do pedido. |
