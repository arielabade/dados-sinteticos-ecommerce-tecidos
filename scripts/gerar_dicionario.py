"""Gera docs/dicionario_dados.md a partir do banco carregado + descrições abaixo.

Uso: python scripts/gerar_dicionario.py
"""
from __future__ import annotations

import os
from pathlib import Path

import pymysql

RAIZ = Path(__file__).resolve().parents[1]
CONN = dict(host=os.environ.get("MYSQL_HOST", "127.0.0.1"), port=int(os.environ.get("MYSQL_PORT", "3336")),
            user=os.environ.get("MYSQL_USER", "analista"), password=os.environ.get("MYSQL_PASSWORD", "analista123"),
            database="tecidos")

# tabela: (domínio, grão, descrição, {coluna: descrição})
D = {
    "categorias": ("Catálogo", "1 linha por categoria", "Árvore de 2 níveis: família de fibra (Algodão, Linho, Viscose, Malha, Sintéticos, Jeans) e subcategoria.", {
        "categoria_id": "Identificador. Famílias usam 1-6; subcategorias 100+.",
        "categoria_pai_id": "Família à qual a subcategoria pertence. Nulo nas famílias.",
        "nome": "Nome exibido na loja.", "slug": "Trecho de URL da categoria (/categoria/<slug>)."}),
    "fornecedores": ("Catálogo", "1 linha por fornecedor", "Tecelagens e distribuidoras (fictícias).", {
        "fornecedor_id": "Identificador.", "razao_social": "Razão social fictícia.", "nome_fantasia": "Nome comercial.",
        "cnpj": "CNPJ sintético (dígitos verificadores válidos, gerado pelo Faker).", "uf": "UF da sede.", "cidade": "Cidade da sede.",
        "prazo_reposicao_dias": "Prazo médio de entrega de reposição.",
        "confiabilidade": "Probabilidade de entregar no prazo. Fornecedores com valor baixo causam rupturas (ex.: chita no São João).",
        "ativo": "1 = fornecedor ativo."}),
    "produtos": ("Catálogo", "1 linha por artigo de tecido", "Artigo (ex.: 'Linho Misto Liso Coleção Natural'). Cor, estampa e formato ficam nas variantes.", {
        "produto_id": "Identificador.", "sku_base": "Prefixo de SKU do artigo.", "nome": "Nome do artigo.",
        "categoria_id": "Subcategoria (FK categorias).", "fornecedor_id": "Fornecedor principal.",
        "composicao": "Composição da fibra (ex.: 55% linho 45% viscose).", "largura_cm": "Largura útil do tecido em cm.",
        "descricao": "Texto da vitrine. Nulo em ~12% (imperfeição: cadastro incompleto).",
        "lancado_em": "Data de lançamento na loja.", "ativo": "0 = descontinuado durante o período."}),
    "variantes": ("Catálogo", "1 linha por SKU", "SKU vendável: cor x estampa x formato. Venda por metro (múltiplos de 0,5 m) ou por rolo (25 m malha, 50 m planos).", {
        "variante_id": "Identificador.", "produto_id": "Artigo.", "sku": "Código do SKU; sufixo -R indica rolo.",
        "cor": "Cor predominante. 'Colorido' em estampas multicoloridas.", "estampa": "'Liso' quando não há estampa.",
        "gramatura_gm2": "Gramatura em g/m². Nula em ~4% (imperfeição).", "formato_venda": "metro ou rolo.",
        "metros_por_unidade": "1 para venda por metro; tamanho do rolo em metros.",
        "preco_atual": "Preço de tabela vigente no fim do período (por unidade de venda).", "custo_atual": "Custo vigente no fim do período.",
        "ativo": "0 = fora de linha.", "criado_em": "Data de criação do SKU."}),
    "historico_precos": ("Catálogo", "1 linha por período de preço de um SKU (SCD tipo 2)", "Mudanças de preço de tabela, promoção e custo ao longo do tempo.", {
        "historico_preco_id": "Identificador.", "variante_id": "SKU.", "preco": "Preço de tabela no período.",
        "preco_promocional": "Preço promocional (nulo = sem promoção).", "custo": "Custo de compra no período.",
        "vigente_de": "Início da vigência.", "vigente_ate": "Fim da vigência (nulo = vigente hoje).",
        "motivo": "lancamento, reajuste_fornecedor, promocao, fim_promocao ou queima_estoque."}),
    "estoque": ("Estoque", "1 linha por SKU", "Posição de estoque no fim do período.", {
        "variante_id": "SKU.", "saldo_unidades": "Saldo em metros (formato metro) ou rolos (formato rolo).",
        "ponto_reposicao": "Saldo que dispara pedido ao fornecedor.", "lote_reposicao": "Quantidade típica do pedido de compra.",
        "atualizado_em": "Momento do snapshot."}),
    "estoque_diario": ("Estoque", "1 linha por SKU e dia em que o SKU existia", "Fechamento diário de estoque. Base para estudar ruptura e demanda censurada.", {
        "variante_id": "SKU.", "data": "Dia (horário local).", "saldo_inicial": "Saldo na abertura do dia (após chegadas de reposição).",
        "entradas": "Entradas de compra no dia.", "saidas": "Vendas pagas no dia.", "saldo_final": "saldo_inicial + entradas - saidas.",
        "em_ruptura": "1 = o SKU zerou em algum momento do dia ou recusou venda por falta de saldo.",
        "demanda_perdida": "Unidades que clientes tentaram comprar sem estoque (não viraram venda)."}),
    "movimentacoes_estoque": ("Estoque", "1 linha por movimento", "Kardex: compras, vendas, devoluções, ajustes de inventário e avarias.", {
        "movimentacao_id": "Identificador (ordem cronológica).", "variante_id": "SKU.",
        "tipo": "entrada_compra, saida_venda, entrada_devolucao, ajuste_inventario ou perda_avaria.",
        "quantidade": "Positiva = entrada; negativa = saída. Unidade de venda do SKU.", "ocorrido_em": "Momento (horário local).",
        "pedido_id": "Pedido relacionado (vendas e devoluções).", "devolucao_id": "Devolução relacionada.",
        "fornecedor_id": "Fornecedor (entradas de compra)."}),
    "clientes": ("Clientes", "1 linha por conta de cliente", "Dados pessoais 100% sintéticos. E-mails só em domínios reservados (example.com, *.example, *.test).", {
        "cliente_id": "Identificador.", "tipo_cliente": "hobby, costureira, atelie ou confeccao (autodeclarado).",
        "tipo_pessoa": "PF ou PJ.", "nome": "Nome fictício.", "razao_social": "Razão social (PJ).",
        "email": "E-mail fictício. ~1,5% com maiúsculas ou espaço à esquerda (imperfeição).",
        "telefone": "Celular fictício com DDD da UF. Formatos inconsistentes e ~17% nulo (imperfeição).",
        "cpf": "CPF sintético. Repetido em ~0,6% das contas: mesma pessoa com dois cadastros (imperfeição).",
        "cnpj": "CNPJ sintético (PJ).", "data_nascimento": "Nula em ~45%.", "genero": "F, M ou O. Nulo em ~60%.",
        "cadastrado_em": "Data de cadastro (horário local).",
        "origem_cadastro": "checkout, newsletter, whatsapp ou importacao_legado (base trazida da plataforma anterior; a 1ª compra no período não é a 1ª de verdade).",
        "aceita_email_marketing": "Opt-in de e-mail (LGPD).", "aceita_whatsapp": "Opt-in de WhatsApp."}),
    "enderecos": ("Clientes", "1 linha por endereço", "Endereços de entrega e cobrança.", {
        "endereco_id": "Identificador.", "cliente_id": "Cliente.", "tipo": "entrega ou cobranca.", "destinatario": "Nome do destinatário.",
        "cep": "CEP coerente com a UF; ~12% sem hífen (imperfeição).", "logradouro": "Rua fictícia.", "numero": "Número.",
        "complemento": "Nulo em ~55%.", "bairro": "Bairro fictício.",
        "cidade": "Cidade real da UF; ~6% sem acento ou em maiúsculas (imperfeição).", "uf": "UF.",
        "principal": "1 = endereço principal.", "criado_em": "Data de criação."}),
    "cupons": ("Pedidos", "1 linha por cupom", "Cupons de desconto (sazonais, primeira compra, criadoras de conteúdo fictícias, e-mail, WhatsApp, atacado).", {
        "cupom_id": "Identificador.", "codigo": "Código digitado no checkout.", "descricao": "Descrição interna.",
        "tipo_desconto": "percentual, valor_fixo ou frete_gratis.", "valor_desconto": "% ou R$, conforme o tipo.",
        "pedido_minimo": "Subtotal mínimo.", "canal": "Origem do cupom.", "valido_de": "Início da validade.",
        "valido_ate": "Fim da validade (nulo = sem fim).", "limite_usos": "Limite de usos (nulo = ilimitado)."}),
    "pedidos": ("Pedidos", "1 linha por pedido", "Pedidos da loja. Valores em R$. Horário local (America/Sao_Paulo).", {
        "pedido_id": "Identificador.", "numero_pedido": "Número exibido ao cliente; vira transaction_id no tracking.",
        "cliente_id": "Cliente.", "endereco_entrega_id": "Endereço de entrega. Nulo = retirada na loja.",
        "sessao_id": "Sessão em que a compra aconteceu. Nulo = sem rastreio (adblock, navegador sem JS, pedido via WhatsApp).",
        "cupom_id": "Cupom aplicado.", "canal_venda": "site ou whatsapp (pedido montado pelo atendimento).",
        "status": "aguardando_pagamento, pago, enviado, entregue, cancelado ou devolvido. Receita = pago, enviado, entregue e devolvido.",
        "criado_em": "Criação do pedido (local).", "pago_em": "Aprovação do pagamento.", "cancelado_em": "Cancelamento (pagamento recusado/expirado, estorno).",
        "subtotal": "Soma dos itens.", "desconto": "Desconto de cupom.", "frete": "Frete cobrado do cliente (0 = grátis).",
        "total": "subtotal - desconto + frete (garantido por CHECK).",
        "pedido_teste": "1 = pedido de teste da equipe (excluir das análises; alguns aparecem como pagos)."}),
    "itens_pedido": ("Pedidos", "1 linha por SKU no pedido", "Itens comprados.", {
        "item_pedido_id": "Identificador.", "pedido_id": "Pedido.", "variante_id": "SKU.",
        "quantidade": "Metros (formato metro) ou rolos.", "preco_unitario": "Preço praticado (com promoção de vitrine).",
        "preco_tabela": "Preço de tabela no dia.", "custo_unitario": "Custo no dia.", "total_item": "quantidade x preco_unitario."}),
    "pagamentos": ("Pedidos", "1 linha por tentativa de pagamento", "Tentativas de pagamento: cartão recusado seguido de nova tentativa gera 2 linhas.", {
        "pagamento_id": "Identificador.", "pedido_id": "Pedido.", "tentativa": "Ordem da tentativa.",
        "metodo": "pix, cartao_credito ou boleto.", "bandeira": "Bandeira do cartão (nula em ~6% dos cartões).",
        "parcelas": "1 a 12 (só cartão parcela).", "valor": "Valor cobrado.",
        "status": "aprovado, recusado, pendente, expirado ou estornado.", "gateway": "Gateway de pagamento.",
        "transacao_gateway": "ID da transação no gateway.", "criado_em": "Criação (local).", "atualizado_em": "Última atualização de status."}),
    "fretes": ("Pedidos", "1 linha por pedido", "Envio do pedido.", {
        "frete_id": "Identificador.", "pedido_id": "Pedido.", "transportadora": "Correios, Jadlog, Loggi ou Retirada na loja.",
        "servico": "PAC, SEDEX, Jadlog .Package, Loggi Expresso ou Retirada.", "peso_kg": "Peso estimado (metros x gramatura x largura).",
        "valor_cobrado": "Frete cobrado do cliente.", "custo_real": "Custo pago à transportadora.",
        "frete_gratis": "1 = frete grátis (política por região e valor; limite subiu em mar/2025).",
        "prazo_estimado_dias": "Prazo prometido.", "postado_em": "Postagem.",
        "entregue_em": "Entrega. Nulo em ~2% de pedidos entregues (imperfeição: rastreio sem baixa).",
        "codigo_rastreio": "Código de rastreio fictício."}),
    "devolucoes": ("Pedidos", "1 linha por item devolvido", "Trocas e devoluções.", {
        "devolucao_id": "Identificador.", "pedido_id": "Pedido.", "item_pedido_id": "Item devolvido.", "motivo": "Motivo informado.",
        "quantidade": "Quantidade devolvida.", "valor_reembolsado": "Reembolso (0 se recusada).",
        "status": "solicitada, aprovada, recusada ou concluida.", "solicitada_em": "Solicitação.", "concluida_em": "Conclusão."}),
    "avaliacoes": ("Pedidos", "1 linha por pedido avaliado", "Avaliações de produto após a entrega.", {
        "avaliacao_id": "Identificador.", "pedido_id": "Pedido.", "cliente_id": "Cliente.", "produto_id": "Produto avaliado.",
        "nota": "1 a 5 (cai com atraso e devolução).", "titulo": "Título (pode ser nulo).", "comentario": "Comentário (pode ser nulo).",
        "criada_em": "Data da avaliação."}),
    "meta_contas": ("Mídia - Meta", "1 linha por conta", "Contas de anúncio.", {
        "conta_id": "ID da conta (act_...).", "nome": "Nome.", "moeda": "BRL.", "fuso_horario": "Fuso das métricas diárias."}),
    "meta_campanhas": ("Mídia - Meta", "1 linha por campanha", "Campanhas: prospecção, Advantage+, remarketing, catálogo, sazonais e testes.", {
        "campanha_id": "ID da campanha (18 dígitos; use BIGINT, não float).", "conta_id": "Conta.", "nome": "Nome com prefixo [PROSP], [RMKT], [SAZ] ou [TESTE].",
        "objetivo": "Objetivo ODAX.", "estrategia": "Classificação interna da campanha.", "status": "ACTIVE, PAUSED ou ARCHIVED.",
        "orcamento_diario": "Orçamento de campanha (CBO); nulo quando o orçamento fica no conjunto.",
        "inicio": "Início.", "fim": "Fim (nulo = ativa)."}),
    "meta_conjuntos": ("Mídia - Meta", "1 linha por conjunto de anúncios", "Públicos e otimização.", {
        "conjunto_id": "ID.", "campanha_id": "Campanha.", "nome": "Nome.", "publico": "Descrição do público.",
        "otimizacao": "Evento de otimização.", "posicionamentos": "Posicionamentos.", "status": "Status."}),
    "meta_anuncios": ("Mídia - Meta", "1 linha por anúncio", "Criativos. Anúncios entram e saem ao longo do tempo (renovação criativa e fadiga).", {
        "anuncio_id": "ID.", "conjunto_id": "Conjunto.", "nome": "Nome.", "formato": "imagem, video, carrossel, catalogo ou reels.",
        "tema_criativo": "Tema do criativo.", "url_destino": "URL com template de UTMs.", "status": "Status."}),
    "meta_metricas_diarias": ("Mídia - Meta", "1 linha por anúncio e dia com entrega", "Insights diários como na API de Marketing.", {
        "data": "Dia no fuso da conta.", "anuncio_id": "Anúncio.", "investimento": "Valor gasto (R$).", "impressoes": "Impressões.",
        "alcance": "Pessoas alcançadas no dia.", "cliques_todos": "Todos os cliques.", "cliques_link": "Cliques no link.",
        "visualizacoes_pagina_destino": "Landing page views reportadas.", "adicoes_carrinho": "Add to cart reportados.",
        "compras": "Compras reportadas (7 dias após clique + 1 dia após visualização, inclui modeladas e pedidos depois cancelados).",
        "valor_compras": "Valor das compras reportadas."}),
    "google_contas": ("Mídia - Google", "1 linha por conta", "Contas Google Ads.", {
        "conta_id": "Customer ID.", "nome": "Nome.", "moeda": "BRL.", "fuso_horario": "Fuso."}),
    "google_campanhas": ("Mídia - Google", "1 linha por campanha", "Search (marca, genérica, concorrentes), Shopping, Performance Max e Demand Gen.", {
        "campanha_id": "ID.", "conta_id": "Conta.", "nome": "Nome.", "tipo_canal": "SEARCH, SHOPPING, PERFORMANCE_MAX ou DEMAND_GEN.",
        "estrategia_lance": "Estratégia de lance.", "roas_alvo": "tROAS (quando aplicável).", "campanha_marca": "1 = Search de marca.",
        "orcamento_diario": "Orçamento diário de referência (escala 1).", "status": "ENABLED, PAUSED ou REMOVED.",
        "inicio": "Início.", "fim": "Fim (nulo = ativa)."}),
    "google_grupos_anuncio": ("Mídia - Google", "1 linha por grupo (ou asset group)", "Grupos de anúncios; em PMax representam asset groups.", {
        "grupo_id": "ID.", "campanha_id": "Campanha.", "nome": "Nome.", "tipo": "Tipo de grupo.", "status": "Status."}),
    "google_palavras_chave": ("Mídia - Google", "1 linha por palavra-chave", "Palavras-chave das campanhas Search.", {
        "palavra_chave_id": "ID.", "grupo_id": "Grupo.", "texto": "Palavra-chave.", "tipo_correspondencia": "EXACT, PHRASE ou BROAD.",
        "indice_qualidade": "1-10; nulo quando sem dados suficientes.", "status": "Status."}),
    "google_metricas_diarias": ("Mídia - Google", "1 linha por grupo e dia com entrega", "Métricas diárias por grupo.", {
        "data": "Dia no fuso da conta.", "grupo_id": "Grupo.", "investimento": "Custo (R$).", "impressoes": "Impressões.",
        "cliques": "Cliques.", "conversoes": "Conversões reportadas (fracionadas, modelo da plataforma, janela 30 dias, por data do clique; inclui engaged-view em PMax/Demand Gen).",
        "valor_conversao": "Valor reportado.", "parcela_impressoes": "Search impression share (só Search)."}),
    "google_palavras_chave_metricas_diarias": ("Mídia - Google", "1 linha por palavra-chave e dia", "Métricas diárias de palavras-chave (Search). A soma de investimento bate com o grupo.", {
        "data": "Dia.", "palavra_chave_id": "Palavra-chave.", "investimento": "Custo.", "impressoes": "Impressões.", "cliques": "Cliques.",
        "conversoes": "Conversões atribuídas a cliques da palavra (o grupo pode ter mais, vindas de PMax/engaged-view).",
        "valor_conversao": "Valor."}),
    "cliques_midia": ("Tracking", "1 linha por click id capturado na entrada do site", "Elo entre a plataforma de mídia e a sessão. Plataformas reportam mais cliques do que chegam aqui (perda entre clique e carregamento).", {
        "clique_id": "Identificador.", "plataforma": "meta ou google.", "click_id": "fbclid ou gclid.",
        "meta_anuncio_id": "Anúncio Meta.", "google_grupo_id": "Grupo Google.", "google_palavra_chave_id": "Palavra-chave (Search).",
        "clicado_em": "Momento do clique (UTC)."}),
    "sessoes": ("Tracking", "1 linha por sessão", "Sessões reconstruídas pelo GTM server-side (padrão GA4). Horário em UTC.", {
        "sessao_id": "Identificador.", "ga_session_id": "ID de sessão GA4 (timestamp unix do início).",
        "client_id": "Cookie _ga. Nulo quando analytics_storage foi negado (cookieless ping).",
        "cliente_id": "user_id: cliente logado/identificado na sessão.", "iniciada_em": "Início (UTC).", "duracao_seg": "Duração.",
        "dispositivo": "mobile, desktop ou tablet (nulo em ~1%).", "sistema_operacional": "SO.", "navegador": "Navegador; inclui navegadores in-app (Instagram/Facebook).",
        "uf": "UF por IP (nula em ~7%).", "landing_page": "URL de entrada.", "referrer": "Página de origem.",
        "utm_source": "Origem. Grafias inconsistentes (ig, IG, Instagram, instagram).", "utm_medium": "Meio (paid_social, paid, cpc, Social, email...).",
        "utm_campaign": "Campanha: nome antes de jun/2024, ID da campanha depois (troca de template).", "utm_content": "ID do anúncio (Meta).",
        "utm_term": "ID do conjunto (Meta) ou palavra-chave (Google com UTM manual).",
        "gclid": "Google click id (auto-tagging).", "fbclid": "Meta click id. Ausente em ~12% das sessões vindas de anúncio Meta (imperfeição).",
        "fbp": "Cookie _fbp (só com ad_storage concedido).", "fbc": "Cookie _fbc derivado do fbclid.",
        "clique_id": "Clique de mídia que originou a sessão.",
        "consent_analytics_storage": "Consent Mode v2.", "consent_ad_storage": "Consent Mode v2.",
        "consent_ad_user_data": "Consent Mode v2 (envio de dados do usuário para anúncios).",
        "consent_ad_personalization": "Consent Mode v2 (personalização).",
        "primeira_visita": "1 = primeira visita do client_id.", "engajada": "Critério GA4: >10 s, 2+ page views ou conversão."}),
    "eventos": ("Tracking", "1 linha por hit recebido pelo servidor (há duplicatas)", "Log de eventos GA4 do GTM server-side: page_view, view_item, add_to_cart, begin_checkout, add_payment_info, purchase.", {
        "evento_id": "Chave surrogate da linha.",
        "event_id": "ID de deduplicação. O purchase chega do navegador e do backend com o mesmo event_id; retries de rede repetem o event_id.",
        "sessao_id": "Sessão.", "cliente_id": "user_id no momento do evento (em compras de cliente novo, só a partir do checkout).",
        "event_name": "Nome do evento GA4.",
        "event_timestamp": "Momento em UTC, EXCETO versao_container = 'v2.3' (01/03 a 15/06/2024), gravado em horário local (UTC-3). Imperfeição documentada.",
        "page_location": "URL da página.", "variante_id": "Item do evento (view_item, add_to_cart).", "quantidade": "Quantidade do item.",
        "valor": "value do evento (R$).", "moeda": "currency.", "transaction_id": "numero_pedido (purchase). Recargas da página de obrigado repetem o transaction_id com event_id novo.",
        "pedido_id": "Pedido (purchase).", "fonte": "web = tag no navegador; server = webhook do backend.",
        "versao_container": "Versão do container sGTM (v2.1, v2.3, v2.4, v3.0, v3.1)."}),
    "envios_conversao": ("Tracking", "1 linha por envio a uma plataforma", "Log dos envios server-side: Meta Conversions API (add_to_cart, begin_checkout, add_payment_info, purchase) e Google Ads Enhanced Conversions (purchase).", {
        "envio_id": "Identificador.", "evento_id": "Evento enviado.", "plataforma": "meta_capi ou google_ads_ec.",
        "status": "enviado, erro, bloqueado_consentimento ou deduplicado.", "http_status": "Resposta HTTP. 401 = token expirado (incidente de 14 a 17/07/2025).",
        "enviado_em": "Envio (UTC).", "email_hash_enviado": "1 = e-mail com SHA-256 enviado.", "telefone_hash_enviado": "1 = telefone com hash enviado.",
        "fbp_enviado": "1 = _fbp enviado.", "fbc_enviado": "1 = _fbc enviado.", "gclid_enviado": "1 = gclid enviado.",
        "event_match_quality": "EMQ estimado da Meta (0-10).", "mensagem_erro": "Mensagem de erro."}),
    "atribuicoes": ("Atribuição", "1 linha por pedido x modelo x toque", "Crédito de cada sessão (toque) na jornada de até 30 dias antes da compra. Só pedidos rastreados.", {
        "atribuicao_id": "Identificador.", "pedido_id": "Pedido.",
        "modelo": "last_click (último clique não direto), first_click, linear ou data_driven (simplificado: lift do canal x decaimento de 7 dias x bônus de primeiro/último toque).",
        "sessao_id": "Sessão (toque).", "posicao": "Ordem do toque (1 = primeiro).", "total_toques": "Toques na jornada.",
        "canal": "Agrupamento de canais padrão pelo que é observável na sessão.",
        "meta_campanha_id": "Campanha Meta do toque (quando o clique foi capturado).", "google_campanha_id": "Campanha Google do toque.",
        "peso": "Crédito do toque (soma 1 por pedido e modelo).", "receita_atribuida": "peso x total do pedido."}),
}


