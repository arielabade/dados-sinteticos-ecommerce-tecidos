-- =====================================================================
-- Tecelã Tecidos (loja fictícia) - schema MySQL 8.4
-- E-commerce brasileiro de tecidos: transacional + tracking (GTM
-- server-side, padrão GA4) + mídia paga (Meta Ads, Google Ads, TikTok Ads,
-- afiliados e CRM) + atribuição + camada de MMM (mídia por UF, calendário
-- comercial e registro de testes geográficos).
--
-- Convenções
--   * Nomes em português, snake_case. IDs surrogate INT/BIGINT.
--   * Fuso horário: veja docs/imperfeicoes.md. Em resumo,
--       - tabelas transacionais (pedidos, pagamentos, ...) = horário local
--         America/Sao_Paulo, como a plataforma de loja grava;
--       - tracking (sessoes, eventos, cliques_midia) = UTC, salvo o
--         defeito documentado do container server-side v2.3;
--       - métricas diárias de mídia = fuso da conta (America/Sao_Paulo).
--   * Valores monetários em BRL, DECIMAL(12,2).
--   * Quantidades de tecido em metros, DECIMAL(10,2).
-- =====================================================================

CREATE DATABASE IF NOT EXISTS tecidos
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE tecidos;

SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------
-- 1. CATÁLOGO
-- ---------------------------------------------------------------------

CREATE TABLE categorias (
  categoria_id      SMALLINT UNSIGNED NOT NULL,
  categoria_pai_id  SMALLINT UNSIGNED NULL,
  nome              VARCHAR(60)  NOT NULL,
  slug              VARCHAR(80)  NOT NULL,
  PRIMARY KEY (categoria_id),
  UNIQUE KEY uq_categorias_slug (slug),
  KEY ix_categorias_pai (categoria_pai_id),
  CONSTRAINT fk_categorias_pai FOREIGN KEY (categoria_pai_id)
    REFERENCES categorias (categoria_id)
) ENGINE=InnoDB COMMENT='Árvore de categorias (2 níveis: família de fibra > subcategoria)';

CREATE TABLE fornecedores (
  fornecedor_id         SMALLINT UNSIGNED NOT NULL,
  razao_social          VARCHAR(120) NOT NULL,
  nome_fantasia         VARCHAR(80)  NOT NULL,
  cnpj                  CHAR(18)     NOT NULL,
  uf                    CHAR(2)      NOT NULL,
  cidade                VARCHAR(80)  NOT NULL,
  prazo_reposicao_dias  TINYINT UNSIGNED NOT NULL,
  confiabilidade        DECIMAL(3,2) NOT NULL COMMENT 'Prob. de entregar no prazo (0-1)',
  ativo                 TINYINT(1)   NOT NULL DEFAULT 1,
  PRIMARY KEY (fornecedor_id),
  UNIQUE KEY uq_fornecedores_cnpj (cnpj),
  CONSTRAINT ck_fornecedores_conf CHECK (confiabilidade BETWEEN 0 AND 1)
) ENGINE=InnoDB COMMENT='Tecelagens e distribuidoras';

CREATE TABLE produtos (
  produto_id     INT UNSIGNED NOT NULL,
  sku_base       VARCHAR(20)  NOT NULL,
  nome           VARCHAR(120) NOT NULL,
  categoria_id   SMALLINT UNSIGNED NOT NULL,
  fornecedor_id  SMALLINT UNSIGNED NOT NULL,
  composicao     VARCHAR(80)  NOT NULL COMMENT 'Ex.: 100% algodão, 55% linho 45% viscose',
  largura_cm     SMALLINT UNSIGNED NOT NULL,
  descricao      VARCHAR(400) NULL,
  lancado_em     DATE         NOT NULL,
  ativo          TINYINT(1)   NOT NULL DEFAULT 1,
  PRIMARY KEY (produto_id),
  UNIQUE KEY uq_produtos_sku (sku_base),
  KEY ix_produtos_categoria (categoria_id),
  KEY ix_produtos_fornecedor (fornecedor_id),
  CONSTRAINT fk_produtos_categoria  FOREIGN KEY (categoria_id)  REFERENCES categorias (categoria_id),
  CONSTRAINT fk_produtos_fornecedor FOREIGN KEY (fornecedor_id) REFERENCES fornecedores (fornecedor_id),
  CONSTRAINT ck_produtos_largura CHECK (largura_cm BETWEEN 50 AND 320)
) ENGINE=InnoDB COMMENT='Produto = tecido (artigo). As variantes trazem cor, estampa e formato';

CREATE TABLE variantes (
  variante_id         INT UNSIGNED NOT NULL,
  produto_id          INT UNSIGNED NOT NULL,
  sku                 VARCHAR(32)  NOT NULL,
  cor                 VARCHAR(40)  NOT NULL,
  estampa             VARCHAR(40)  NOT NULL COMMENT '"Liso" quando não há estampa',
  gramatura_gm2       SMALLINT UNSIGNED NULL COMMENT 'g/m². Nulo = não cadastrado (imperfeição)',
  formato_venda       ENUM('metro','rolo') NOT NULL,
  metros_por_unidade  DECIMAL(6,2) NOT NULL COMMENT '1 para venda por metro; tamanho do rolo para rolos',
  preco_atual         DECIMAL(12,2) NOT NULL COMMENT 'Preço de tabela vigente (por unidade de venda)',
  custo_atual         DECIMAL(12,2) NOT NULL,
  ativo               TINYINT(1)   NOT NULL DEFAULT 1,
  criado_em           DATE         NOT NULL,
  PRIMARY KEY (variante_id),
  UNIQUE KEY uq_variantes_sku (sku),
  KEY ix_variantes_produto (produto_id),
  CONSTRAINT fk_variantes_produto FOREIGN KEY (produto_id) REFERENCES produtos (produto_id),
  CONSTRAINT ck_variantes_preco CHECK (preco_atual > 0 AND custo_atual > 0),
  CONSTRAINT ck_variantes_metros CHECK (metros_por_unidade > 0)
) ENGINE=InnoDB COMMENT='SKU vendável: cor x estampa x formato (metro ou rolo)';

CREATE TABLE historico_precos (
  historico_preco_id  INT UNSIGNED NOT NULL,
  variante_id         INT UNSIGNED NOT NULL,
  preco               DECIMAL(12,2) NOT NULL COMMENT 'Preço de tabela',
  preco_promocional   DECIMAL(12,2) NULL,
  custo               DECIMAL(12,2) NOT NULL,
  vigente_de          DATE NOT NULL,
  vigente_ate         DATE NULL COMMENT 'Nulo = vigente hoje',
  motivo              ENUM('lancamento','reajuste_fornecedor','promocao','fim_promocao','queima_estoque') NOT NULL,
  PRIMARY KEY (historico_preco_id),
  KEY ix_hp_variante_data (variante_id, vigente_de),
  CONSTRAINT fk_hp_variante FOREIGN KEY (variante_id) REFERENCES variantes (variante_id),
  CONSTRAINT ck_hp_datas CHECK (vigente_ate IS NULL OR vigente_ate >= vigente_de)
) ENGINE=InnoDB COMMENT='SCD tipo 2 de preço e custo por variante';

