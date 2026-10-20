"""Generates the entity-relationship diagrams in docs/diagramas/*.svg from schema.sql.

Why not Mermaid: Mermaid's automatic layout gives no control over positions, and the single
diagram crossed lines. Here each area of the database becomes a small diagram, with tables on a
fixed grid and orthogonal connectors, following UML/ER diagramming guidelines:

- no line crosses another and none goes through a table (checked in `validar`, which stops the
  build if it finds a crossing);
- horizontal and vertical segments only, each relationship with its own path;
- parent above or to the left of the child, read top-down and left-to-right;
- the large model split into areas of 5 to 13 tables, with white space;
- crow's foot notation at the ends, no arrows (a relationship goes both ways);
- a table from another area appears dashed, name only, to show the link without repeating it.

PK, FK, UK, types and nullability come from schema.sql; the list of attributes shown is curated
(the full table is in docs/dicionario_dados.md).

Usage: python scripts/gerar_diagramas.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "docs" / "diagramas"

# --------------------------------------------------------------------------- schema
ATRIBUTOS = {
    "categorias": ["categoria_id", "categoria_pai_id", "nome", "slug"],
    "fornecedores": ["fornecedor_id", "razao_social", "cnpj", "uf", "prazo_reposicao_dias", "confiabilidade"],
    "produtos": ["produto_id", "sku_base", "nome", "categoria_id", "fornecedor_id", "composicao", "largura_cm"],
    "variantes": ["variante_id", "produto_id", "sku", "cor", "estampa", "formato_venda", "preco_atual", "custo_atual"],
    "historico_precos": ["historico_preco_id", "variante_id", "preco", "preco_promocional", "custo", "vigente_de", "vigente_ate"],
    "estoque": ["variante_id", "saldo_unidades", "ponto_reposicao", "lote_reposicao"],
    "estoque_diario": ["variante_id", "data", "saldo_final", "em_ruptura", "demanda_perdida"],
    "movimentacoes_estoque": ["movimentacao_id", "variante_id", "tipo", "quantidade", "ocorrido_em", "pedido_id", "devolucao_id", "fornecedor_id"],
    "clientes": ["cliente_id", "tipo_cliente", "tipo_pessoa", "nome", "email", "cpf", "cadastrado_em"],
    "enderecos": ["endereco_id", "cliente_id", "cep", "cidade", "uf", "principal"],
    "cupons": ["cupom_id", "codigo", "tipo_desconto", "valor_desconto", "canal"],
    "pedidos": ["pedido_id", "cliente_id", "endereco_entrega_id", "sessao_id", "cupom_id", "status", "criado_em", "total", "pedido_teste"],
    "itens_pedido": ["item_pedido_id", "pedido_id", "variante_id", "quantidade", "preco_unitario", "total_item"],
    "pagamentos": ["pagamento_id", "pedido_id", "tentativa", "metodo", "status"],
    "fretes": ["frete_id", "pedido_id", "transportadora", "custo_real", "frete_gratis", "entregue_em"],
    "devolucoes": ["devolucao_id", "pedido_id", "item_pedido_id", "motivo", "valor_reembolsado"],
    "avaliacoes": ["avaliacao_id", "pedido_id", "cliente_id", "produto_id", "nota"],
    "cliques_midia": ["clique_id", "plataforma", "click_id", "meta_anuncio_id", "google_grupo_id", "google_palavra_chave_id", "clicado_em"],
    "sessoes": ["sessao_id", "cliente_id", "clique_id", "iniciada_em", "dispositivo", "utm_source", "utm_medium", "utm_campaign", "gclid", "fbclid", "consent_ad_storage"],
    "eventos": ["evento_id", "event_id", "sessao_id", "cliente_id", "variante_id", "pedido_id", "event_name", "event_timestamp", "fonte", "versao_container"],
    "envios_conversao": ["envio_id", "evento_id", "plataforma", "status", "http_status", "event_match_quality"],
    "atribuicoes": ["atribuicao_id", "pedido_id", "sessao_id", "meta_campanha_id", "google_campanha_id", "modelo", "canal", "peso", "receita_atribuida"],
    "meta_contas": ["conta_id", "nome", "fuso_horario"],
    "meta_campanhas": ["campanha_id", "conta_id", "nome", "objetivo", "estrategia", "status"],
    "meta_conjuntos": ["conjunto_id", "campanha_id", "publico", "otimizacao"],
    "meta_anuncios": ["anuncio_id", "conjunto_id", "formato", "tema_criativo"],
    "meta_metricas_diarias": ["data", "anuncio_id", "investimento", "impressoes", "alcance", "cliques_link", "compras", "valor_compras"],
    "google_contas": ["conta_id", "nome", "fuso_horario"],
    "google_campanhas": ["campanha_id", "conta_id", "tipo_canal", "estrategia_lance", "campanha_marca"],
    "google_grupos_anuncio": ["grupo_id", "campanha_id", "tipo"],
    "google_palavras_chave": ["palavra_chave_id", "grupo_id", "texto", "tipo_correspondencia"],
    "google_metricas_diarias": ["data", "grupo_id", "investimento", "impressoes", "cliques", "conversoes", "parcela_impressoes"],
    "google_palavras_chave_metricas_diarias": ["data", "palavra_chave_id", "investimento", "cliques", "conversoes"],
    "canais_midia": ["canal_id", "canal", "canal_mmm", "plataforma"],
    "regioes": ["uf", "nome", "macrorregiao", "entrega_disponivel"],
    "midia_regional_diaria": ["data", "canal_id", "uf", "investimento", "impressoes", "cliques"],
    "calendario_comercial": ["data", "feriado_nacional", "evento_comercial", "promocao_loja"],
    "testes_geo": ["teste_id", "canal_id", "tipo_mudanca", "inicio", "fim"],
    "testes_geo_regioes": ["teste_id", "uf", "grupo"],
    "tiktok_campanhas": ["campanha_id", "nome", "objetivo"],
    "tiktok_metricas_diarias": ["data", "campanha_id", "investimento", "cliques", "conversoes"],
    "afiliados_parceiros": ["parceiro_id", "nome", "tipo"],
    "afiliados_metricas_diarias": ["data", "parceiro_id", "investimento", "pedidos_atribuidos"],
    "crm_disparos": ["disparo_id", "data", "tipo_campanha", "entregues", "custo"],
}


@dataclass
class Coluna:
    nome: str
    tipo: str
    nulo: bool
    chaves: list[str] = field(default_factory=list)


def ler_schema() -> dict[str, dict[str, Coluna]]:
    s = (RAIZ / "schema.sql").read_text(encoding="utf-8")
    out: dict[str, dict[str, Coluna]] = {}
    for bloco in re.split(r"\nCREATE TABLE ", s)[1:]:
        nome = bloco.split()[0]
        corpo = bloco[: bloco.find("ENGINE")]
        cols: dict[str, Coluna] = {}
        for linha in corpo.split("\n")[1:]:
            w = linha.strip().split()
            if len(w) >= 2 and re.match(r"^[a-z_0-9]+$", w[0]):
                tipo = re.sub(r"\(.*", "", w[1]).lower()
                cols[w[0]] = Coluna(w[0], tipo, "NOT NULL" not in linha and "PRIMARY" not in linha)
        pk = re.search(r"PRIMARY KEY \(([^)]*)\)", corpo)
        for c in (pk.group(1).replace(" ", "").split(",") if pk else []):
            cols[c].chaves.append("PK")
            cols[c].nulo = False
        for c, _, _ in re.findall(r"FOREIGN KEY\s*\(\s*(\w+)\s*\)\s*REFERENCES\s+(\w+)\s*\(\s*(\w+)\s*\)", corpo):
            cols[c].chaves.append("FK")
        for grupo in re.findall(r"UNIQUE KEY \w+ \(([^)]*)\)", corpo):
            g = grupo.replace(" ", "").split(",")
            if len(g) == 1:
                cols[g[0]].chaves.append("UK")
        out[nome] = cols
    return out


# --------------------------------------------------------------------------- geometry
LARG, CAB, LINHA = 250, 30, 19
GAP_X, GAP_Y, MARGEM, TOPO = 150, 96, 36, 70
FONTE = "Helvetica, Arial, sans-serif"
TINTA, MUDO, LINHA_COR, FUNDO = "#1F2328", "#59636E", "#57606A", "#FFFFFF"


@dataclass
class Caixa:
    nome: str
    col: float
    lin: int
    fantasma: bool = False
    nota: str = ""
    largura: float = LARG
    itens: list = field(default_factory=list)   # area box (overview): list of tables
    x: float = 0
    y: float = 0
    h: float = 0

    @property
    def w(self) -> float:
        return self.largura

    def lado(self, lado: str, f: float) -> tuple[float, float]:
        if lado == "t":
            return self.x + f * self.w, self.y
        if lado == "b":
            return self.x + f * self.w, self.y + self.h
        if lado == "l":
            return self.x, self.y + f * self.h
        return self.x + self.w, self.y + f * self.h


@dataclass
class Rel:
    pai: str
    filho: str
    rotulo: str
    rota: str                 # h, v, vhv, hvh, laco
    sp: tuple[str, float]     # side/fraction on the parent box
    sf: tuple[str, float]     # side/fraction on the child box
    min_pai: str = "1"        # "1" (mandatory FK) or "0" (nullable FK)
    max_filho: str = "N"      # "N" or "1"
    min_filho: str = "0"      # "0" or "1"
    faixa: float = 0.5        # lane position (0-1) in the gap between rows/columns
    tracejada: bool = False   # logical link, no physical FK
    pos_rotulo: float = 0.5
    sem_marcador: bool = False  # overview: link between areas, no cardinality
    pontos: list = field(default_factory=list)


@dataclass
class Diagrama:
    arquivo: str
    titulo: str
    subtitulo: str
    cor: str
    caixas: list[Caixa]
    rels: list[Rel]
    largura: float = 0
    altura: float = 0


def montar(d: Diagrama, schema: dict) -> None:
    alturas: dict[int, float] = {}
    for c in d.caixas:
        if c.fantasma:
            c.h = CAB + (16 if c.nota else 0) + 6
        elif c.itens:
            c.h = CAB + LINHA * len(c.itens) + 10
        else:
            c.h = CAB + LINHA * len(ATRIBUTOS[c.nome]) + 10
        alturas[c.lin] = max(alturas.get(c.lin, 0), c.h)
    ys, y = {}, TOPO
    for lin in sorted(alturas):
        ys[lin] = y
        y += alturas[lin] + GAP_Y
    for c in d.caixas:
        c.x = MARGEM + c.col * (LARG + GAP_X)
        c.y = ys[c.lin]
    d.largura = max(c.x + c.w for c in d.caixas) + MARGEM
    d.altura = y - GAP_Y + 92
    caixa = {c.nome: c for c in d.caixas}
    for r in d.rels:
        a, b = caixa[r.pai], caixa[r.filho]
        p0 = a.lado(*r.sp)
        p1 = b.lado(*r.sf)
        if r.rota == "h":
            y = p0[1] if a.h <= b.h else p1[1]
            p0, p1 = (p0[0], y), (p1[0], y)
            r.pontos = [p0, p1]
        elif r.rota == "v":
            x = p0[0]
            r.pontos = [(x, p0[1]), (x, p1[1])]
        elif r.rota == "vhv":
            topo, base = (a, b) if a.y < b.y else (b, a)
            yfaixa = topo.y + alturas[topo.lin] + r.faixa * GAP_Y
            r.pontos = [p0, (p0[0], yfaixa), (p1[0], yfaixa), p1]
        elif r.rota == "hvh":
            esq = a if a.x < b.x else b
            xfaixa = esq.x + esq.w + r.faixa * GAP_X
            r.pontos = [p0, (xfaixa, p0[1]), (xfaixa, p1[1]), p1]
        elif r.rota == "laco":       # self-relationship: orthogonal loop in the gap below the table
            ybase = a.y + a.h + r.faixa * GAP_Y
            q0, q1 = a.lado("b", r.sp[1]), a.lado("b", r.sf[1])
            r.pontos = [q0, (q0[0], ybase), (q1[0], ybase), q1]
        else:
            raise ValueError(r.rota)


# --------------------------------------------------------------------------- validation
def _segmentos(r: Rel):
    return list(zip(r.pontos[:-1], r.pontos[1:]))


def _cruza(s1, s2) -> bool:
    (a, b), (c, d) = s1, s2
    def orient(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)
    def sobre(p, q, r):
        return min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9 and min(p[1], r[1]) - 1e-9 <= q[1] <= max(p[1], r[1]) + 1e-9
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    return (o1 == 0 and sobre(a, c, b)) or (o2 == 0 and sobre(a, d, b)) or (o3 == 0 and sobre(c, a, d)) or (o4 == 0 and sobre(c, b, d))


def _atravessa(seg, c: Caixa) -> bool:
    (x1, y1), (x2, y2) = seg
    x0, y0, xa, ya = c.x + 1, c.y + 1, c.x + c.w - 1, c.y + c.h - 1
    if x1 == x2:
        return x0 < x1 < xa and max(y1, y2) > y0 and min(y1, y2) < ya
    return y0 < y1 < ya and max(x1, x2) > x0 and min(x1, x2) < xa


def _rotulo_rect(r: Rel):
    seg = max(_segmentos(r), key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
    (x1, y1), (x2, y2) = seg
    x, y = x1 + (x2 - x1) * r.pos_rotulo, y1 + (y2 - y1) * r.pos_rotulo
    w, h = 6.4 * len(r.rotulo) + 10, 16
    return seg, (x - w / 2, y - h / 2, x + w / 2, y + h / 2)


def validar(d: Diagrama) -> None:
    erros = []
    for i, r in enumerate(d.rels):
        for s in _segmentos(r):
            if s[0][0] != s[1][0] and s[0][1] != s[1][1]:
                erros.append(f"{r.pai}-{r.filho}: diagonal segment")
            for c in d.caixas:
                if _atravessa(s, c):
                    erros.append(f"{r.pai}-{r.filho}: goes through table {c.nome}")
        for q in d.rels[i + 1:]:
            if any(_cruza(s1, s2) for s1 in _segmentos(r) for s2 in _segmentos(q)):
                erros.append(f"{r.pai}-{r.filho} crosses {q.pai}-{q.filho}")
    # labels may not cover another line, a table or their own line's crow's foot
    for r in d.rels:
        _, (x0, y0, x1, y1) = _rotulo_rect(r)
        for p in ([] if r.sem_marcador else (r.pontos[0], r.pontos[-1])):
            if x0 - 26 < p[0] < x1 + 26 and y0 - 26 < p[1] < y1 + 26:
                erros.append(f"label '{r.rotulo}' covers the end of {r.pai}-{r.filho}")
        for q in d.rels:
            if q is r:
                continue
            for (a, b) in _segmentos(q):
                if max(a[0], b[0]) >= x0 and min(a[0], b[0]) <= x1 and max(a[1], b[1]) >= y0 and min(a[1], b[1]) <= y1:
                    erros.append(f"label '{r.rotulo}' touches line {q.pai}-{q.filho}")
        for c in d.caixas:
            if x1 > c.x and x0 < c.x + c.w and y1 > c.y and y0 < c.y + c.h:
                erros.append(f"label '{r.rotulo}' covers table {c.nome}")
    if erros:
        raise SystemExit(f"{d.arquivo}: invalid diagram\n  " + "\n  ".join(erros))


# --------------------------------------------------------------------------- drawing
def _marcador(p, direcao, minimo: str, maximo: str) -> str:
    """Crow's foot at end p. `direcao` points away from the box, along the line."""
    (x, y), (dx, dy) = p, direcao
    nx, ny = -dy, dx
    at = lambda d, o=0: (x + dx * d + nx * o, y + dy * d + ny * o)  # noqa: E731
    partes = []
    def barra(d):
        (a, b), (c, e) = at(d, -7), at(d, 7)
        partes.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{e:.1f}"/>')
    def circulo(d):
        cx, cy = at(d)
        partes.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" fill="{FUNDO}"/>')
    if maximo == "N":
        for o in (-7, 0, 7):
            (a, b), (c, e) = at(0, o), at(13)
            partes.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{e:.1f}"/>')
        barra(17) if minimo == "1" else circulo(22)
    else:
        barra(8)
        barra(14) if minimo == "1" else circulo(19)
    return "".join(partes)