def main():
    con = pymysql.connect(**CONN)
    cur = con.cursor()
    cur.execute("""SELECT c.table_name, c.column_name, c.column_type, c.is_nullable, c.column_key,
                          k.referenced_table_name, k.referenced_column_name
                   FROM information_schema.columns c
                   LEFT JOIN information_schema.key_column_usage k
                     ON k.table_schema = c.table_schema AND k.table_name = c.table_name AND k.column_name = c.column_name
                    AND k.referenced_table_name IS NOT NULL
                   WHERE c.table_schema = 'tecidos' AND c.table_name NOT LIKE '\\_%'
                   ORDER BY c.table_name, c.ordinal_position""")
    cols: dict[str, list] = {}
    for t, c, tipo, nulo, chave, rt, rc in cur.fetchall():
        cols.setdefault(t, []).append((c, tipo, nulo, chave, rt, rc))

    linhas = ["# Dicionário de dados", "",
              "Banco `tecidos` (MySQL 8.4). Gerado por `scripts/gerar_dicionario.py` a partir do banco carregado: "
              "tipos, chaves e % de nulos são lidos do MySQL. Imperfeições propositais estão marcadas e explicadas em "
              "[imperfeicoes.md](imperfeicoes.md).", "",
              "**Fusos:** transacional em horário local (America/Sao_Paulo); tracking em UTC; métricas de mídia no fuso da conta.", "",
              "## Índice", ""]
    por_dominio: dict[str, list] = {}
    for t, (dom, *_rest) in D.items():
        por_dominio.setdefault(dom, []).append(t)
    for dom, ts in por_dominio.items():
        linhas.append(f"- **{dom}:** " + ", ".join(f"[{t}](#{t})" for t in ts))
    linhas.append("")

    for t, (dom, grao, desc, cdesc) in D.items():
        cur.execute(f"SELECT COUNT(*) FROM `{t}`")
        n = cur.fetchone()[0]
        amostra = "" if n <= 2_000_000 else f" WHERE MOD(`{cols[t][0][0]}`, 20) = 0"
        exprs = ", ".join(f"AVG(`{c}` IS NULL)" for c, _, nulo, *_ in cols[t])
        cur.execute(f"SELECT {exprs} FROM `{t}`{amostra}")
        nulos = cur.fetchone()
        linhas += [f"## {t}", "", f"{desc}", "", f"*Domínio:* {dom} · *Grão:* {grao} · *Linhas:* {n:,}".replace(",", "."), "",
                   "| Coluna | Tipo | Chave | Nulos | Descrição |", "|---|---|---|---|---|"]
        for (c, tipo, nulo, chave, rt, rc), pn in zip(cols[t], nulos):
            k = {"PRI": "PK", "UNI": "UK", "MUL": "índice"}.get(chave, "")
            if rt:
                k = (k + " · " if k and k != "índice" else "") + f"FK → {rt}.{rc}"
            pnull = "—" if nulo == "NO" else f"{float(pn or 0):.1%}".replace(".", ",")
            linhas.append(f"| `{c}` | {tipo} | {k} | {pnull} | {cdesc.get(c, '')} |")
        linhas.append("")
    (RAIZ / "docs" / "dicionario_dados.md").write_text("\n".join(linhas), encoding="utf-8")
    faltando = [(t, c) for t in D for c, *_ in cols.get(t, []) if c not in D[t][3]]
    print("ok; colunas sem descrição:", faltando or "nenhuma")


if __name__ == "__main__":
    main()
