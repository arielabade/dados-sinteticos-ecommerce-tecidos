"""Validação do banco carregado: integridade referencial, regras de negócio e
métricas em faixas plausíveis para o varejo online de tecidos.

Uso:  python scripts/validar.py            (lê MYSQL_HOST/PORT/USER/PASSWORD do ambiente)
Sai com código 1 se alguma verificação obrigatória falhar.
"""
from __future__ import annotations

import os
import sys

import pymysql

CONN = dict(host=os.environ.get("MYSQL_HOST", "127.0.0.1"), port=int(os.environ.get("MYSQL_PORT", "3336")),
            user=os.environ.get("MYSQL_USER", "analista"), password=os.environ.get("MYSQL_PASSWORD", "analista123"),
            database="tecidos")

PAGOS = "('pago','enviado','entregue','devolvido')"

# (descrição, SQL que retorna um número, mínimo, máximo)
FAIXAS = [
    ("Ticket médio (R$) dos pedidos pagos",
     f"SELECT AVG(total) FROM pedidos WHERE status IN {PAGOS} AND pedido_teste = 0", 180, 380),
    ("Taxa de conversão: pedidos pagos rastreados / sessões",
     f"SELECT (SELECT COUNT(*) FROM pedidos WHERE status IN {PAGOS} AND sessao_id IS NOT NULL) / (SELECT COUNT(*) FROM sessoes)",
     0.012, 0.035),
    ("Taxa de adição ao carrinho (sessões com add_to_cart / sessões)",
     "SELECT COUNT(DISTINCT sessao_id) / (SELECT COUNT(*) FROM sessoes) FROM eventos WHERE event_name = 'add_to_cart'",
     0.05, 0.15),
    ("Taxa de cancelamento", "SELECT AVG(status = 'cancelado') FROM pedidos WHERE pedido_teste = 0", 0.03, 0.12),
    ("Taxa de devolução (pedidos entregues com devolução)",
     "SELECT COUNT(DISTINCT d.pedido_id) / (SELECT COUNT(*) FROM pedidos WHERE status IN ('entregue','devolvido')) FROM devolucoes d",
     0.01, 0.05),
    ("MER (receita paga / investimento total)",
     f"""SELECT (SELECT SUM(total) FROM pedidos WHERE status IN {PAGOS} AND pedido_teste = 0) /
               ((SELECT SUM(investimento) FROM meta_metricas_diarias) + (SELECT SUM(investimento) FROM google_metricas_diarias))""",
     5, 14),
    ("ROAS reportado pela Meta", "SELECT SUM(valor_compras) / SUM(investimento) FROM meta_metricas_diarias", 2.5, 9),
    ("ROAS reportado pelo Google", "SELECT SUM(valor_conversao) / SUM(investimento) FROM google_metricas_diarias", 3, 12),
    ("CPC médio Meta (R$, clique no link)", "SELECT SUM(investimento) / SUM(cliques_link) FROM meta_metricas_diarias", 0.6, 3.0),
    ("CPC médio Google (R$)", "SELECT SUM(investimento) / SUM(cliques) FROM google_metricas_diarias", 0.4, 2.5),
    ("CTR Meta (link)", "SELECT SUM(cliques_link) / SUM(impressoes) FROM meta_metricas_diarias", 0.006, 0.025),
    ("Participação mobile nas sessões", "SELECT AVG(dispositivo = 'mobile') FROM sessoes WHERE dispositivo IS NOT NULL", 0.75, 0.95),
    ("Pedidos com frete grátis", "SELECT AVG(frete_gratis) FROM fretes", 0.3, 0.7),
    ("Participação do Pix nos pagamentos aprovados",
     "SELECT AVG(metodo = 'pix') FROM pagamentos WHERE status = 'aprovado'", 0.25, 0.5),
    ("Conversões reportadas (Meta + Google) / pedidos reais",
     """SELECT ((SELECT SUM(compras) FROM meta_metricas_diarias) + (SELECT SUM(conversoes) FROM google_metricas_diarias))
               / (SELECT COUNT(*) FROM pedidos WHERE pedido_teste = 0)""", 0.4, 1.3),
    ("SKU-dias em ruptura", "SELECT AVG(em_ruptura) FROM estoque_diario", 0.01, 0.15),
    ("Clientes com 2+ pedidos", "SELECT AVG(n >= 2) FROM (SELECT COUNT(*) n FROM pedidos GROUP BY cliente_id) x", 0.25, 0.65),
]