def desenhar(d: Diagrama, schema: dict) -> str:
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{d.largura:.0f}" height="{d.altura:.0f}" '
         f'viewBox="0 0 {d.largura:.0f} {d.altura:.0f}" font-family="{FONTE}" role="img" aria-label="{escape(d.titulo)}">',
         f'<rect width="100%" height="100%" fill="{FUNDO}"/>',
         f'<text x="{MARGEM}" y="32" font-size="19" font-weight="700" fill="{TINTA}">{escape(d.titulo)}</text>',
         f'<text x="{MARGEM}" y="52" font-size="12.5" fill="{MUDO}">{escape(d.subtitulo)}</text>']
    # lines first, boxes on top
    for r in d.rels:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in r.pontos)
        dash = ' stroke-dasharray="6 4"' if r.tracejada else ""
        o.append(f'<polyline points="{pts}" fill="none" stroke="{LINHA_COR}" stroke-width="1.5"{dash}/>')
        def dirv(p, q):
            dx, dy = q[0] - p[0], q[1] - p[1]
            n = (dx * dx + dy * dy) ** 0.5
            return dx / n, dy / n
        if not r.sem_marcador:
            o.append(f'<g stroke="{LINHA_COR}" stroke-width="1.5" fill="none">')
            o.append(_marcador(r.pontos[0], dirv(r.pontos[0], r.pontos[1]), r.min_pai, "1"))
            o.append(_marcador(r.pontos[-1], dirv(r.pontos[-1], r.pontos[-2]), r.min_filho, r.max_filho))
            o.append("</g>")
        _, (x0, y0, x1, y1) = _rotulo_rect(r)
        o.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" rx="3" fill="{FUNDO}"/>')
        o.append(f'<text x="{(x0 + x1) / 2:.1f}" y="{y1 - 4.5:.1f}" font-size="11" font-style="italic" fill="{MUDO}" text-anchor="middle">{escape(r.rotulo)}</text>')
    for c in d.caixas:
        if c.fantasma:
            o.append(f'<rect x="{c.x}" y="{c.y}" width="{c.w}" height="{c.h}" rx="6" fill="#F6F8FA" stroke="#8C959F" stroke-width="1.2" stroke-dasharray="5 4"/>')
            o.append(f'<text x="{c.x + 12}" y="{c.y + 20}" font-size="13" font-weight="700" fill="{MUDO}">{escape(c.nome)}</text>')
            if c.nota:
                o.append(f'<text x="{c.x + 12}" y="{c.y + 38}" font-size="11" fill="{MUDO}">{escape(c.nota)}</text>')
            continue
        o.append(f'<rect x="{c.x}" y="{c.y}" width="{c.w}" height="{c.h}" rx="6" fill="{FUNDO}" stroke="{d.cor}" stroke-width="1.6"/>')
        o.append(f'<path d="M{c.x} {c.y + CAB} v{-CAB + 6} a6 6 0 0 1 6 -6 h{c.w - 12} a6 6 0 0 1 6 6 v{CAB - 6} z" fill="{d.cor}"/>')
        fs = min(13.5, (c.w - 24) / (0.62 * len(c.nome)))
        o.append(f'<text x="{c.x + 12}" y="{c.y + 20}" font-size="{fs:.1f}" font-weight="700" fill="#FFFFFF">{escape(c.nome)}</text>')
        if c.itens:
            for i, item in enumerate(c.itens):
                o.append(f'<text x="{c.x + 14}" y="{c.y + CAB + 16 + i * LINHA}" font-size="12" fill="{TINTA}">{escape(item)}</text>')
            continue
        cols = schema[c.nome]
        for i, nome in enumerate(ATRIBUTOS[c.nome]):
            col = cols[nome]
            yy = c.y + CAB + 16 + i * LINHA
            chave = "/".join(k for k in ("PK", "FK", "UK") if k in col.chaves)
            if chave:
                o.append(f'<text x="{c.x + 10}" y="{yy}" font-size="10" font-weight="700" fill="{d.cor}">{chave}</text>')
            peso = ' font-weight="700"' if "PK" in col.chaves else ""
            nulo = "?" if col.nulo else ""
            o.append(f'<text x="{c.x + 46}" y="{yy}" font-size="12"{peso} fill="{TINTA}">{escape(nome)}{nulo}</text>')
            o.append(f'<text x="{c.x + c.w - 10}" y="{yy}" font-size="11" fill="{MUDO}" text-anchor="end">{escape(col.tipo)}</text>')
    o.append(_legenda(d))
    o.append("</svg>")
    return "\n".join(o)


