# Diagrama entidade-relacionamento

O GitHub renderiza os blocos Mermaid abaixo. São três vistas do mesmo banco `tecidos`; as chaves estrangeiras atravessam as vistas (por exemplo, `pedidos.sessao_id` liga o transacional ao tracking).

## 1. Transacional (catálogo, estoque, clientes, pedidos)

```mermaid
erDiagram
    categorias ||--o{ categorias : "pai de"
    categorias ||--o{ produtos : classifica
    fornecedores ||--o{ produtos : fornece
    produtos ||--|{ variantes : "tem SKUs"
    variantes ||--o{ historico_precos : "preço/custo (SCD2)"
    variantes ||--|| estoque : "saldo atual"
    variantes ||--o{ estoque_diario : "fechamento diário"
    variantes ||--o{ movimentacoes_estoque : movimenta
    fornecedores ||--o{ movimentacoes_estoque : "entrada de compra"
    clientes ||--|{ enderecos : possui
    clientes ||--o{ pedidos : faz
    enderecos ||--o{ pedidos : "entrega em"
    cupons ||--o{ pedidos : "aplicado em"
    pedidos ||--|{ itens_pedido : contem
    variantes ||--o{ itens_pedido : vendida
    pedidos ||--|{ pagamentos : "tentativas"
    pedidos ||--|| fretes : envia
    pedidos ||--o{ devolucoes : gera
    itens_pedido ||--o{ devolucoes : devolvido
    devolucoes ||--o{ movimentacoes_estoque : "volta ao estoque"
    pedidos ||--o{ movimentacoes_estoque : baixa
    pedidos ||--o{ avaliacoes : recebe
    produtos ||--o{ avaliacoes : avaliado
    clientes ||--o{ avaliacoes : escreve

    categorias {
        smallint categoria_id PK
        smallint categoria_pai_id FK
        varchar nome
        varchar slug UK
    }
    fornecedores {
        smallint fornecedor_id PK
        varchar razao_social
        char cnpj UK
        char uf
        tinyint prazo_reposicao_dias
        decimal confiabilidade
    }
    produtos {
        int produto_id PK
        varchar sku_base UK
        varchar nome
        smallint categoria_id FK
        smallint fornecedor_id FK
        varchar composicao
        smallint largura_cm
    }
    variantes {
        int variante_id PK
        int produto_id FK
        varchar sku UK
        varchar cor
        varchar estampa
        smallint gramatura_gm2
        enum formato_venda
        decimal metros_por_unidade
        decimal preco_atual
        decimal custo_atual
    }
    historico_precos {
        int historico_preco_id PK
        int variante_id FK
        decimal preco
        decimal preco_promocional
        decimal custo
        date vigente_de
        date vigente_ate
        enum motivo
    }
    estoque {
        int variante_id PK
        decimal saldo_unidades
        decimal ponto_reposicao
        decimal lote_reposicao
    }
    estoque_diario {
        int variante_id PK
        date data PK
        decimal saldo_inicial
        decimal entradas
        decimal saidas
        decimal saldo_final
        tinyint em_ruptura
        decimal demanda_perdida
    }
    movimentacoes_estoque {
        bigint movimentacao_id PK
        int variante_id FK
        enum tipo
        decimal quantidade
        datetime ocorrido_em
        int pedido_id FK
        int devolucao_id FK
        smallint fornecedor_id FK
    }
    clientes {
        int cliente_id PK
        enum tipo_cliente
        enum tipo_pessoa
        varchar nome
        varchar email UK
        varchar telefone
        char cpf
        char cnpj
        datetime cadastrado_em
    }
    enderecos {
        int endereco_id PK
        int cliente_id FK
        enum tipo
        varchar cep
        varchar cidade
        char uf
        tinyint principal
    }
    cupons {
        smallint cupom_id PK
        varchar codigo UK
        enum tipo_desconto
        decimal valor_desconto
        enum canal
    }
    pedidos {
        int pedido_id PK
        varchar numero_pedido UK
        int cliente_id FK
        int endereco_entrega_id FK
        bigint sessao_id FK
        smallint cupom_id FK
        enum status
        datetime criado_em
        decimal total
        tinyint pedido_teste
    }
    itens_pedido {
        int item_pedido_id PK
        int pedido_id FK
        int variante_id FK
        decimal quantidade
        decimal preco_unitario
        decimal preco_tabela
        decimal custo_unitario
        decimal total_item
    }
    pagamentos {
        int pagamento_id PK
        int pedido_id FK
        tinyint tentativa
        enum metodo
        tinyint parcelas
        enum status
        varchar transacao_gateway UK
    }
    fretes {
        int frete_id PK
        int pedido_id FK
        varchar transportadora
        decimal valor_cobrado
        decimal custo_real
        tinyint frete_gratis
        datetime postado_em
        datetime entregue_em
    }
    devolucoes {
        int devolucao_id PK
        int pedido_id FK
        int item_pedido_id FK
        enum motivo
        decimal valor_reembolsado
        enum status
    }
    avaliacoes {
        int avaliacao_id PK
        int pedido_id FK
        int cliente_id FK
        int produto_id FK
        tinyint nota
    }
```

## 2. Tracking (GTM server-side, GA4) e atribuição

