"""Catálogo: categorias, fornecedores, produtos, variantes e preços diários."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from faker import Faker

from .calendario import BLACK_FRIDAY, mult_categoria
from .clientes import doc_ficticio
from .config import CFG

TIPOS = ["hobby", "costureira", "atelie", "confeccao"]

# familia -> (id, nome)
FAMILIAS = {
    "algodao": (1, "Algodão"),
    "linho": (2, "Linho"),
    "viscose": (3, "Viscose"),
    "malha": (4, "Malha"),
    "sintetico": (5, "Sintéticos e Especiais"),
    "jeans": (6, "Jeans e Sarja"),
}

# subcategoria: família, sazonalidade, faixa de preço por metro, gramatura,
# largura, composições, nº de produtos, afinidade (hobby, costureira, ateliê,
# confecção), aceita rolo?, nomes de linha de produto, tipo de variação.
SUBCATS = [
    # chave, nome, familia, saz, preco, gram, larg, composicoes, nprod, afin, rolo, variacao
    ("tricoline", "Tricoline", "algodao", "algodao", (24, 44), (110, 135), 150,
     ["100% algodão"], 34, (1.6, 1.4, 1.0, 0.6), True, "misto"),
    ("chita", "Chita", "algodao", "chita", (11, 18), (85, 105), 140,
     ["100% algodão"], 10, (1.4, 0.8, 0.4, 0.5), True, "estampa"),
    ("percal", "Percal e Cretone", "algodao", "algodao", (19, 34), (120, 170), 250,
     ["100% algodão", "50% algodão 50% poliéster"], 12, (0.8, 1.0, 1.0, 0.8), True, "misto"),
    ("algodao_cru", "Algodão Cru e Morim", "algodao", "algodao", (8, 16), (100, 160), 160,
     ["100% algodão"], 6, (0.9, 0.7, 0.6, 1.2), True, "cor"),
    ("linho_puro", "Linho Puro", "linho", "linho", (85, 145), (160, 210), 145,
     ["100% linho"], 10, (0.2, 0.7, 1.8, 0.4), False, "cor"),
    ("linho_misto", "Linho Misto", "linho", "linho", (42, 72), (150, 200), 145,
     ["55% linho 45% viscose", "70% viscose 30% linho"], 14, (0.4, 1.1, 1.5, 0.9), True, "cor"),
    ("viscolinho", "Viscolinho", "linho", "viscose", (29, 42), (120, 150), 140,
     ["67% viscose 33% linho"], 12, (0.5, 1.2, 1.2, 1.2), True, "misto"),
    ("viscose_lisa", "Viscose Lisa", "viscose", "viscose", (21, 33), (110, 140), 145,
     ["100% viscose"], 14, (0.6, 1.3, 1.0, 1.5), True, "cor"),
    ("viscose_estampada", "Viscose Estampada", "viscose", "viscose", (25, 39), (110, 140), 145,
     ["100% viscose"], 22, (0.8, 1.4, 1.1, 1.0), True, "estampa"),
    ("crepe", "Crepe", "viscose", "viscose", (29, 49), (130, 170), 150,
     ["100% viscose", "100% poliéster"], 10, (0.3, 1.0, 1.5, 0.9), True, "cor"),
    ("malha_pv", "Malha PV", "malha", "malha", (29, 42), (160, 190), 180,
     ["67% poliéster 33% viscose"], 8, (0.5, 1.0, 0.7, 2.2), True, "cor"),
    ("suedine", "Suedine", "malha", "malha", (33, 47), (150, 180), 170,
     ["92% algodão 8% elastano"], 6, (0.4, 1.0, 0.8, 1.8), True, "cor"),
    ("ribana", "Ribana", "malha", "malha", (28, 39), (220, 280), 120,
     ["96% algodão 4% elastano"], 5, (0.4, 1.1, 0.7, 1.8), True, "cor"),
    ("moletom", "Moletom", "malha", "malha", (44, 66), (280, 340), 180,
     ["50% algodão 50% poliéster", "100% algodão"], 7, (0.5, 1.0, 0.8, 1.7), True, "cor"),
    ("malha_algodao", "Malha 100% Algodão", "malha", "malha", (36, 54), (150, 180), 180,
     ["100% algodão"], 8, (0.6, 1.2, 0.9, 1.4), True, "misto"),
    ("oxford", "Oxford e Tricoline Mista", "sintetico", "sintetico", (9, 16), (90, 120), 150,
     ["100% poliéster"], 6, (0.9, 0.8, 0.5, 1.6), True, "cor"),
    ("cetim", "Cetim", "sintetico", "sintetico", (13, 25), (90, 120), 150,
     ["100% poliéster"], 6, (0.9, 0.8, 1.1, 0.7), True, "cor"),
    ("tule", "Tule", "sintetico", "sintetico", (6, 13), (25, 40), 240,
     ["100% poliamida"], 4, (1.2, 0.9, 1.2, 0.4), True, "cor"),
    ("lycra", "Lycra e Suplex", "sintetico", "sintetico", (36, 58), (180, 240), 160,
     ["80% poliamida 20% elastano"], 6, (0.7, 1.0, 0.9, 1.4), True, "cor"),
    ("paete", "Paetê e Lantejoula", "sintetico", "sintetico", (45, 95), (200, 300), 130,
     ["100% poliéster"], 5, (0.9, 0.8, 1.2, 0.3), False, "cor"),
    ("feltro", "Feltro", "sintetico", "sintetico", (14, 24), (180, 220), 140,
     ["100% poliéster"], 4, (1.8, 0.6, 0.6, 0.2), False, "cor"),
    ("jeans", "Jeans", "jeans", "jeans", (32, 56), (290, 400), 160,
     ["98% algodão 2% elastano", "100% algodão"], 8, (0.4, 1.0, 0.9, 1.6), True, "cor"),
    ("sarja", "Sarja e Brim", "jeans", "jeans", (22, 38), (220, 300), 160,
     ["100% algodão", "97% algodão 3% elastano"], 8, (0.4, 1.0, 0.8, 1.6), True, "cor"),
]

CORES = [
    ("Preto", 2.4), ("Branco", 2.2), ("Off-White", 1.8), ("Cru", 1.2), ("Azul Marinho", 1.7),
    ("Azul Royal", 0.9), ("Azul Bebê", 0.8), ("Azul Serenity", 0.7), ("Verde Militar", 1.0),
    ("Verde Água", 0.7), ("Verde Bandeira", 0.6), ("Verde Musgo", 0.8), ("Vermelho", 1.0),
    ("Vinho", 1.1), ("Marsala", 0.9), ("Rosa Bebê", 0.9), ("Rosa Chiclete", 0.6),
    ("Rosa Antigo", 0.8), ("Pink", 0.6), ("Lilás", 0.7), ("Roxo", 0.5), ("Amarelo", 0.6),
    ("Mostarda", 1.0), ("Laranja", 0.5), ("Terracota", 1.1), ("Caramelo", 0.9), ("Bege", 1.3),
    ("Areia", 1.0), ("Nude", 0.9), ("Cinza Mescla", 1.3), ("Chumbo", 0.9), ("Marrom", 0.7),
    ("Café", 0.6), ("Goiaba", 0.5), ("Coral", 0.6), ("Salmão", 0.5), ("Tiffany", 0.6),
]

ESTAMPAS = [
    ("Floral Pequeno", 1.4, None), ("Floral Grande", 1.1, None), ("Poá", 1.0, None),
    ("Xadrez Vichy", 1.0, "junino"), ("Xadrez Escocês", 0.7, "inverno"), ("Listrado", 0.8, None),
    ("Geométrico", 0.7, None), ("Folhagem Tropical", 0.9, "verao"), ("Animal Print", 0.6, None),
    ("Patchwork", 0.7, None), ("Abstrato", 0.6, None), ("Infantil Ursinhos", 0.8, None),
    ("Natalino", 0.9, "natal"), ("Bandeirinhas Juninas", 0.8, "junino"), ("Liberty", 0.9, None),
    ("Paisley", 0.5, None), ("Tie-Dye", 0.5, "verao"), ("Arabesco", 0.4, None),
    ("Chita Floral Clássica", 1.6, "junino"), ("Chita Fuxico", 0.8, "junino"),
]

# Multiplicador mensal por "tema" da estampa (jan..dez)
SAZ_ESTAMPA = {
    None: [1] * 12,
    "junino": [0.6, 0.7, 0.8, 1.0, 2.2, 3.0, 1.2, 0.6, 0.5, 0.5, 0.5, 0.6],
    "natal": [0.2, 0.1, 0.1, 0.1, 0.1, 0.2, 0.2, 0.3, 0.8, 2.2, 4.0, 3.0],
    "inverno": [0.6, 0.6, 0.8, 1.1, 1.5, 1.7, 1.6, 1.2, 0.9, 0.7, 0.6, 0.6],
    "verao": [1.4, 1.3, 1.1, 0.9, 0.7, 0.6, 0.6, 0.8, 1.0, 1.2, 1.4, 1.5],
}

LINHAS = ["Premium", "Essencial", "Coleção Jardim", "Coleção Brasil", "Coleção Atelier",
          "Coleção Raízes", "Coleção Verão", "Coleção Aconchego", "Linha Profissional",
          "Coleção Festa", "Coleção Infantil", "Coleção Natural", "Linha Confecção"]

GRAMATURA_NOME = {"leve": "Leve", "medio": "", "pesado": "Encorpado"}

FORNECEDORES_BASE = [
    # nome fantasia, UF, cidade, prazo, confiabilidade, famílias que fornece
    ("Tecelagem Vale Azul", "SC", "Blumenau", 12, 0.95, ["algodao", "malha"]),
    ("Fiação Serra Verde", "SC", "Brusque", 14, 0.92, ["algodao", "malha", "jeans"]),
    ("Têxtil Rio Claro", "SP", "Americana", 10, 0.90, ["sintetico", "viscose"]),
    ("Linhos do Nordeste", "CE", "Fortaleza", 25, 0.80, ["linho"]),
    ("Estamparia Aquarela", "SP", "São Paulo", 9, 0.88, ["viscose", "algodao"]),
    ("Malharia Monte Alto", "MG", "Juiz de Fora", 15, 0.86, ["malha"]),
    ("Chitas Agreste", "PE", "Caruaru", 28, 0.62, ["algodao"]),  # fornecedor de chita pouco confiável
    ("Denim Paraná", "PR", "Maringá", 18, 0.91, ["jeans"]),
    ("Importadora Seda Leste", "SP", "São Paulo", 35, 0.75, ["sintetico", "viscose", "linho"]),
    ("Tecidos Itajaí", "SC", "Gaspar", 11, 0.93, ["algodao", "sintetico"]),
    ("Viscose Bandeirante", "SP", "Santa Bárbara d'Oeste", 13, 0.89, ["viscose", "linho"]),
    ("Brim Minas", "MG", "Divinópolis", 16, 0.87, ["jeans", "algodao"]),
    ("Ateliê Têxtil Sul", "RS", "Caxias do Sul", 20, 0.84, ["malha", "sintetico"]),
    ("Tecelagem Horizonte", "GO", "Jaraguá", 14, 0.90, ["jeans", "malha"]),
]

METROS_ROLO = {"malha": 25.0, "default": 50.0}


@dataclass
class Catalogo:
    categorias: pd.DataFrame
    fornecedores: pd.DataFrame
    produtos: pd.DataFrame
    variantes: pd.DataFrame  # inclui colunas internas (prefixo _)
    preco_tabela: np.ndarray  # [variante, dia]
    preco_promo: np.ndarray   # [variante, dia] NaN = sem promoção
    custo: np.ndarray         # [variante, dia]
    historico: pd.DataFrame
    sazonalidade: np.ndarray  # [variante, dia] multiplicador de preferência
    ativo: np.ndarray         # [variante, dia] bool (lançado e não descontinuado)


def gerar_catalogo() -> Catalogo:
    rng = CFG.rng("catalogo")
    fk = Faker("pt_BR")
    fk.seed_instance(CFG.seed)
    datas = CFG.datas
    nd = len(datas)

    # ---------------- categorias
    cats = []
    for fam, (fid, nome) in FAMILIAS.items():
        cats.append((fid, None, nome, _slug(nome)))
    sub_id = {}
    for i, s in enumerate(SUBCATS):
        cid = 100 + i
        sub_id[s[0]] = cid
        cats.append((cid, FAMILIAS[s[2]][0], s[1], _slug(FAMILIAS[s[2]][1] + "-" + s[1])))
    categorias = pd.DataFrame(cats, columns=["categoria_id", "categoria_pai_id", "nome", "slug"])
    categorias["categoria_pai_id"] = categorias["categoria_pai_id"].astype("Int64")

    # ---------------- fornecedores
    forn = []
    for i, (fant, uf, cidade, prazo, conf, _) in enumerate(FORNECEDORES_BASE, start=1):
        forn.append({
            "fornecedor_id": i,
            "razao_social": f"{fant} {rng.choice(['Indústria Têxtil Ltda', 'Comércio de Tecidos Ltda', 'S.A.', 'Têxtil Eireli'])}",
            "nome_fantasia": fant,
            "cnpj": doc_ficticio(fk.cnpj()),
            "uf": uf, "cidade": cidade,
            "prazo_reposicao_dias": prazo,
            "confiabilidade": conf,
            "ativo": 1,
        })
    fornecedores = pd.DataFrame(forn)
    forn_por_fam = {f: [i + 1 for i, fb in enumerate(FORNECEDORES_BASE) if f in fb[5]] for f in FAMILIAS}

    # ---------------- produtos e variantes
    prods, vars_ = [], []
    pid, vid = 0, 0
    cores_nome = np.array([c for c, _ in CORES])
    cores_peso = np.array([w for _, w in CORES])
    est_nome = [e for e, _, _ in ESTAMPAS]
    est_peso = np.array([w for _, w, _ in ESTAMPAS])
    est_tema = {e: t for e, _, t in ESTAMPAS}

    for (chave, nome_sub, fam, saz, (pmin, pmax), (gmin, gmax), larg, comps, nprod, afin,
         aceita_rolo, variacao) in SUBCATS:
        linhas = rng.permutation(LINHAS)
        for k in range(nprod):
            pid += 1
            # Popularidade com cauda longa (curva ABC).
            pop = rng.lognormal(0, 0.9)
            preco_base = round(float(rng.uniform(pmin, pmax)), 1) - 0.1
            gram = int(rng.integers(gmin, gmax + 1) // 5 * 5)
            if variacao == "misto":
                tipo_var = "cor" if k % 2 == 0 else "estampa"
            else:
                tipo_var = variacao
            if chave == "chita":
                tipo_var = "estampa"
            sufixo = "Liso" if tipo_var == "cor" else "Estampado"
            if chave in ("chita", "viscose_estampada"):
                sufixo = ""
            linha = linhas[k % len(linhas)]
            if fam in ("linho", "jeans") and linha in ("Coleção Infantil", "Coleção Festa"):
                linha = "Coleção Atelier" if fam == "linho" else "Linha Profissional"
            nome = " ".join(x for x in [nome_sub.split(" e ")[0], sufixo, linha] if x)
            if k >= len(linhas):
                nome += f" {['II', 'III', 'IV'][min(k // len(linhas) - 1, 2)]}"
            # Lançamento: 80% já existiam; o resto entra ao longo do período.
            if rng.random() < 0.8:
                lancado = CFG.inicio - pd.Timedelta(days=int(rng.integers(30, 900)))
            else:
                lancado = datas[int(rng.integers(30, nd - 60))]
            # 8% descontinuados durante o período.
            descont = None
            if rng.random() < 0.08:
                ini = max(0, (lancado - CFG.inicio).days) + 120
                if ini < nd - 30:
                    descont = int(rng.integers(ini, nd - 10))
            forn_id = int(rng.choice(forn_por_fam[fam]))
            if chave == "chita":
                forn_id = 7 if rng.random() < 0.7 else forn_id  # Chitas Agreste
            prods.append({
                "produto_id": pid,
                "sku_base": f"{chave[:3].upper()}{pid:04d}",
                "nome": f"{nome}",
                "categoria_id": sub_id[chave],
                "fornecedor_id": forn_id,
                "composicao": str(rng.choice(comps)),
                "largura_cm": int(larg + rng.choice([-10, 0, 0, 0, 10])),
                "descricao": (f"{nome_sub} {sufixo.lower()} com {gram} g/m² e toque macio. "
                              f"Ideal para {_uso(fam, rng)}.") if rng.random() > 0.12 else None,
                "lancado_em": lancado.date(),
                "ativo": 0 if descont is not None else 1,
                "_descont_idx": descont,
                "_chave": chave, "_familia": fam, "_saz": saz,
            })

            # variantes
            if tipo_var == "cor":
                n = int(np.clip(rng.poisson(9 if chave not in ("linho_puro", "paete") else 6), 3, 22))
                p = cores_peso / cores_peso.sum()
                cores = rng.choice(cores_nome, size=min(n, len(cores_nome)), replace=False, p=p)
                combos = [(c, "Liso") for c in cores]
            else:
                n = int(np.clip(rng.poisson(5), 2, 10))
                if chave == "chita":
                    pool = [e for e in est_nome if est_tema[e] == "junino" or e.startswith("Floral")] + ["Patchwork"]
                else:
                    pool = [e for e in est_nome if not e.startswith("Chita")]
                pw = np.array([est_peso[est_nome.index(e)] for e in pool])
                ests = rng.choice(pool, size=min(n, len(pool)), replace=False, p=pw / pw.sum())
                combos = [(str(rng.choice(cores_nome[:12])) if rng.random() < 0.5 else "Colorido", e)
                          for e in ests]
            for cor, est in combos:
                pop_v = pop * (dict(CORES).get(cor, 1.0) if est == "Liso" else
                               est_peso[est_nome.index(est)]) * rng.lognormal(0, 0.35)
                g = gram + int(rng.integers(-1, 2)) * 5
                criado = max(lancado, CFG.inicio - pd.Timedelta(days=60))
                for formato in (["metro", "rolo"] if aceita_rolo and pop_v > 1.1 and rng.random() < 0.45
                                else ["metro"]):
                    vid += 1
                    mpu = 1.0 if formato == "metro" else METROS_ROLO.get(fam, METROS_ROLO["default"])
                    vars_.append({
                        "variante_id": vid,
                        "produto_id": pid,
                        "sku": f"{chave[:3].upper()}{pid:04d}-{vid:05d}{'-R' if formato == 'rolo' else ''}",
                        "cor": cor,
                        "estampa": est,
                        "gramatura_gm2": g,
                        "formato_venda": formato,
                        "metros_por_unidade": mpu,
                        "criado_em": criado.date(),
                        "ativo": 1,
                        "_preco_m": preco_base,
                        "_pop": pop_v * (0.35 if formato == "rolo" else 1.0),
                        "_afin": np.array(afin) * (np.array([0.01, 0.04, 0.10, 0.60]) if formato == "rolo"
                                                   else np.array([1, 1, 1, 0.7])),
                        "_familia": fam, "_saz": saz, "_tema": est_tema.get(est),
                        "_fornecedor_id": forn_id, "_chave": chave,
                        "_lanc_idx": max(0, (lancado - CFG.inicio).days),
                        "_descont_idx": descont,
                    })
    produtos = pd.DataFrame(prods)
    variantes = pd.DataFrame(vars_)
    nv = len(variantes)

    # ---------------- disponibilidade, sazonalidade
    idx = np.arange(nd)
    ativo = (idx[None, :] >= variantes["_lanc_idx"].values[:, None])
    desc = variantes["_descont_idx"].fillna(10**9).values.astype(int)
    ativo &= idx[None, :] < desc[:, None]
    saz = np.ones((nv, nd))
    for s in variantes["_saz"].unique():
        m = variantes["_saz"].values == s
        saz[m] *= mult_categoria(s, datas)[None, :]
    for tema, curva in SAZ_ESTAMPA.items():
        if tema is None:
            continue
        m = variantes["_tema"].values == tema
        saz[m] *= np.asarray(curva)[datas.month.values - 1][None, :]

    # ---------------- preços: reajustes de fornecedor + promoções
    preco_m = variantes["_preco_m"].values.astype(float)
    mpu = variantes["metros_por_unidade"].values.astype(float)
    desc_rolo = np.where(variantes["formato_venda"].values == "rolo", 0.78, 1.0)
    base_unit = preco_m * mpu * desc_rolo
    markup = rng.uniform(1.9, 2.5, size=nv)  # varejo de tecidos: markup ~2x
    preco_tabela = np.repeat(base_unit[:, None], nd, axis=1)
    custo = np.repeat((base_unit / markup)[:, None], nd, axis=1)
    eventos_preco = []  # (variante_idx, dia_idx, motivo)

    # Reajustes por fornecedor (2 por ano, 3-11%). O custo sobe junto; o preço
    # de tabela sobe alguns dias depois.
    forn_v = variantes["_fornecedor_id"].values
    for f in fornecedores["fornecedor_id"]:
        dias_reaj = sorted(rng.choice(np.arange(60, nd - 20), size=4, replace=False))
        mv = forn_v == f
        for dr in dias_reaj:
            aum = rng.uniform(0.025, 0.065)
            custo[mv, dr:] *= (1 + aum)
            lag = int(rng.integers(3, 15))
            preco_tabela[mv, min(dr + lag, nd - 1):] *= (1 + aum * rng.uniform(0.7, 1.1))
            for v in np.where(mv)[0]:
                eventos_preco.append((v, min(dr + lag, nd - 1), "reajuste_fornecedor"))

    # Preço "psicológico": arredonda para ,90.
    preco_tabela = np.floor(preco_tabela) + 0.9
    custo = np.round(custo, 2)

    preco_promo = np.full((nv, nd), np.nan)

    def promo(ini: str, fim: str, frac: float, desc_min: float, desc_max: float, filtro=None):
        a = int((pd.Timestamp(ini) - CFG.inicio).days)
        b = int((pd.Timestamp(fim) - CFG.inicio).days)
        if b < 0 or a >= nd:
            return
        a, b = max(a, 0), min(b, nd - 1)
        elegiveis = np.where(filtro if filtro is not None else np.ones(nv, bool))[0]
        sel = elegiveis[rng.random(len(elegiveis)) < frac]
        d_ = rng.uniform(desc_min, desc_max, size=len(sel))
        for v, dd in zip(sel, d_):
            preco_promo[v, a:b + 1] = np.floor(preco_tabela[v, a:b + 1] * (1 - dd)) + 0.9
            eventos_preco.append((v, a, "promocao"))
            if b + 1 < nd:
                eventos_preco.append((v, b + 1, "fim_promocao"))

    fam_v = variantes["_familia"].values
    for bf in BLACK_FRIDAY:
        t = pd.Timestamp(bf)
        promo(str((t - pd.Timedelta(days=4)).date()), str((t + pd.Timedelta(days=3)).date()), 0.55, 0.15, 0.35)
    for ano in (2024, 2025, 2026):
        promo(f"{ano}-03-13", f"{ano}-03-16", 0.30, 0.10, 0.20)
        promo(f"{ano}-05-22", f"{ano}-05-26", 0.45, 0.12, 0.25)
        promo(f"{ano}-05-01", f"{ano}-05-12", 0.6, 0.08, 0.15, variantes["_chave"].values == "chita")
        # Queima de coleção: malha no fim do inverno, linho/viscose no fim do verão.
        promo(f"{ano}-08-20", f"{ano}-09-15", 0.35, 0.20, 0.40, fam_v == "malha")
        promo(f"{ano}-03-25", f"{ano}-04-20", 0.30, 0.20, 0.35, np.isin(fam_v, ["linho", "viscose"]))
    for ano in (2023, 2024, 2025):
        promo(f"{ano}-12-26", f"{ano + 1}-01-10", 0.25, 0.20, 0.40)

    # Variantes descontinuadas: queima de estoque nos 30 dias finais.
    for v in np.where(~np.isnan(variantes["_descont_idx"].astype(float).values))[0]:
        dfim = int(variantes["_descont_idx"].iloc[v])
        a = max(dfim - 30, 0)
        preco_promo[v, a:dfim] = np.floor(preco_tabela[v, a:dfim] * 0.7) + 0.9
        eventos_preco.append((v, a, "queima_estoque"))

    historico = _historico(variantes, preco_tabela, preco_promo, custo, eventos_preco)

    variantes["preco_atual"] = preco_tabela[:, -1].round(2)
    variantes["custo_atual"] = custo[:, -1].round(2)
    variantes.loc[~ativo[:, -1], "ativo"] = 0

    return Catalogo(categorias, fornecedores, produtos, variantes, preco_tabela, preco_promo,
                    custo, historico, saz, ativo)


def _historico(variantes, preco_tabela, preco_promo, custo, eventos):
    """Converte as séries diárias em linhas SCD2 (uma por mudança)."""
    datas = CFG.datas
    nd = len(datas)
    linhas = []
    motivo_em = {}
    for v, d, m in eventos:
        motivo_em[(v, d)] = m
    for v in range(len(variantes)):
        pt, pp, c = preco_tabela[v], preco_promo[v], custo[v]
        ini = int(variantes["_lanc_idx"].iloc[v])
        estado = None
        seg_ini = ini
        for d in range(ini, nd):
            e = (round(pt[d], 2), None if np.isnan(pp[d]) else round(pp[d], 2), round(c[d], 2))
            if estado is None:
                estado = e
                seg_ini = d
                motivo = "lancamento"
                continue
            if e != estado:
                linhas.append((v, estado, seg_ini, d - 1, motivo))
                motivo = motivo_em.get((v, d), "reajuste_fornecedor" if e[2] != estado[2] else
                                       ("promocao" if e[1] is not None else "fim_promocao"))
                estado, seg_ini = e, d
        linhas.append((v, estado, seg_ini, None, motivo))
    out = pd.DataFrame({
        "historico_preco_id": np.arange(1, len(linhas) + 1),
        "variante_id": [variantes["variante_id"].iloc[v] for v, *_ in linhas],
        "preco": [e[0] for _, e, *_ in linhas],
        "preco_promocional": [e[1] for _, e, *_ in linhas],
        "custo": [e[2] for _, e, *_ in linhas],
        # Lançamentos anteriores ao início do período começam na data de criação.
        "vigente_de": [datas[a].date() if not (m == "lancamento" and a == 0) else
                       variantes["criado_em"].iloc[v] for v, _, a, _, m in linhas],
        "vigente_ate": [datas[b].date() if b is not None else None for *_, b, _ in linhas],
        "motivo": [m for *_, m in linhas],
    })
    return out


def _slug(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return "".join(ch if ch.isalnum() else "-" for ch in s).strip("-").replace("--", "-")


def _uso(fam, rng):
    usos = {
        "algodao": ["patchwork, vestidos e roupas infantis", "artesanato e acessórios", "camisas e vestidos"],
        "linho": ["alfaiataria leve e peças de verão", "vestidos, calças e camisas"],
        "viscose": ["vestidos, saias e batas", "peças fluidas de verão"],
        "malha": ["camisetas, moletons e peças de inverno", "roupas fitness e básicas"],
        "sintetico": ["fantasias e decoração", "forros, uniformes e festas"],
        "jeans": ["calças, jaquetas e uniformes", "bermudas e peças resistentes"],
    }
    return str(rng.choice(usos[fam]))