def _legenda(d: Diagrama) -> str:
    y = d.altura - 34
    if all(r.sem_marcador for r in d.rels):
        return (f'<text x="{MARGEM}" y="{y + 4}" font-size="11.5" fill="{MUDO}">Labels: keys that link the areas. '
                f'Dashed line: logical link (no physical FK) or reconciliation of totals. Details in diagrams 1 to 6.</text>')
    x = MARGEM
    itens = [("1", "1", "exactly one"), ("0", "1", "zero or one"), ("1", "N", "one or more"), ("0", "N", "zero or more")]
    o = [f'<g font-size="11.5" fill="{MUDO}">']
    for mn, mx, txt in itens:
        o.append(f'<line x1="{x}" y1="{y}" x2="{x + 44}" y2="{y}" stroke="{LINHA_COR}" stroke-width="1.5"/>')
        o.append(f'<g stroke="{LINHA_COR}" stroke-width="1.5" fill="none">{_marcador((x + 44, y), (-1, 0), mn, mx)}</g>')
        o.append(f'<text x="{x + 52}" y="{y + 4}">{txt}</text>')
        x += 52 + 7 * len(txt) + 26
    o.append(f'<rect x="{x}" y="{y - 9}" width="26" height="18" rx="4" fill="#F6F8FA" stroke="#8C959F" stroke-dasharray="4 3"/>')
    o.append(f'<text x="{x + 34}" y="{y + 4}">table from another area</text>')
    x += 34 + 7 * 20 + 20
    o.append(f'<text x="{x}" y="{y + 4}">field? = nullable</text>')
    o.append("</g>")
    return "".join(o)