```mermaid
erDiagram
    cliques_midia ||--o{ sessoes : "originou (gclid/fbclid)"
    clientes ||--o{ sessoes : "user_id"
    sessoes ||--|{ eventos : contem
    clientes ||--o{ eventos : "user_id no evento"
    variantes ||--o{ eventos : "item do evento"
    pedidos ||--o{ eventos : "purchase"
    sessoes ||--o| pedidos : "sessão da compra"
    eventos ||--o{ envios_conversao : "Meta CAPI / Google EC"
    pedidos ||--|{ atribuicoes : "crédito por toque"
    sessoes ||--o{ atribuicoes : "toque"
    meta_campanhas ||--o{ atribuicoes : creditada
    google_campanhas ||--o{ atribuicoes : creditada

    cliques_midia {
        bigint clique_id PK
        enum plataforma
        varchar click_id UK
        bigint meta_anuncio_id FK
        bigint google_grupo_id FK
        bigint google_palavra_chave_id FK
        datetime clicado_em
    }
    sessoes {
        bigint sessao_id PK
        varchar client_id
        int cliente_id FK
        datetime iniciada_em
        enum dispositivo
        varchar utm_source
        varchar utm_medium
        varchar utm_campaign
        varchar gclid
        varchar fbclid
        varchar fbp
        varchar fbc
        bigint clique_id FK
        enum consent_analytics_storage
        enum consent_ad_storage
    }
    eventos {
        bigint evento_id PK
        char event_id
        bigint sessao_id FK
        int cliente_id FK
        enum event_name
        datetime event_timestamp
        int variante_id FK
        decimal valor
        varchar transaction_id
        int pedido_id FK
        enum fonte
        varchar versao_container
    }
    envios_conversao {
        bigint envio_id PK
        bigint evento_id FK
        enum plataforma
        enum status
        smallint http_status
        tinyint email_hash_enviado
        decimal event_match_quality
    }
    atribuicoes {
        int atribuicao_id PK
        int pedido_id FK
        enum modelo
        bigint sessao_id FK
        tinyint posicao
        varchar canal
        bigint meta_campanha_id FK
        bigint google_campanha_id FK
        decimal peso
        decimal receita_atribuida
    }
```

## 3. Mídia paga (Meta Ads e Google Ads)

```mermaid
erDiagram
    meta_contas ||--|{ meta_campanhas : contem
    meta_campanhas ||--|{ meta_conjuntos : contem
    meta_conjuntos ||--|{ meta_anuncios : contem
    meta_anuncios ||--o{ meta_metricas_diarias : "insights/dia"
    meta_anuncios ||--o{ cliques_midia : "clique (fbclid)"
    google_contas ||--|{ google_campanhas : contem
    google_campanhas ||--|{ google_grupos_anuncio : "grupos / asset groups"
    google_grupos_anuncio ||--o{ google_palavras_chave : contem
    google_grupos_anuncio ||--o{ google_metricas_diarias : "métricas/dia"
    google_palavras_chave ||--o{ google_palavras_chave_metricas_diarias : "métricas/dia"
    google_grupos_anuncio ||--o{ cliques_midia : "clique (gclid)"
    google_palavras_chave ||--o{ cliques_midia : "palavra do clique"

    meta_contas {
        varchar conta_id PK
        varchar nome
        varchar fuso_horario
    }
    meta_campanhas {
        bigint campanha_id PK
        varchar conta_id FK
        varchar nome
        enum objetivo
        enum estrategia
        enum status
        date inicio
        date fim
    }
    meta_conjuntos {
        bigint conjunto_id PK
        bigint campanha_id FK
        varchar publico
        enum otimizacao
    }
    meta_anuncios {
        bigint anuncio_id PK
        bigint conjunto_id FK
        enum formato
        varchar tema_criativo
        varchar url_destino
    }
    meta_metricas_diarias {
        date data PK
        bigint anuncio_id PK
        decimal investimento
        int impressoes
        int alcance
        int cliques_link
        int compras
        decimal valor_compras
    }
    google_contas {
        varchar conta_id PK
        varchar nome
        varchar fuso_horario
    }
    google_campanhas {
        bigint campanha_id PK
        varchar conta_id FK
        enum tipo_canal
        enum estrategia_lance
        tinyint campanha_marca
        decimal orcamento_diario
    }
    google_grupos_anuncio {
        bigint grupo_id PK
        bigint campanha_id FK
        enum tipo
    }
    google_palavras_chave {
        bigint palavra_chave_id PK
        bigint grupo_id FK
        varchar texto
        enum tipo_correspondencia
        tinyint indice_qualidade
    }
    google_metricas_diarias {
        date data PK
        bigint grupo_id PK
        decimal investimento
        int impressoes
        int cliques
        decimal conversoes
        decimal valor_conversao
        decimal parcela_impressoes
    }
    google_palavras_chave_metricas_diarias {
        date data PK
        bigint palavra_chave_id PK
        decimal investimento
        int cliques
        decimal conversoes
    }
```

## Cadeia clique → sessão → pedido

```mermaid
flowchart LR
    A[meta_anuncios / google_grupos_anuncio<br/>google_palavras_chave] -->|click id| B[cliques_midia]
    B -->|clique_id| C[sessoes]
    C -->|sessao_id| D[eventos GA4]
    D -->|purchase.pedido_id| E[pedidos]
    C -->|sessao_id da compra| E
    D -->|evento_id| F[envios_conversao<br/>Meta CAPI · Google EC]
    E --> G[atribuicoes<br/>last/first/linear/data-driven]
    C --> G
```