-- ---------------------------------------------------------------------
-- 2. ESTOQUE
-- ---------------------------------------------------------------------

CREATE TABLE estoque (
  variante_id        INT UNSIGNED NOT NULL,
  saldo_unidades     DECIMAL(10,2) NOT NULL COMMENT 'Metros (formato metro) ou rolos (formato rolo)',
  ponto_reposicao    DECIMAL(10,2) NOT NULL,
  lote_reposicao     DECIMAL(10,2) NOT NULL,
  atualizado_em      DATETIME NOT NULL,
  PRIMARY KEY (variante_id),
  CONSTRAINT fk_estoque_variante FOREIGN KEY (variante_id) REFERENCES variantes (variante_id)
) ENGINE=InnoDB COMMENT='Posição atual (snapshot no fim do período)';

CREATE TABLE estoque_diario (
  variante_id     INT UNSIGNED NOT NULL,
  data            DATE NOT NULL,
  saldo_inicial   DECIMAL(10,2) NOT NULL,
  entradas        DECIMAL(10,2) NOT NULL,
  saidas          DECIMAL(10,2) NOT NULL,
  saldo_final     DECIMAL(10,2) NOT NULL,
  em_ruptura      TINYINT(1) NOT NULL COMMENT '1 = saldo zerado em algum momento do dia',
  demanda_perdida DECIMAL(10,2) NOT NULL COMMENT 'Unidades pedidas em carrinhos que não puderam ser atendidas',
  PRIMARY KEY (variante_id, data),
  KEY ix_ed_data (data),
  CONSTRAINT fk_ed_variante FOREIGN KEY (variante_id) REFERENCES variantes (variante_id)
) ENGINE=InnoDB COMMENT='Fechamento diário de estoque por SKU (base para demanda censurada)';

-- ---------------------------------------------------------------------
-- 3. CLIENTES
-- ---------------------------------------------------------------------

CREATE TABLE clientes (
  cliente_id              INT UNSIGNED NOT NULL,
  tipo_cliente            ENUM('hobby','costureira','atelie','confeccao') NOT NULL,
  tipo_pessoa             ENUM('PF','PJ') NOT NULL,
  nome                    VARCHAR(120) NOT NULL,
  razao_social            VARCHAR(160) NULL,
  email                   VARCHAR(160) NOT NULL,
  telefone                VARCHAR(25)  NULL COMMENT 'Formatos inconsistentes (imperfeição)',
  cpf                     CHAR(14)     NULL,
  cnpj                    CHAR(18)     NULL,
  data_nascimento         DATE         NULL,
  genero                  ENUM('F','M','O') NULL,
  cadastrado_em           DATETIME     NOT NULL COMMENT 'Horário local',
  origem_cadastro         ENUM('checkout','newsletter','whatsapp','importacao_legado') NOT NULL,
  aceita_email_marketing  TINYINT(1)   NOT NULL DEFAULT 0,
  aceita_whatsapp         TINYINT(1)   NOT NULL DEFAULT 0,
  PRIMARY KEY (cliente_id),
  UNIQUE KEY uq_clientes_email (email),
  KEY ix_clientes_tipo (tipo_cliente),
  KEY ix_clientes_cadastro (cadastrado_em),
  CONSTRAINT ck_clientes_doc CHECK (
    (tipo_pessoa = 'PF' AND cnpj IS NULL) OR (tipo_pessoa = 'PJ' AND cnpj IS NOT NULL))
) ENGINE=InnoDB COMMENT='Dados pessoais 100% sintéticos (Faker pt_BR, domínios example.*)';