# --------------------------------------------------------------------------- the diagrams
G = lambda nome, col, lin, nota="": Caixa(nome, col, lin, fantasma=True, nota=nota)  # noqa: E731
T = Caixa

DIAGRAMAS = [
    Diagrama(
        "01_catalogo_estoque.svg", "1. Catalog and inventory",
        "Product, SKU (variant), price history (SCD2), stock balance and daily stock closing.", "#1F6FEB",
        [T("categorias", 0, 0), T("produtos", 1, 0), T("fornecedores", 2, 0),
         T("historico_precos", 0, 1), T("variantes", 1, 1), T("movimentacoes_estoque", 2, 1),
         G("devolucoes", 3, 1, "see diagram 2"),
         T("estoque", 0, 2), T("estoque_diario", 1, 2), G("pedidos", 2, 2, "see diagram 2")],
        [Rel("categorias", "categorias", "parent of", "laco", ("b", .15), ("b", .85), min_pai="0", faixa=.32),
         Rel("categorias", "produtos", "classifies", "h", ("r", .5), ("l", .5)),
         Rel("fornecedores", "produtos", "supplies", "h", ("l", .5), ("r", .5)),
         Rel("produtos", "variantes", "has SKUs", "v", ("b", .5), ("t", .5), min_filho="1"),
         Rel("variantes", "historico_precos", "prices", "h", ("l", .3), ("r", .3)),
         Rel("variantes", "movimentacoes_estoque", "moves", "h", ("r", .3), ("l", .3)),
         Rel("fornecedores", "movimentacoes_estoque", "purchase receipt", "v", ("b", .5), ("t", .5), min_pai="0"),
         Rel("variantes", "estoque_diario", "daily close", "v", ("b", .5), ("t", .5)),
         Rel("variantes", "estoque", "current stock", "vhv", ("b", .2), ("t", .5), max_filho="1", min_filho="1"),
         Rel("pedidos", "movimentacoes_estoque", "sale", "v", ("t", .5), ("b", .5), min_pai="0"),
         Rel("devolucoes", "movimentacoes_estoque", "return", "h", ("l", .5), ("r", .3), min_pai="0")],
    ),
    Diagrama(
        "02_clientes_pedidos.svg", "2. Customers, orders and after-sales",
        "Customer registration, orders with items, payment attempts, shipping, returns and reviews.", "#8250DF",
        [T("enderecos", 0, 0), T("clientes", 1, 0), T("avaliacoes", 2, 0), G("produtos", 3, 0, "see diagram 1"),
         T("cupons", 0, 1), T("pedidos", 1, 1), T("fretes", 2, 1),
         T("pagamentos", 0, 2), T("itens_pedido", 1, 2), T("devolucoes", 2, 2),
         G("variantes", 1, 3, "see diagram 1")],
        [Rel("clientes", "enderecos", "has", "h", ("l", .3), ("r", .3), min_filho="1"),
         Rel("clientes", "avaliacoes", "writes", "h", ("r", .3), ("l", .3)),
         Rel("produtos", "avaliacoes", "reviewed in", "h", ("l", .2), ("r", .2)),
         Rel("clientes", "pedidos", "places", "v", ("b", .5), ("t", .5)),
         Rel("enderecos", "pedidos", "ships to", "vhv", ("b", .5), ("t", .25), min_pai="0"),
         Rel("pedidos", "avaliacoes", "receives", "vhv", ("t", .75), ("b", .5)),
         Rel("cupons", "pedidos", "applied to", "h", ("r", .3), ("l", .3), min_pai="0"),
         Rel("pedidos", "fretes", "ships", "h", ("r", .3), ("l", .3), max_filho="1", min_filho="1"),
         Rel("pedidos", "pagamentos", "attempts", "vhv", ("b", .2), ("t", .5), min_filho="1"),
         Rel("pedidos", "itens_pedido", "contains", "v", ("b", .5), ("t", .5), min_filho="1"),
         Rel("pedidos", "devolucoes", "generates", "vhv", ("b", .8), ("t", .5)),
         Rel("itens_pedido", "devolucoes", "returned", "h", ("r", .3), ("l", .3)),
         Rel("variantes", "itens_pedido", "sold in", "v", ("t", .5), ("b", .5))],
    ),

    Diagrama(
        "03_tracking_atribuicao.svg", "3. Website tracking and attribution",
        "Ad click → session → GA4 events (server-side GTM) → sends to Meta CAPI / Google; credit per touchpoint.", "#BF3989",
        [G("meta_anuncios", 0, 0, "see diagram 4"), G("google_grupos_anuncio", 1, 0, "see diagram 5"),
         G("google_palavras_chave", 2, 0, "see diagram 5"),
         T("cliques_midia", 1, 1), G("meta_campanhas", 3, 1, "see diagram 4"),
         G("clientes", 0, 2, "see diagram 2"), T("sessoes", 1, 2), T("atribuicoes", 2, 2), G("google_campanhas", 3, 2, "see diagram 5"),
         G("variantes", 0, 3, "see diagram 1"), T("eventos", 1, 3), G("pedidos", 2, 3, "see diagram 2"),
         T("envios_conversao", 1, 4)],
        [Rel("meta_anuncios", "cliques_midia", "fbclid", "vhv", ("b", .5), ("t", .2), min_pai="0"),
         Rel("google_grupos_anuncio", "cliques_midia", "gclid", "v", ("b", .5), ("t", .5), min_pai="0"),
         Rel("google_palavras_chave", "cliques_midia", "keyword", "vhv", ("b", .5), ("t", .8), min_pai="0"),
         Rel("cliques_midia", "sessoes", "opens", "v", ("b", .5), ("t", .5), min_pai="0", max_filho="1"),
         Rel("clientes", "sessoes", "user_id", "h", ("r", .3), ("l", .3), min_pai="0"),
         Rel("sessoes", "atribuicoes", "touchpoint", "h", ("r", .3), ("l", .3)),
         Rel("google_campanhas", "atribuicoes", "credited", "h", ("l", .3), ("r", .3), min_pai="0"),
         Rel("meta_campanhas", "atribuicoes", "credited", "vhv", ("b", .5), ("t", .7), min_pai="0"),
         Rel("sessoes", "eventos", "contains", "v", ("b", .5), ("t", .5), min_filho="1"),
         Rel("clientes", "eventos", "user_id", "vhv", ("b", .5), ("t", .2), min_pai="0"),
         Rel("sessoes", "pedidos", "purchase session", "vhv", ("b", .8), ("t", .2), min_pai="0"),
         Rel("pedidos", "atribuicoes", "credit", "v", ("t", .7), ("b", .7), min_filho="1"),
         Rel("variantes", "eventos", "item", "h", ("r", .3), ("l", .3), min_pai="0"),
         Rel("pedidos", "eventos", "purchase", "h", ("l", .3), ("r", .3), min_pai="0"),
         Rel("eventos", "envios_conversao", "CAPI / EC", "v", ("b", .5), ("t", .5))],
    ),
    Diagrama(
        "04_meta_ads.svg", "4. Meta Ads",
        "Account → campaign → ad set → ad, with daily insights per ad (as the Marketing API exports them).", "#0969DA",
        [T("meta_contas", 1, 0),
         G("atribuicoes", 0, 1, "see diagram 3"), T("meta_campanhas", 1, 1), T("meta_conjuntos", 2, 1), T("meta_anuncios", 3, 1),
         G("cliques_midia", 2, 2, "see diagram 3"), T("meta_metricas_diarias", 3, 2)],
        [Rel("meta_contas", "meta_campanhas", "contains", "v", ("b", .5), ("t", .5), min_filho="1"),
         Rel("meta_campanhas", "meta_conjuntos", "contains", "h", ("r", .3), ("l", .3), min_filho="1"),
         Rel("meta_conjuntos", "meta_anuncios", "contains", "h", ("r", .3), ("l", .3), min_filho="1"),
         Rel("meta_campanhas", "atribuicoes", "credited", "h", ("l", .3), ("r", .3), min_pai="0"),
         Rel("meta_anuncios", "meta_metricas_diarias", "daily insights", "v", ("b", .5), ("t", .5)),
         Rel("meta_anuncios", "cliques_midia", "fbclid", "vhv", ("b", .2), ("t", .5), min_pai="0")],
    ),
    Diagrama(
        "05_google_ads.svg", "5. Google Ads",
        "Account → campaign (Search, Shopping, PMax, Demand Gen) → ad group/asset group → keyword, with daily metrics.", "#1A7F37",
        [T("google_contas", 1, 0), T("google_palavras_chave_metricas_diarias", 3, 0, largura=300),
         G("atribuicoes", 0, 1, "see diagram 3"), T("google_campanhas", 1, 1), T("google_grupos_anuncio", 2, 1), T("google_palavras_chave", 3, 1),
         T("google_metricas_diarias", 2, 2), G("cliques_midia", 3, 2, "see diagram 3")],
        [Rel("google_contas", "google_campanhas", "contains", "v", ("b", .5), ("t", .5), min_filho="1"),
         Rel("google_campanhas", "google_grupos_anuncio", "contains", "h", ("r", .3), ("l", .3), min_filho="1"),
         Rel("google_grupos_anuncio", "google_palavras_chave", "contains", "h", ("r", .3), ("l", .3)),
         Rel("google_campanhas", "atribuicoes", "credited", "h", ("l", .3), ("r", .3), min_pai="0"),
         Rel("google_palavras_chave", "google_palavras_chave_metricas_diarias", "daily metrics", "v", ("t", .5), ("b", .5)),
         Rel("google_grupos_anuncio", "google_metricas_diarias", "daily metrics", "v", ("b", .5), ("t", .5)),
         Rel("google_palavras_chave", "cliques_midia", "keyword", "v", ("b", .6), ("t", .6), min_pai="0"),
         Rel("google_grupos_anuncio", "cliques_midia", "gclid", "vhv", ("b", .85), ("t", .2), min_pai="0")],
    ),
    Diagrama(
        "06_mmm_outros_canais.svg", "6. Regional MMM, geo tests and other channels",
        "Media from every platform by day × channel × state; geo-lift; TikTok, affiliates and CRM. Dashed lines: logical link, no physical FK.", "#9A6700",
        [T("canais_midia", 0, 0), T("midia_regional_diaria", 1, 0), T("regioes", 2, 0), G("enderecos", 3, 0, "see diagram 2"),
         T("testes_geo", 0, 1), T("testes_geo_regioes", 1, 1), T("calendario_comercial", 2, 1), G("pedidos", 3, 1, "see diagram 2"),
         T("tiktok_campanhas", 0, 2), T("tiktok_metricas_diarias", 1, 2), T("crm_disparos", 2, 2),
         T("afiliados_parceiros", 0, 3), T("afiliados_metricas_diarias", 1, 3)],
        [Rel("canais_midia", "midia_regional_diaria", "spends on", "h", ("r", .3), ("l", .3)),
         Rel("regioes", "midia_regional_diaria", "in state", "h", ("l", .3), ("r", .3)),
         Rel("canais_midia", "testes_geo", "tested in", "v", ("b", .5), ("t", .5)),
         Rel("testes_geo", "testes_geo_regioes", "by state", "h", ("r", .3), ("l", .3), min_filho="1"),
         Rel("regioes", "testes_geo_regioes", "state", "vhv", ("b", .3), ("t", .7)),
         Rel("regioes", "enderecos", "uf", "h", ("r", .3), ("l", .3), tracejada=True),
         Rel("calendario_comercial", "pedidos", "date", "h", ("r", .3), ("l", .3), tracejada=True),
         Rel("tiktok_campanhas", "tiktok_metricas_diarias", "daily metrics", "h", ("r", .3), ("l", .3)),
         Rel("afiliados_parceiros", "afiliados_metricas_diarias", "daily metrics", "h", ("r", .3), ("l", .3))],
    ),
]