# Regras que devem retornar 0 linhas problemáticas
REGRAS = [
    ("Total do pedido = subtotal - desconto + frete",
     "SELECT COUNT(*) FROM pedidos WHERE total <> subtotal - desconto + frete"),
    ("Subtotal = soma dos itens (pedidos reais)",
     """SELECT COUNT(*) FROM pedidos p JOIN (SELECT pedido_id, SUM(total_item) s FROM itens_pedido GROUP BY pedido_id) i
        USING (pedido_id) WHERE ABS(p.subtotal - i.s) > 0.01"""),
    ("Todo pedido tem frete e ao menos um pagamento",
     """SELECT COUNT(*) FROM pedidos p WHERE NOT EXISTS (SELECT 1 FROM fretes f WHERE f.pedido_id = p.pedido_id)
        OR NOT EXISTS (SELECT 1 FROM pagamentos g WHERE g.pedido_id = p.pedido_id)"""),
    ("Pedido pago tem pagamento aprovado",
     f"""SELECT COUNT(*) FROM pedidos p WHERE p.status IN {PAGOS} AND NOT EXISTS
        (SELECT 1 FROM pagamentos g WHERE g.pedido_id = p.pedido_id AND g.status IN ('aprovado','estornado'))"""),
    ("Soma dos pesos de atribuição = 1 por pedido e modelo",
     "SELECT COUNT(*) FROM (SELECT pedido_id, modelo, SUM(peso) s FROM atribuicoes GROUP BY 1, 2) x WHERE ABS(s - 1) > 0.0001"),
    ("Evento purchase aponta para o pedido da sessão",
     """SELECT COUNT(*) FROM eventos e JOIN pedidos p ON p.pedido_id = e.pedido_id
        WHERE e.event_name = 'purchase' AND p.sessao_id <> e.sessao_id"""),
    ("Clique da sessão é da plataforma do click id",
     """SELECT COUNT(*) FROM sessoes s JOIN cliques_midia c USING (clique_id)
        WHERE (c.plataforma = 'google' AND s.gclid <> c.click_id) OR (c.plataforma = 'meta' AND s.fbclid <> c.click_id)"""),
    ("Palavras-chave somam no máximo o investimento do grupo",
     """SELECT COUNT(*) FROM (SELECT k.data, g.grupo_id, SUM(k.investimento) s FROM google_palavras_chave_metricas_diarias k
        JOIN google_palavras_chave g USING (palavra_chave_id) GROUP BY 1, 2) x
        JOIN google_metricas_diarias m ON m.data = x.data AND m.grupo_id = x.grupo_id WHERE x.s > m.investimento + 0.05"""),
    ("Saldo final = inicial + entradas - saídas (estoque diário)",
     "SELECT COUNT(*) FROM estoque_diario WHERE ABS(saldo_final - (saldo_inicial + entradas - saidas)) > 0.02"),
]