CREATE TABLE enderecos (
  endereco_id    INT UNSIGNED NOT NULL,
  cliente_id     INT UNSIGNED NOT NULL,
  tipo           ENUM('entrega','cobranca') NOT NULL,
  destinatario   VARCHAR(120) NOT NULL,
  cep            VARCHAR(9)   NOT NULL COMMENT 'Com ou sem hífen (imperfeição)',
  logradouro     VARCHAR(160) NOT NULL,
  numero         VARCHAR(10)  NOT NULL,
  complemento    VARCHAR(60)  NULL,
  bairro         VARCHAR(80)  NOT NULL,
  cidade         VARCHAR(80)  NOT NULL,
  uf             CHAR(2)      NOT NULL,
  principal      TINYINT(1)   NOT NULL DEFAULT 0,
  criado_em      DATETIME     NOT NULL,
  PRIMARY KEY (endereco_id),
  KEY ix_enderecos_cliente (cliente_id),
  KEY ix_enderecos_uf (uf),
  CONSTRAINT fk_enderecos_cliente FOREIGN KEY (cliente_id) REFERENCES clientes (cliente_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. MÍDIA PAGA - META ADS
-- ---------------------------------------------------------------------

CREATE TABLE meta_contas (
  conta_id       VARCHAR(24) NOT NULL COMMENT 'act_<id>',
  nome           VARCHAR(80) NOT NULL,
  moeda          CHAR(3)     NOT NULL DEFAULT 'BRL',
  fuso_horario   VARCHAR(40) NOT NULL,
  PRIMARY KEY (conta_id)
) ENGINE=InnoDB;

CREATE TABLE meta_campanhas (
  campanha_id      BIGINT UNSIGNED NOT NULL,
  conta_id         VARCHAR(24) NOT NULL,
  nome             VARCHAR(120) NOT NULL,
  objetivo         ENUM('OUTCOME_SALES','OUTCOME_TRAFFIC','OUTCOME_AWARENESS','OUTCOME_ENGAGEMENT') NOT NULL,
  estrategia       ENUM('prospeccao','remarketing','advantage_plus','catalogo','sazonal','teste') NOT NULL,
  status           ENUM('ACTIVE','PAUSED','ARCHIVED') NOT NULL,
  orcamento_diario DECIMAL(12,2) NULL COMMENT 'Nulo = orçamento no conjunto (ABO)',
  inicio           DATE NOT NULL,
  fim              DATE NULL,
  PRIMARY KEY (campanha_id),
  KEY ix_mc_conta (conta_id),
  CONSTRAINT fk_mc_conta FOREIGN KEY (conta_id) REFERENCES meta_contas (conta_id)
) ENGINE=InnoDB;

CREATE TABLE meta_conjuntos (
  conjunto_id      BIGINT UNSIGNED NOT NULL,
  campanha_id      BIGINT UNSIGNED NOT NULL,
  nome             VARCHAR(140) NOT NULL,
  publico          VARCHAR(200) NOT NULL,
  otimizacao       ENUM('OFFSITE_CONVERSIONS','VALUE','LINK_CLICKS','LANDING_PAGE_VIEWS','REACH') NOT NULL,
  posicionamentos  VARCHAR(120) NOT NULL,
  status           ENUM('ACTIVE','PAUSED','ARCHIVED') NOT NULL,
  PRIMARY KEY (conjunto_id),
  KEY ix_mcj_campanha (campanha_id),
  CONSTRAINT fk_mcj_campanha FOREIGN KEY (campanha_id) REFERENCES meta_campanhas (campanha_id)
) ENGINE=InnoDB;

CREATE TABLE meta_anuncios (
  anuncio_id      BIGINT UNSIGNED NOT NULL,
  conjunto_id     BIGINT UNSIGNED NOT NULL,
  nome            VARCHAR(140) NOT NULL,
  formato         ENUM('imagem','video','carrossel','catalogo','reels') NOT NULL,
  tema_criativo   VARCHAR(80)  NOT NULL,
  url_destino     VARCHAR(300) NOT NULL COMMENT 'Com o template de UTMs configurado',
  status          ENUM('ACTIVE','PAUSED','ARCHIVED') NOT NULL,
  PRIMARY KEY (anuncio_id),
  KEY ix_ma_conjunto (conjunto_id),
  CONSTRAINT fk_ma_conjunto FOREIGN KEY (conjunto_id) REFERENCES meta_conjuntos (conjunto_id)
) ENGINE=InnoDB;

CREATE TABLE meta_metricas_diarias (
  data                         DATE NOT NULL COMMENT 'Fuso da conta',
  anuncio_id                   BIGINT UNSIGNED NOT NULL,
  investimento                 DECIMAL(12,2) NOT NULL,
  impressoes                   INT UNSIGNED NOT NULL,
  alcance                      INT UNSIGNED NOT NULL,
  cliques_todos                INT UNSIGNED NOT NULL,
  cliques_link                 INT UNSIGNED NOT NULL,
  visualizacoes_pagina_destino INT UNSIGNED NOT NULL,
  adicoes_carrinho             INT UNSIGNED NOT NULL COMMENT 'Reportado pela plataforma',
  compras                      INT UNSIGNED NOT NULL COMMENT 'Reportado (7d clique + 1d visualização)',
  valor_compras                DECIMAL(12,2) NOT NULL COMMENT 'Reportado pela plataforma',
  PRIMARY KEY (data, anuncio_id),
  KEY ix_mmd_anuncio (anuncio_id, data),
  CONSTRAINT fk_mmd_anuncio FOREIGN KEY (anuncio_id) REFERENCES meta_anuncios (anuncio_id),
  CONSTRAINT ck_mmd_cliques CHECK (cliques_link <= cliques_todos)
) ENGINE=InnoDB COMMENT='Insights diários por anúncio, como exportado da API de Marketing';

-- ---------------------------------------------------------------------
-- 5. MÍDIA PAGA - GOOGLE ADS
-- ---------------------------------------------------------------------

CREATE TABLE google_contas (
  conta_id       VARCHAR(12) NOT NULL COMMENT 'Customer ID 000-000-0000',
  nome           VARCHAR(80) NOT NULL,
  moeda          CHAR(3)     NOT NULL DEFAULT 'BRL',
  fuso_horario   VARCHAR(40) NOT NULL,
  PRIMARY KEY (conta_id)
) ENGINE=InnoDB;

CREATE TABLE google_campanhas (
  campanha_id       BIGINT UNSIGNED NOT NULL,
  conta_id          VARCHAR(12) NOT NULL,
  nome              VARCHAR(120) NOT NULL,
  tipo_canal        ENUM('SEARCH','SHOPPING','PERFORMANCE_MAX','DEMAND_GEN') NOT NULL,
  estrategia_lance  ENUM('MAXIMIZE_CONVERSIONS','MAXIMIZE_CONVERSION_VALUE','TARGET_ROAS','TARGET_CPA','MANUAL_CPC') NOT NULL,
  roas_alvo         DECIMAL(6,2) NULL,
  campanha_marca    TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1 = Search de marca (termos com o nome da loja)',
  orcamento_diario  DECIMAL(12,2) NOT NULL,
  status            ENUM('ENABLED','PAUSED','REMOVED') NOT NULL,
  inicio            DATE NOT NULL,
  fim               DATE NULL,
  PRIMARY KEY (campanha_id),
  KEY ix_gc_conta (conta_id),
  CONSTRAINT fk_gc_conta FOREIGN KEY (conta_id) REFERENCES google_contas (conta_id)
) ENGINE=InnoDB;

CREATE TABLE google_grupos_anuncio (
  grupo_id     BIGINT UNSIGNED NOT NULL,
  campanha_id  BIGINT UNSIGNED NOT NULL,
  nome         VARCHAR(140) NOT NULL,
  tipo         ENUM('SEARCH_STANDARD','SHOPPING_PRODUCT_ADS','ASSET_GROUP','DEMAND_GEN') NOT NULL
               COMMENT 'Em PMax, o grupo é o asset group',
  status       ENUM('ENABLED','PAUSED','REMOVED') NOT NULL,
  PRIMARY KEY (grupo_id),
  KEY ix_gg_campanha (campanha_id),
  CONSTRAINT fk_gg_campanha FOREIGN KEY (campanha_id) REFERENCES google_campanhas (campanha_id)
) ENGINE=InnoDB;

CREATE TABLE google_palavras_chave (
  palavra_chave_id      BIGINT UNSIGNED NOT NULL,
  grupo_id              BIGINT UNSIGNED NOT NULL,
  texto                 VARCHAR(120) NOT NULL,
  tipo_correspondencia  ENUM('EXACT','PHRASE','BROAD') NOT NULL,
  indice_qualidade      TINYINT UNSIGNED NULL,
  status                ENUM('ENABLED','PAUSED','REMOVED') NOT NULL,
  PRIMARY KEY (palavra_chave_id),
  KEY ix_gpc_grupo (grupo_id),
  CONSTRAINT fk_gpc_grupo FOREIGN KEY (grupo_id) REFERENCES google_grupos_anuncio (grupo_id),
  CONSTRAINT ck_gpc_iq CHECK (indice_qualidade IS NULL OR indice_qualidade BETWEEN 1 AND 10)
) ENGINE=InnoDB;

CREATE TABLE google_metricas_diarias (
  data                  DATE NOT NULL COMMENT 'Fuso da conta',
  grupo_id              BIGINT UNSIGNED NOT NULL,
  investimento          DECIMAL(12,2) NOT NULL,
  impressoes            INT UNSIGNED NOT NULL,
  cliques               INT UNSIGNED NOT NULL,
  conversoes            DECIMAL(10,2) NOT NULL COMMENT 'Reportado (data-driven, fracionado)',
  valor_conversao       DECIMAL(12,2) NOT NULL,
  parcela_impressoes    DECIMAL(5,4) NULL COMMENT 'Search impression share; nulo fora de Search',
  PRIMARY KEY (data, grupo_id),
  KEY ix_gmd_grupo (grupo_id, data),
  CONSTRAINT fk_gmd_grupo FOREIGN KEY (grupo_id) REFERENCES google_grupos_anuncio (grupo_id)
) ENGINE=InnoDB;

CREATE TABLE google_palavras_chave_metricas_diarias (
  data              DATE NOT NULL,
  palavra_chave_id  BIGINT UNSIGNED NOT NULL,
  investimento      DECIMAL(12,2) NOT NULL,
  impressoes        INT UNSIGNED NOT NULL,
  cliques           INT UNSIGNED NOT NULL,
  conversoes        DECIMAL(10,2) NOT NULL,
  valor_conversao   DECIMAL(12,2) NOT NULL,
  PRIMARY KEY (data, palavra_chave_id),
  KEY ix_gpcm_kw (palavra_chave_id, data),
  CONSTRAINT fk_gpcm_kw FOREIGN KEY (palavra_chave_id) REFERENCES google_palavras_chave (palavra_chave_id)
) ENGINE=InnoDB COMMENT='Somente campanhas SEARCH. A soma bate com google_metricas_diarias do grupo';

-- ---------------------------------------------------------------------
-- 6. CUPONS
-- ---------------------------------------------------------------------

CREATE TABLE cupons (
  cupom_id        SMALLINT UNSIGNED NOT NULL,
  codigo          VARCHAR(30)  NOT NULL,
  descricao       VARCHAR(120) NOT NULL,
  tipo_desconto   ENUM('percentual','valor_fixo','frete_gratis') NOT NULL,
  valor_desconto  DECIMAL(10,2) NOT NULL COMMENT '% (0-100) ou R$',
  pedido_minimo   DECIMAL(10,2) NULL,
  canal           ENUM('geral','primeira_compra','influenciador','email','whatsapp','sazonal','recuperacao_carrinho') NOT NULL,
  valido_de       DATE NOT NULL,
  valido_ate      DATE NULL,
  limite_usos     INT UNSIGNED NULL,
  PRIMARY KEY (cupom_id),
  UNIQUE KEY uq_cupons_codigo (codigo),
  CONSTRAINT ck_cupons_pct CHECK (tipo_desconto <> 'percentual' OR valor_desconto BETWEEN 0 AND 100)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 7. TRACKING (GTM server-side, padrão GA4)
-- ---------------------------------------------------------------------

CREATE TABLE cliques_midia (
  clique_id               BIGINT UNSIGNED NOT NULL,
  plataforma              ENUM('meta','google') NOT NULL,
  click_id                VARCHAR(120) NOT NULL COMMENT 'gclid ou fbclid',
  meta_anuncio_id         BIGINT UNSIGNED NULL,
  google_grupo_id         BIGINT UNSIGNED NULL,
  google_palavra_chave_id BIGINT UNSIGNED NULL,
  clicado_em              DATETIME(3) NOT NULL COMMENT 'UTC',
  PRIMARY KEY (clique_id),
  UNIQUE KEY uq_cliques_click_id (click_id),
  KEY ix_cliques_meta (meta_anuncio_id),
  KEY ix_cliques_google (google_grupo_id),
  KEY ix_cliques_data (clicado_em),
  CONSTRAINT fk_cliques_meta_anuncio FOREIGN KEY (meta_anuncio_id) REFERENCES meta_anuncios (anuncio_id),
  CONSTRAINT fk_cliques_google_grupo FOREIGN KEY (google_grupo_id) REFERENCES google_grupos_anuncio (grupo_id),
  CONSTRAINT fk_cliques_google_kw    FOREIGN KEY (google_palavra_chave_id) REFERENCES google_palavras_chave (palavra_chave_id),
  CONSTRAINT ck_cliques_plataforma CHECK (
    (plataforma = 'meta'   AND meta_anuncio_id IS NOT NULL AND google_grupo_id IS NULL) OR
    (plataforma = 'google' AND google_grupo_id IS NOT NULL AND meta_anuncio_id IS NULL))
) ENGINE=InnoDB COMMENT='Clique em anúncio que gerou sessão, ligado pelo click id (gclid/fbclid)';

CREATE TABLE sessoes (
  sessao_id                BIGINT UNSIGNED NOT NULL,
  ga_session_id            INT UNSIGNED NOT NULL COMMENT 'Timestamp unix do início, como no cookie _ga_<id>',
  client_id                VARCHAR(40)  NULL COMMENT 'Cookie _ga. Nulo com analytics_storage negado',
  cliente_id               INT UNSIGNED NULL COMMENT 'user_id (cliente logado ou identificado)',
  iniciada_em              DATETIME(3)  NOT NULL COMMENT 'UTC',
  duracao_seg              INT UNSIGNED NOT NULL,
  dispositivo              ENUM('mobile','desktop','tablet') NULL,
  sistema_operacional      VARCHAR(20)  NULL,
  navegador                VARCHAR(30)  NULL,
  uf                       CHAR(2)      NULL COMMENT 'Geolocalização por IP',
  landing_page             VARCHAR(200) NOT NULL,
  referrer                 VARCHAR(200) NULL,
  utm_source               VARCHAR(60)  NULL,
  utm_medium               VARCHAR(40)  NULL,
  utm_campaign             VARCHAR(120) NULL,
  utm_content              VARCHAR(120) NULL,
  utm_term                 VARCHAR(120) NULL,
  gclid                    VARCHAR(120) NULL,
  fbclid                   VARCHAR(120) NULL,
  fbp                      VARCHAR(60)  NULL COMMENT 'Cookie _fbp',
  fbc                      VARCHAR(160) NULL COMMENT 'Cookie _fbc (derivado do fbclid)',
  clique_id                BIGINT UNSIGNED NULL,
  consent_analytics_storage ENUM('granted','denied') NOT NULL,
  consent_ad_storage        ENUM('granted','denied') NOT NULL,
  consent_ad_user_data      ENUM('granted','denied') NOT NULL,
  consent_ad_personalization ENUM('granted','denied') NOT NULL,
  primeira_visita          TINYINT(1)   NOT NULL,
  engajada                 TINYINT(1)   NOT NULL COMMENT 'Critério GA4: >10s, 2+ page views ou conversão',
  PRIMARY KEY (sessao_id),
  KEY ix_sessoes_inicio (iniciada_em),
  KEY ix_sessoes_cliente (cliente_id),
  KEY ix_sessoes_client_id (client_id),
  KEY ix_sessoes_clique (clique_id),
  CONSTRAINT fk_sessoes_cliente FOREIGN KEY (cliente_id) REFERENCES clientes (cliente_id),
  CONSTRAINT fk_sessoes_clique  FOREIGN KEY (clique_id)  REFERENCES cliques_midia (clique_id)
) ENGINE=InnoDB COMMENT='Sessões reconstruídas pelo container server-side';

-- ---------------------------------------------------------------------
-- 8. PEDIDOS
-- ---------------------------------------------------------------------

CREATE TABLE pedidos (
  pedido_id            INT UNSIGNED NOT NULL,
  numero_pedido        VARCHAR(12)  NOT NULL,
  cliente_id           INT UNSIGNED NOT NULL,
  endereco_entrega_id  INT UNSIGNED NULL COMMENT 'Nulo = retirada na loja',
  sessao_id            BIGINT UNSIGNED NULL COMMENT 'Sessão da compra. Nulo = sem rastreio (adblock, WhatsApp)',
  cupom_id             SMALLINT UNSIGNED NULL,
  canal_venda          ENUM('site','whatsapp') NOT NULL,
  status               ENUM('aguardando_pagamento','pago','enviado','entregue','cancelado','devolvido') NOT NULL,
  criado_em            DATETIME NOT NULL COMMENT 'Horário local America/Sao_Paulo',
  pago_em              DATETIME NULL,
  cancelado_em         DATETIME NULL,
  subtotal             DECIMAL(12,2) NOT NULL,
  desconto             DECIMAL(12,2) NOT NULL DEFAULT 0,
  frete                DECIMAL(12,2) NOT NULL DEFAULT 0,
  total                DECIMAL(12,2) NOT NULL,
  pedido_teste         TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1 = pedido de teste da equipe (excluir das análises)',
  PRIMARY KEY (pedido_id),
  UNIQUE KEY uq_pedidos_numero (numero_pedido),
  KEY ix_pedidos_cliente (cliente_id, criado_em),
  KEY ix_pedidos_criado (criado_em),
  KEY ix_pedidos_sessao (sessao_id),
  KEY ix_pedidos_status (status),
  CONSTRAINT fk_pedidos_cliente  FOREIGN KEY (cliente_id)          REFERENCES clientes (cliente_id),
  CONSTRAINT fk_pedidos_endereco FOREIGN KEY (endereco_entrega_id) REFERENCES enderecos (endereco_id),
  CONSTRAINT fk_pedidos_sessao   FOREIGN KEY (sessao_id)           REFERENCES sessoes (sessao_id),
  CONSTRAINT fk_pedidos_cupom    FOREIGN KEY (cupom_id)            REFERENCES cupons (cupom_id),
  CONSTRAINT ck_pedidos_total CHECK (total = subtotal - desconto + frete),
  CONSTRAINT ck_pedidos_valores CHECK (subtotal >= 0 AND desconto >= 0 AND frete >= 0)
) ENGINE=InnoDB;

CREATE TABLE itens_pedido (
  item_pedido_id   INT UNSIGNED NOT NULL,
  pedido_id        INT UNSIGNED NOT NULL,
  variante_id      INT UNSIGNED NOT NULL,
  quantidade       DECIMAL(10,2) NOT NULL COMMENT 'Metros ou rolos, conforme formato da variante',
  preco_unitario   DECIMAL(12,2) NOT NULL COMMENT 'Preço praticado (já com promoção de vitrine)',
  preco_tabela     DECIMAL(12,2) NOT NULL,
  custo_unitario   DECIMAL(12,2) NOT NULL,
  total_item       DECIMAL(12,2) NOT NULL,
  PRIMARY KEY (item_pedido_id),
  KEY ix_itens_pedido (pedido_id),
  KEY ix_itens_variante (variante_id),
  CONSTRAINT fk_itens_pedido   FOREIGN KEY (pedido_id)   REFERENCES pedidos (pedido_id),
  CONSTRAINT fk_itens_variante FOREIGN KEY (variante_id) REFERENCES variantes (variante_id),
  CONSTRAINT ck_itens_qtd CHECK (quantidade > 0)
) ENGINE=InnoDB;

CREATE TABLE pagamentos (
  pagamento_id      INT UNSIGNED NOT NULL,
  pedido_id         INT UNSIGNED NOT NULL,
  tentativa         TINYINT UNSIGNED NOT NULL DEFAULT 1,
  metodo            ENUM('pix','cartao_credito','boleto') NOT NULL,
  bandeira          VARCHAR(20) NULL,
  parcelas          TINYINT UNSIGNED NOT NULL DEFAULT 1,
  valor             DECIMAL(12,2) NOT NULL,
  status            ENUM('aprovado','recusado','pendente','expirado','estornado') NOT NULL,
  gateway           VARCHAR(30) NOT NULL,
  transacao_gateway VARCHAR(40) NOT NULL,
  criado_em         DATETIME NOT NULL COMMENT 'Horário local',
  atualizado_em     DATETIME NULL,
  PRIMARY KEY (pagamento_id),
  UNIQUE KEY uq_pagamentos_transacao (transacao_gateway),
  KEY ix_pagamentos_pedido (pedido_id),
  CONSTRAINT fk_pagamentos_pedido FOREIGN KEY (pedido_id) REFERENCES pedidos (pedido_id),
  CONSTRAINT ck_pagamentos_parcelas CHECK (parcelas BETWEEN 1 AND 12),
  CONSTRAINT ck_pagamentos_pix CHECK (metodo = 'cartao_credito' OR parcelas = 1)
) ENGINE=InnoDB;

CREATE TABLE fretes (
  frete_id             INT UNSIGNED NOT NULL,
  pedido_id            INT UNSIGNED NOT NULL,
  transportadora       VARCHAR(30) NOT NULL,
  servico              VARCHAR(30) NOT NULL,
  peso_kg              DECIMAL(8,3) NOT NULL,
  valor_cobrado        DECIMAL(10,2) NOT NULL,
  custo_real           DECIMAL(10,2) NOT NULL,
  frete_gratis         TINYINT(1) NOT NULL,
  prazo_estimado_dias  TINYINT UNSIGNED NOT NULL,
  postado_em           DATETIME NULL,
  entregue_em          DATETIME NULL,
  codigo_rastreio      VARCHAR(20) NULL,
  PRIMARY KEY (frete_id),
  UNIQUE KEY uq_fretes_pedido (pedido_id),
  CONSTRAINT fk_fretes_pedido FOREIGN KEY (pedido_id) REFERENCES pedidos (pedido_id),
  CONSTRAINT ck_fretes_datas CHECK (entregue_em IS NULL OR postado_em IS NULL OR entregue_em >= postado_em)
) ENGINE=InnoDB;

CREATE TABLE devolucoes (
  devolucao_id       INT UNSIGNED NOT NULL,
  pedido_id          INT UNSIGNED NOT NULL,
  item_pedido_id     INT UNSIGNED NOT NULL,
  motivo             ENUM('cor_diferente_da_foto','defeito_no_tecido','metragem_incorreta','gramatura_diferente','desistencia','atraso_na_entrega') NOT NULL,
  quantidade         DECIMAL(10,2) NOT NULL,
  valor_reembolsado  DECIMAL(12,2) NOT NULL,
  status             ENUM('solicitada','aprovada','recusada','concluida') NOT NULL,
  solicitada_em      DATETIME NOT NULL,
  concluida_em       DATETIME NULL,
  PRIMARY KEY (devolucao_id),
  KEY ix_devolucoes_pedido (pedido_id),
  KEY ix_devolucoes_item (item_pedido_id),
  CONSTRAINT fk_devolucoes_pedido FOREIGN KEY (pedido_id)      REFERENCES pedidos (pedido_id),
  CONSTRAINT fk_devolucoes_item   FOREIGN KEY (item_pedido_id) REFERENCES itens_pedido (item_pedido_id)
) ENGINE=InnoDB;

CREATE TABLE movimentacoes_estoque (
  movimentacao_id  BIGINT UNSIGNED NOT NULL,
  variante_id      INT UNSIGNED NOT NULL,
  tipo             ENUM('entrada_compra','saida_venda','entrada_devolucao','ajuste_inventario','perda_avaria') NOT NULL,
  quantidade       DECIMAL(10,2) NOT NULL COMMENT 'Positiva = entrada, negativa = saída',
  ocorrido_em      DATETIME NOT NULL COMMENT 'Horário local',
  pedido_id        INT UNSIGNED NULL,
  devolucao_id     INT UNSIGNED NULL,
  fornecedor_id    SMALLINT UNSIGNED NULL,
  PRIMARY KEY (movimentacao_id),
  KEY ix_mov_variante_data (variante_id, ocorrido_em),
  KEY ix_mov_pedido (pedido_id),
  CONSTRAINT fk_mov_variante   FOREIGN KEY (variante_id)   REFERENCES variantes (variante_id),
  CONSTRAINT fk_mov_pedido     FOREIGN KEY (pedido_id)     REFERENCES pedidos (pedido_id),
  CONSTRAINT fk_mov_devolucao  FOREIGN KEY (devolucao_id)  REFERENCES devolucoes (devolucao_id),
  CONSTRAINT fk_mov_fornecedor FOREIGN KEY (fornecedor_id) REFERENCES fornecedores (fornecedor_id)
) ENGINE=InnoDB;

CREATE TABLE avaliacoes (
  avaliacao_id      INT UNSIGNED NOT NULL,
  pedido_id         INT UNSIGNED NOT NULL,
  cliente_id        INT UNSIGNED NOT NULL,
  produto_id        INT UNSIGNED NOT NULL,
  nota              TINYINT UNSIGNED NOT NULL,
  titulo            VARCHAR(80)  NULL,
  comentario        VARCHAR(400) NULL,
  criada_em         DATETIME NOT NULL,
  PRIMARY KEY (avaliacao_id),
  UNIQUE KEY uq_avaliacoes_pedido_produto (pedido_id, produto_id),
  KEY ix_avaliacoes_produto (produto_id),
  CONSTRAINT fk_av_pedido  FOREIGN KEY (pedido_id)  REFERENCES pedidos (pedido_id),
  CONSTRAINT fk_av_cliente FOREIGN KEY (cliente_id) REFERENCES clientes (cliente_id),
  CONSTRAINT fk_av_produto FOREIGN KEY (produto_id) REFERENCES produtos (produto_id),
  CONSTRAINT ck_av_nota CHECK (nota BETWEEN 1 AND 5)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 9. EVENTOS GA4 E ENVIOS SERVER-SIDE
-- ---------------------------------------------------------------------

CREATE TABLE eventos (
  evento_id         BIGINT UNSIGNED NOT NULL COMMENT 'Chave surrogate da linha',
  event_id          CHAR(36) NOT NULL COMMENT 'ID de deduplicação browser/server (não é único: há duplicatas)',
  sessao_id         BIGINT UNSIGNED NOT NULL,
  cliente_id        INT UNSIGNED NULL COMMENT 'user_id no momento do evento',
  event_name        ENUM('page_view','view_item','add_to_cart','begin_checkout','add_payment_info','purchase') NOT NULL,
  event_timestamp   DATETIME(3) NOT NULL COMMENT 'UTC, exceto defeito do container v2.3 (ver docs)',
  page_location     VARCHAR(200) NOT NULL,
  variante_id       INT UNSIGNED NULL,
  quantidade        DECIMAL(10,2) NULL,
  valor             DECIMAL(12,2) NULL,
  moeda             CHAR(3) NULL,
  transaction_id    VARCHAR(12) NULL COMMENT 'numero_pedido no evento purchase',
  pedido_id         INT UNSIGNED NULL,
  fonte             ENUM('web','server') NOT NULL COMMENT 'web = tag GA4 no navegador; server = container sGTM',
  versao_container  VARCHAR(8) NOT NULL,
  PRIMARY KEY (evento_id),
  KEY ix_eventos_event_id (event_id),
  KEY ix_eventos_sessao (sessao_id),
  KEY ix_eventos_nome_ts (event_name, event_timestamp),
  KEY ix_eventos_pedido (pedido_id),
  CONSTRAINT fk_eventos_sessao   FOREIGN KEY (sessao_id)   REFERENCES sessoes (sessao_id),
  CONSTRAINT fk_eventos_cliente  FOREIGN KEY (cliente_id)  REFERENCES clientes (cliente_id),
  CONSTRAINT fk_eventos_variante FOREIGN KEY (variante_id) REFERENCES variantes (variante_id),
  CONSTRAINT fk_eventos_pedido   FOREIGN KEY (pedido_id)   REFERENCES pedidos (pedido_id)
) ENGINE=InnoDB COMMENT='Log de eventos no padrão GA4 recebidos pelo GTM server-side';

CREATE TABLE envios_conversao (
  envio_id              BIGINT UNSIGNED NOT NULL,
  evento_id             BIGINT UNSIGNED NOT NULL,
  plataforma            ENUM('meta_capi','google_ads_ec') NOT NULL,
  status                ENUM('enviado','erro','bloqueado_consentimento','deduplicado') NOT NULL,
  http_status           SMALLINT UNSIGNED NULL,
  enviado_em            DATETIME(3) NULL COMMENT 'UTC',
  email_hash_enviado    TINYINT(1) NOT NULL,
  telefone_hash_enviado TINYINT(1) NOT NULL,
  fbp_enviado           TINYINT(1) NOT NULL,
  fbc_enviado           TINYINT(1) NOT NULL,
  gclid_enviado         TINYINT(1) NOT NULL,
  event_match_quality   DECIMAL(3,1) NULL COMMENT 'EMQ estimado pela Meta (0-10)',
  mensagem_erro         VARCHAR(120) NULL,
  PRIMARY KEY (envio_id),
  KEY ix_envios_evento (evento_id),
  KEY ix_envios_plat_status (plataforma, status),
  CONSTRAINT fk_envios_evento FOREIGN KEY (evento_id) REFERENCES eventos (evento_id)
) ENGINE=InnoDB COMMENT='Log de envio server-side para Meta CAPI e Google Ads Enhanced Conversions';

-- ---------------------------------------------------------------------
-- 10. ATRIBUIÇÃO
-- ---------------------------------------------------------------------

CREATE TABLE atribuicoes (
  atribuicao_id       INT UNSIGNED NOT NULL,
  pedido_id           INT UNSIGNED NOT NULL,
  modelo              ENUM('last_click','first_click','linear','data_driven') NOT NULL,
  sessao_id           BIGINT UNSIGNED NOT NULL,
  posicao             TINYINT UNSIGNED NOT NULL COMMENT '1 = primeiro toque',
  total_toques        TINYINT UNSIGNED NOT NULL,
  canal               VARCHAR(30) NOT NULL COMMENT 'Agrupamento de canais padrão',
  meta_campanha_id    BIGINT UNSIGNED NULL,
  google_campanha_id  BIGINT UNSIGNED NULL,
  peso                DECIMAL(7,6) NOT NULL,
  receita_atribuida   DECIMAL(12,2) NOT NULL,
  PRIMARY KEY (atribuicao_id),
  UNIQUE KEY uq_atrib (pedido_id, modelo, sessao_id),
  KEY ix_atrib_modelo_canal (modelo, canal),
  KEY ix_atrib_sessao (sessao_id),
  CONSTRAINT fk_atrib_pedido  FOREIGN KEY (pedido_id)          REFERENCES pedidos (pedido_id),
  CONSTRAINT fk_atrib_sessao  FOREIGN KEY (sessao_id)          REFERENCES sessoes (sessao_id),
  CONSTRAINT fk_atrib_meta    FOREIGN KEY (meta_campanha_id)   REFERENCES meta_campanhas (campanha_id),
  CONSTRAINT fk_atrib_google  FOREIGN KEY (google_campanha_id) REFERENCES google_campanhas (campanha_id),
  CONSTRAINT ck_atrib_peso CHECK (peso > 0 AND peso <= 1)
) ENGINE=InnoDB COMMENT='Crédito por toque (lookback 30 dias). A soma dos pesos por pedido e modelo é 1';

-- ---------------------------------------------------------------------
-- 11. CAMADA DE MMM: CANAIS, REGIÕES, MÍDIA POR UF, CALENDÁRIO E TESTE GEO
--     (gerador/regional.py; parâmetros em gerador/parametros_mmm.yaml)
-- ---------------------------------------------------------------------

CREATE TABLE canais_midia (
  canal_id           TINYINT UNSIGNED NOT NULL,
  canal              VARCHAR(30) NOT NULL COMMENT 'Canal de compra (grão do relatório da plataforma)',
  canal_mmm          VARCHAR(30) NOT NULL COMMENT 'Agrupamento usado no MMM (orçamento decidido em conjunto)',
  plataforma         VARCHAR(20) NOT NULL,
  tipo_investimento  ENUM('pago','proprio') NOT NULL COMMENT 'proprio = custo de ferramenta (CRM), fora do otimizador',
  PRIMARY KEY (canal_id),
  UNIQUE KEY uq_canais_midia_canal (canal),
  KEY ix_canais_midia_mmm (canal_mmm)
) ENGINE=InnoDB COMMENT='Dimensão de canais de mídia';

CREATE TABLE regioes (
  uf                  CHAR(2)      NOT NULL,
  nome                VARCHAR(40)  NOT NULL,
  macrorregiao        VARCHAR(20)  NOT NULL,
  sigla_macrorregiao  CHAR(2)      NOT NULL,
  peso_populacional   DECIMAL(8,6) NOT NULL COMMENT 'Participação da UF na base de clientes potenciais',
  entrega_disponivel  TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '0 = a loja não entrega na UF (não pode haver mídia)',
  PRIMARY KEY (uf),
  CONSTRAINT ck_regioes_peso CHECK (peso_populacional > 0 AND peso_populacional < 1),
  CONSTRAINT ck_regioes_macro CHECK (sigla_macrorregiao IN ('SE','S','CO','NE','N'))
) ENGINE=InnoDB COMMENT='UFs atendidas pela loja';

CREATE TABLE midia_regional_diaria (
  data                   DATE NOT NULL COMMENT 'Fuso da conta',
  canal_id               TINYINT UNSIGNED NOT NULL,
  uf                     CHAR(2) NOT NULL,
  investimento           DECIMAL(12,2) NOT NULL,
  impressoes             INT UNSIGNED NULL COMMENT 'Nulo = canal sem impressões (afiliados). CRM: e-mails entregues',
  cliques                INT UNSIGNED NOT NULL,
  conversoes_plataforma  DECIMAL(10,2) NULL COMMENT 'Conversões por clique reportadas no relatório geográfico',
  PRIMARY KEY (data, canal_id, uf),
  KEY ix_mrd_uf_data (uf, data),
  KEY ix_mrd_canal_data (canal_id, data),
  CONSTRAINT fk_mrd_canal FOREIGN KEY (canal_id) REFERENCES canais_midia (canal_id),
  CONSTRAINT fk_mrd_uf    FOREIGN KEY (uf)       REFERENCES regioes (uf),
  CONSTRAINT ck_mrd_investimento CHECK (investimento >= 0),
  CONSTRAINT ck_mrd_conversoes CHECK (conversoes_plataforma IS NULL OR (conversoes_plataforma >= 0 AND conversoes_plataforma <= cliques))
) ENGINE=InnoDB COMMENT='Relatório geográfico das plataformas: investimento, impressões e cliques por dia, canal e UF';

CREATE TABLE calendario_comercial (
  data              DATE NOT NULL,
  dia_semana        TINYINT UNSIGNED NOT NULL COMMENT '1 = segunda ... 7 = domingo',
  feriado_nacional  TINYINT(1) NOT NULL DEFAULT 0,
  nome_feriado      VARCHAR(60)  NULL,
  evento_comercial  VARCHAR(120) NULL COMMENT 'Datas comerciais (black_friday, dia_das_maes, natal...), separadas por |',
  promocao_loja     TINYINT(1) NOT NULL DEFAULT 0,
  nome_promocao     VARCHAR(60)  NULL,
  PRIMARY KEY (data),
  CONSTRAINT ck_cal_dia CHECK (dia_semana BETWEEN 1 AND 7),
  CONSTRAINT ck_cal_feriado CHECK ((feriado_nacional = 1) = (nome_feriado IS NOT NULL)),
  CONSTRAINT ck_cal_promo CHECK ((promocao_loja = 1) = (nome_promocao IS NOT NULL))
) ENGINE=InnoDB COMMENT='Calendário de marketing: feriados nacionais, datas comerciais e promoções da loja';

CREATE TABLE testes_geo (
  teste_id                    SMALLINT UNSIGNED NOT NULL,
  nome                        VARCHAR(80) NOT NULL,
  canal_id                    TINYINT UNSIGNED NOT NULL COMMENT 'Canal principal testado',
  canal_mmm                   VARCHAR(30) NOT NULL,
  tipo_mudanca                ENUM('desligar','reduzir','aumentar','dobrar') NOT NULL,
  multiplicador_investimento  DECIMAL(4,2) NOT NULL COMMENT 'Investimento nas UFs de tratamento / planejado (0 = desligado)',
  pre_inicio                  DATE NOT NULL COMMENT 'Início do pré-período usado no desenho',
  inicio                      DATE NOT NULL,
  fim                         DATE NOT NULL,
  resfriamento_fim            DATE NOT NULL COMMENT 'Fim da janela de carryover depois do teste',
  metrica_principal           VARCHAR(30) NOT NULL,
  descricao                   VARCHAR(400) NULL,
  PRIMARY KEY (teste_id),
  CONSTRAINT fk_tg_canal FOREIGN KEY (canal_id) REFERENCES canais_midia (canal_id),
  CONSTRAINT ck_tg_mult CHECK (multiplicador_investimento >= 0),
  CONSTRAINT ck_tg_datas CHECK (pre_inicio < inicio AND inicio <= fim AND fim <= resfriamento_fim)
) ENGINE=InnoDB COMMENT='Registro dos testes de incrementalidade geográfica';

CREATE TABLE testes_geo_regioes (
  teste_id  SMALLINT UNSIGNED NOT NULL,
  uf        CHAR(2) NOT NULL,
  grupo     ENUM('tratamento','controle') NOT NULL,
  PRIMARY KEY (teste_id, uf),
  CONSTRAINT fk_tgr_teste FOREIGN KEY (teste_id) REFERENCES testes_geo (teste_id),
  CONSTRAINT fk_tgr_uf    FOREIGN KEY (uf)       REFERENCES regioes (uf)
) ENGINE=InnoDB COMMENT='UFs de cada teste: tratamento recebeu a mudança, controle seguiu o plano';

-- ---------------------------------------------------------------------
-- 12. MÍDIA PAGA - TIKTOK ADS, AFILIADOS E CRM
-- ---------------------------------------------------------------------

CREATE TABLE tiktok_campanhas (
  campanha_id  BIGINT UNSIGNED NOT NULL,
  conta_id     VARCHAR(24)  NOT NULL,
  nome         VARCHAR(120) NOT NULL,
  objetivo     ENUM('CONVERSIONS','PRODUCT_SALES','REACH','TRAFFIC') NOT NULL,
  status       ENUM('ENABLE','DISABLE') NOT NULL,
  inicio       DATE NOT NULL,
  fim          DATE NULL,
  PRIMARY KEY (campanha_id),
  CONSTRAINT ck_tkc_datas CHECK (fim IS NULL OR fim >= inicio)
) ENGINE=InnoDB;

CREATE TABLE tiktok_metricas_diarias (
  data              DATE NOT NULL COMMENT 'Fuso da conta',
  campanha_id       BIGINT UNSIGNED NOT NULL,
  investimento      DECIMAL(12,2) NOT NULL,
  impressoes        INT UNSIGNED NOT NULL,
  cliques           INT UNSIGNED NOT NULL,
  conversoes        INT UNSIGNED NOT NULL COMMENT 'Reportado (7d clique + 1d visualização)',
  valor_conversoes  DECIMAL(12,2) NOT NULL,
  PRIMARY KEY (data, campanha_id),
  CONSTRAINT fk_tkm_campanha FOREIGN KEY (campanha_id) REFERENCES tiktok_campanhas (campanha_id),
  CONSTRAINT ck_tkm_valores CHECK (investimento >= 0 AND cliques <= impressoes AND conversoes <= cliques)
) ENGINE=InnoDB COMMENT='Relatório diário por campanha, como exportado da API do TikTok';

CREATE TABLE afiliados_parceiros (
  parceiro_id   SMALLINT UNSIGNED NOT NULL,
  nome          VARCHAR(80) NOT NULL,
  tipo          ENUM('conteudo','cupom','comparador') NOT NULL,
  comissao_pct  DECIMAL(4,2) NOT NULL,
  inicio        DATE NOT NULL,
  ativo         TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (parceiro_id),
  CONSTRAINT ck_afp_comissao CHECK (comissao_pct BETWEEN 0 AND 30)
) ENGINE=InnoDB COMMENT='Sites parceiros (conteúdo, cupom, comparador de preços)';

CREATE TABLE afiliados_metricas_diarias (
  data                DATE NOT NULL,
  parceiro_id         SMALLINT UNSIGNED NOT NULL,
  investimento        DECIMAL(12,2) NOT NULL COMMENT 'Fee de campanha negociado no mês, rateado por dia',
  cliques             INT UNSIGNED NOT NULL,
  pedidos_atribuidos  INT UNSIGNED NOT NULL COMMENT 'Último clique no link do parceiro (relatório da rede)',
  receita_atribuida   DECIMAL(12,2) NOT NULL,
  PRIMARY KEY (data, parceiro_id),
  CONSTRAINT fk_afm_parceiro FOREIGN KEY (parceiro_id) REFERENCES afiliados_parceiros (parceiro_id),
  CONSTRAINT ck_afm_valores CHECK (investimento >= 0 AND pedidos_atribuidos <= cliques)
) ENGINE=InnoDB;

CREATE TABLE crm_disparos (
  disparo_id     INT UNSIGNED NOT NULL,
  data           DATE NOT NULL,
  tipo_campanha  ENUM('newsletter','reativacao','carrinho_abandonado') NOT NULL,
  enviados       INT UNSIGNED NOT NULL,
  entregues      INT UNSIGNED NOT NULL,
  aberturas      INT UNSIGNED NOT NULL,
  cliques        INT UNSIGNED NOT NULL,
  descadastros   INT UNSIGNED NOT NULL,
  custo          DECIMAL(10,2) NOT NULL COMMENT 'Custo da ferramenta de disparo',
  PRIMARY KEY (disparo_id),
  UNIQUE KEY uq_crm_data_tipo (data, tipo_campanha),
  CONSTRAINT ck_crm_funil CHECK (entregues <= enviados AND aberturas <= entregues AND cliques <= aberturas),
  CONSTRAINT ck_crm_custo CHECK (custo >= 0)
) ENGINE=InnoDB COMMENT='Disparos de e-mail por dia e tipo de campanha';

SET FOREIGN_KEY_CHECKS = 1;