A = lambda nome, col, lin, itens: Caixa(nome, col, lin, itens=itens)  # noqa: E731
VISAO_GERAL = Diagrama(
    "00_visao_geral.svg", "Overview: 44 tables in 7 areas",
    "Each area has its own diagram (1 to 6). The lines show which keys link the areas.", "#24292F",
    [A("1 · Catalog and inventory", 0, 0, ["categorias · fornecedores", "produtos · variantes", "historico_precos (SCD2)", "estoque · estoque_diario", "movimentacoes_estoque"]),
     A("2 · Customers and orders", 1, 0, ["clientes · enderecos · cupons", "pedidos · itens_pedido", "pagamentos · fretes", "devolucoes · avaliacoes"]),
     A("6 · Regional MMM", 2, 0, ["midia_regional_diaria", "canais_midia · regioes", "calendario_comercial", "testes_geo · testes_geo_regioes"]),
     A("6 · TikTok, affiliates, CRM", 3, 0, ["tiktok_campanhas", "tiktok_metricas_diarias", "afiliados_parceiros", "afiliados_metricas_diarias", "crm_disparos"]),
     A("4 · Meta Ads", 0, 1, ["meta_contas · meta_campanhas", "meta_conjuntos · meta_anuncios", "meta_metricas_diarias"]),
     A("3 · Tracking and attribution", 1, 1, ["cliques_midia · sessoes", "eventos (GA4)", "envios_conversao (CAPI/EC)", "atribuicoes"]),
     A("5 · Google Ads", 2, 1, ["google_contas · google_campanhas", "google_grupos_anuncio", "google_palavras_chave", "*_metricas_diarias"])],
    [Rel("1 · Catalog and inventory", "2 · Customers and orders", "variante_id", "h", ("r", .3), ("l", .3), sem_marcador=True),
     Rel("2 · Customers and orders", "3 · Tracking and attribution", "sessao_id · pedido_id", "v", ("b", .5), ("t", .5), sem_marcador=True),
     Rel("1 · Catalog and inventory", "3 · Tracking and attribution", "variante_id", "vhv", ("b", .8), ("t", .2), sem_marcador=True),
     Rel("2 · Customers and orders", "6 · Regional MMM", "uf · date", "h", ("r", .3), ("l", .3), sem_marcador=True, tracejada=True),
     Rel("6 · Regional MMM", "6 · TikTok, affiliates, CRM", "reconciles", "h", ("r", .3), ("l", .3), sem_marcador=True, tracejada=True),
     Rel("6 · Regional MMM", "5 · Google Ads", "reconciles", "v", ("b", .5), ("t", .5), sem_marcador=True, tracejada=True),
     Rel("4 · Meta Ads", "3 · Tracking and attribution", "ad · campaign", "h", ("r", .3), ("l", .3), sem_marcador=True),
     Rel("5 · Google Ads", "3 · Tracking and attribution", "ad group · keyword", "h", ("l", .3), ("r", .3), sem_marcador=True)],
)