# Imperfeições propositais: devem EXISTIR (documentadas em docs/imperfeicoes.md)
IMPERFEICOES = [
    ("event_id duplicado (mesmo evento recebido 2x)",
     "SELECT COUNT(*) FROM (SELECT event_id FROM eventos GROUP BY event_id HAVING COUNT(*) > 1) x"),
    ("purchase recarregado (mesmo transaction_id, event_id diferente)",
     """SELECT COUNT(*) FROM (SELECT transaction_id FROM eventos WHERE event_name = 'purchase'
        GROUP BY transaction_id HAVING COUNT(DISTINCT event_id) > 1) x"""),
    ("Eventos gravados em horário local (container v2.3)", "SELECT COUNT(*) FROM eventos WHERE versao_container = 'v2.3'"),
    ("Sessões sem UTM, click id nem referrer (Direct/sem atribuição)",
     "SELECT COUNT(*) FROM sessoes WHERE utm_source IS NULL AND gclid IS NULL AND fbclid IS NULL AND referrer IS NULL"),
    ("Pedidos sem sessão rastreada", "SELECT COUNT(*) FROM pedidos WHERE sessao_id IS NULL AND pedido_teste = 0"),
    ("Pedidos de teste", "SELECT COUNT(*) FROM pedidos WHERE pedido_teste = 1"),
    ("Clientes com CPF repetido (contas duplicadas)",
     "SELECT COUNT(*) FROM (SELECT cpf FROM clientes WHERE cpf IS NOT NULL GROUP BY cpf HAVING COUNT(*) > 1) x"),
    ("Telefones nulos", "SELECT COUNT(*) FROM clientes WHERE telefone IS NULL"),
    ("Variantes sem gramatura", "SELECT COUNT(*) FROM variantes WHERE gramatura_gm2 IS NULL"),
    ("Envios CAPI com erro 401 (incidente jul/2025)", "SELECT COUNT(*) FROM envios_conversao WHERE http_status = 401"),
    ("utm_source com grafias diferentes para Instagram",
     "SELECT COUNT(DISTINCT utm_source) FROM sessoes WHERE LOWER(utm_source) IN ('ig','instagram')"),
]


def main() -> int:
    con = pymysql.connect(**CONN)
    cur = con.cursor()
    falhas = 0

    def um(sql):
        cur.execute(sql)
        return cur.fetchone()[0]

    print("== Contagem de linhas")
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'tecidos' "
                "AND table_name NOT LIKE '\\_%' ORDER BY table_name")
    for (t,) in cur.fetchall():
        print(f"  {t:<42} {um(f'SELECT COUNT(*) FROM `{t}`'):>12,}")

    print("\n== Integridade referencial (registros órfãos por FK)")
    cur.execute("""SELECT table_name, column_name, referenced_table_name, referenced_column_name, constraint_name
                   FROM information_schema.key_column_usage
                   WHERE table_schema = 'tecidos' AND referenced_table_name IS NOT NULL ORDER BY table_name""")
    for t, c, rt, rc, nome in cur.fetchall():
        n = um(f"SELECT COUNT(*) FROM `{t}` x LEFT JOIN `{rt}` r ON r.`{rc}` = x.`{c}` "
               f"WHERE x.`{c}` IS NOT NULL AND r.`{rc}` IS NULL")
        ok = n == 0
        falhas += not ok
        print(f"  [{'ok' if ok else 'FALHA'}] {t}.{c} -> {rt}.{rc}: {n} órfãos")

    print("\n== Regras de negócio (devem ser 0)")
    for desc, sql in REGRAS:
        n = um(sql)
        falhas += n != 0
        print(f"  [{'ok' if n == 0 else 'FALHA'}] {desc}: {n}")

    print("\n== Métricas em faixas plausíveis")
    for desc, sql, lo, hi in FAIXAS:
        v = float(um(sql) or 0)
        ok = lo <= v <= hi
        falhas += not ok
        print(f"  [{'ok' if ok else 'FALHA'}] {desc}: {v:,.4f} (faixa {lo}–{hi})")

    print("\n== Imperfeições propositais (devem existir)")
    for desc, sql in IMPERFEICOES:
        n = um(sql)
        ok = n > 0
        falhas += not ok
        print(f"  [{'ok' if ok else 'FALHA'}] {desc}: {n:,}")

    print(f"\n{'TUDO OK' if falhas == 0 else f'{falhas} verificação(ões) falharam'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