def gerar() -> list[Path]:
    schema = ler_schema()
    cobertas = {c.nome for d in DIAGRAMAS for c in d.caixas if not c.fantasma and not c.itens}
    faltando = set(schema) - cobertas
    assert not faltando, f"tables missing from the diagrams: {sorted(faltando)}"
    for d in DIAGRAMAS:
        for c in d.caixas:
            if not c.fantasma and not c.itens:
                assert set(ATRIBUTOS[c.nome]) <= set(schema[c.nome]), (c.nome, set(ATRIBUTOS[c.nome]) - set(schema[c.nome]))
    SAIDA.mkdir(parents=True, exist_ok=True)
    feitos = []
    for d in [VISAO_GERAL] + DIAGRAMAS:
        montar(d, schema)
        validar(d)
        p = SAIDA / d.arquivo
        p.write_text(desenhar(d, schema), encoding="utf-8")
        feitos.append(p)
        print(f"{p.relative_to(RAIZ)}: {sum(not c.fantasma and not c.itens for c in d.caixas)} tables, {len(d.rels)} relationships, 0 crossings")
    return feitos


# --------------------------------------------------------------------------- one-pager
DESTAQUES = [("44", "tables"), ("144k", "orders"), ("7.0M", "sessions"), ("20.5M", "GA4 events"),
             ("R$ 38.9M", "paid revenue"), ("R$ 6.0M", "paid media")]


def _interno(svg: str) -> tuple[float, float, str]:
    w, h = (float(v) for v in re.search(r'width="([\d.]+)" height="([\d.]+)"', svg).groups())
    return w, h, svg[svg.index(">") + 1: svg.rindex("</svg>")]


def one_pager(arquivos: list[Path]) -> Path:
    """Puts the overview and the 6 area diagrams together in a single image (top of the README)."""
    visao, *areas = [_interno(p.read_text(encoding="utf-8")) for p in arquivos]
    esc, gap, m = 0.62, 40, 40
    larg_painel = max(w for w, _, _ in areas) * esc
    largura = 2 * larg_painel + gap + 2 * m
    o_svg = []
    y = 150
    # the overview takes the full width
    ev = (largura - 2 * m) / visao[0]
    o_svg.append(f'<svg x="{m}" y="{y}" width="{visao[0] * ev:.0f}" height="{visao[1] * ev:.0f}" viewBox="0 0 {visao[0]:.0f} {visao[1]:.0f}">{visao[2]}</svg>')
    y += visao[1] * ev + gap
    for i in range(0, len(areas), 2):
        par = areas[i:i + 2]
        altura = max(h for _, h, _ in par) * esc
        for j, (w, h, corpo) in enumerate(par):
            x = m + j * (larg_painel + gap)
            o_svg.append(f'<rect x="{x - 1}" y="{y - 1}" width="{w * esc + 2:.0f}" height="{h * esc + 2:.0f}" fill="none" stroke="#D0D7DE" rx="8"/>')
            o_svg.append(f'<svg x="{x}" y="{y}" width="{w * esc:.0f}" height="{h * esc:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">{corpo}</svg>')
        y += altura + gap
    altura_total = y + 20
    chips, cx = [], m
    for valor, rotulo in DESTAQUES:
        wv = 11.6 * len(valor) + 7.4 * len(rotulo) + 46
        chips.append(f'<rect x="{cx}" y="86" width="{wv}" height="40" rx="20" fill="#F6F8FA" stroke="#D0D7DE"/>'
                     f'<text x="{cx + 18}" y="112" font-size="20" font-weight="700" fill="{TINTA}">{escape(valor)}'
                     f'<tspan font-size="14" font-weight="400" fill="{MUDO}"> {escape(rotulo)}</tspan></text>')
        cx += wv + 14
    topo = (f'<text x="{m}" y="48" font-size="30" font-weight="700" fill="{TINTA}">Tecelã Tecidos · e-commerce data model</text>'
            f'<text x="{m}" y="74" font-size="16" fill="{MUDO}">Fictitious fabric store, Oct/2023 to Oct/2026: catalog, orders, GA4 tracking (server-side GTM), '
            f'Meta, Google and TikTok Ads, attribution and regional MMM. 100% synthetic data.</text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura:.0f}" height="{altura_total:.0f}" '
           f'viewBox="0 0 {largura:.0f} {altura_total:.0f}" font-family="{FONTE}" role="img" '
           f'aria-label="Tecelã Tecidos data model: overview and the diagram of each area">'
           f'<rect width="100%" height="100%" fill="{FUNDO}"/>{topo}{"".join(chips)}{"".join(o_svg)}</svg>')
    destino = SAIDA / "modelo_de_dados_one_pager.svg"
    destino.write_text(svg, encoding="utf-8")
    print(f"{destino.relative_to(RAIZ)}: one-pager with {len(arquivos)} diagrams")
    return destino


def _pares(itens: list) -> list[list]:
    """Every way of grouping the panels in rows of two (order within a row follows the number)."""
    if not itens:
        return [[]]
    a, resto = itens[0], itens[1:]
    out = []
    for i, b in enumerate(resto):
        for cauda in _pares(resto[:i] + resto[i + 1:]):
            out.append([[a, b]] + cauda)
    return out


def one_pager_3x4(arquivos: list[Path]) -> Path:
    """3:4 version for LinkedIn: 1500 x 2000 canvas with header, overview, the 6 areas and a footer.
    Tries the arrangements (how areas are grouped in rows and the overview width) and keeps the one
    that makes the diagrams largest."""
    W, H, m, gap = 1500, 2000, 50, 28
    visao, *areas = [_interno(p.read_text(encoding="utf-8")) for p in arquivos]
    topo_h, rodape_h = 250, 80
    cw, ch = W - 2 * m, H - topo_h - rodape_h
    melhor = None
    for frac in [x / 20 for x in range(10, 21)]:
        vw = cw * frac
        vh = vw * visao[1] / visao[0]
        resto_h = ch - vh - gap
        for linhas in _pares(list(range(len(areas)))):
            soma_h = sum(max(areas[i][1] for i in lin) for lin in linhas)
            larg = max(sum(areas[i][0] for i in lin) for lin in linhas)
            s = min((resto_h - gap * (len(linhas) - 1)) / soma_h, (cw - gap) / larg)
            if melhor is None or s > melhor[0] + 1e-9:
                melhor = (s, frac, linhas, vw, vh)
    s, frac, linhas, vw, vh = melhor
    o = []
    y = topo_h
    o.append(f'<svg x="{(W - vw) / 2:.1f}" y="{y}" width="{vw:.1f}" height="{vh:.1f}" viewBox="0 0 {visao[0]:.0f} {visao[1]:.0f}">{visao[2]}</svg>')
    y += vh + gap
    for lin in linhas:
        larg_lin = sum(areas[i][0] * s for i in lin) + gap * (len(lin) - 1)
        x = (W - larg_lin) / 2
        alt = max(areas[i][1] for i in lin) * s
        for i in lin:
            w, h, corpo = areas[i]
            o.append(f'<rect x="{x - 1:.1f}" y="{y - 1:.1f}" width="{w * s + 2:.1f}" height="{h * s + 2:.1f}" fill="none" stroke="#D0D7DE" rx="6"/>')
            o.append(f'<svg x="{x:.1f}" y="{y:.1f}" width="{w * s:.1f}" height="{h * s:.1f}" viewBox="0 0 {w:.0f} {h:.0f}">{corpo}</svg>')
            x += w * s + gap
        y += alt + gap
    chips, cx = [], m
    for valor, rotulo in DESTAQUES:
        wv = 13.2 * len(valor) + 8.6 * len(rotulo) + 46
        chips.append(f'<rect x="{cx:.1f}" y="168" width="{wv:.1f}" height="48" rx="24" fill="#F6F8FA" stroke="#D0D7DE"/>'
                     f'<text x="{cx + 20:.1f}" y="199" font-size="23" font-weight="700" fill="{TINTA}">{escape(valor)}'
                     f'<tspan font-size="16" font-weight="400" fill="{MUDO}"> {escape(rotulo)}</tspan></text>')
        cx += wv + 12
    topo = (f'<text x="{m}" y="78" font-size="46" font-weight="700" fill="{TINTA}">Tecelã Tecidos: the data model</text>'
            f'<text x="{m}" y="120" font-size="21" fill="{MUDO}">Fictitious e-commerce, 3 years of operations: orders, GA4 tracking, Meta, Google and TikTok Ads,</text>'
            f'<text x="{m}" y="148" font-size="21" fill="{MUDO}">attribution and regional MMM. 44 tables in 7 areas. 100% synthetic data.</text>')
    rodape = (f'<line x1="{m}" y1="{H - rodape_h + 10}" x2="{W - m}" y2="{H - rodape_h + 10}" stroke="#D0D7DE"/>'
              f'<text x="{m}" y="{H - 34}" font-size="19" fill="{MUDO}">Code and diagrams: '
              f'<tspan font-weight="700" fill="{TINTA}">github.com/arielabade/dados-sinteticos-ecommerce-tecidos</tspan></text>'
              f'<text x="{W - m}" y="{H - 34}" font-size="19" fill="{MUDO}" text-anchor="end">Dataset: '
              f'<tspan font-weight="700" fill="{TINTA}">kaggle.com/arielabade</tspan></text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONTE}" '
           f'role="img" aria-label="Tecelã Tecidos data model, 3:4 format">'
           f'<rect width="100%" height="100%" fill="{FUNDO}"/>{topo}{"".join(chips)}{"".join(o)}{rodape}</svg>')
    destino = SAIDA / "modelo_de_dados_one_pager_3x4.svg"
    destino.write_text(svg, encoding="utf-8")
    print(f"{destino.relative_to(RAIZ)}: 3:4, diagram scale {s:.2f}, overview at {frac:.0%} of the width, rows {linhas}")
    return destino


if __name__ == "__main__":
    feitos = gerar()
    one_pager(feitos)
    one_pager_3x4(feitos)
