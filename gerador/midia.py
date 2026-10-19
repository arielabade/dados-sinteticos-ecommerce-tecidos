"""Estrutura de contas/campanhas e entrega diária de Meta Ads e Google Ads.

Cada campanha tem uma *eficiência* verdadeira (efeito incremental por real
investido). Ela não aparece nas tabelas: só se revela nos pedidos. É isso que
cria campanhas que funcionam e campanhas que não funcionam, e permite ao MMM
recuperar a verdade guardada em data/verdade/.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .calendario import BLACK_FRIDAY
from .config import CFG

CANAIS_MMM = ["meta_prospeccao", "meta_remarketing", "google_marca", "google_search",
              "google_shopping_pmax", "google_demand_gen"]

FIM = str(CFG.fim.date())

# nome, objetivo, estratégia, canal MMM, início, fim, orçamento/dia (R$, escala 1), eficiência
META_CAMPANHAS = [
    ("[PROSP] Interesses Costura e Artesanato", "OUTCOME_SALES", "prospeccao", "meta_prospeccao", "2023-10-01", "2025-03-31", 470, 1.00),
    ("[PROSP] Lookalike 3% Compradores", "OUTCOME_SALES", "prospeccao", "meta_prospeccao", "2023-10-01", FIM, 360, 1.10),
    ("[PROSP] Advantage+ Shopping Catálogo", "OUTCOME_SALES", "advantage_plus", "meta_prospeccao", "2024-02-15", FIM, 560, 1.15),
    ("[PROSP] Reels Tutoriais de Costura", "OUTCOME_SALES", "prospeccao", "meta_prospeccao", "2024-05-06", FIM, 330, 1.55),
    ("[TESTE] Interesses Moda Amplo", "OUTCOME_SALES", "teste", "meta_prospeccao", "2024-09-02", "2024-11-10", 400, 0.30),
    ("[TESTE] Tráfego para o Blog", "OUTCOME_TRAFFIC", "teste", "meta_prospeccao", "2025-02-03", "2025-04-27", 260, 0.15),
    ("[RMKT] Catálogo Dinâmico Visitantes 14d", "OUTCOME_SALES", "catalogo", "meta_remarketing", "2023-10-01", FIM, 260, 1.00),
    ("[RMKT] Carrinho Abandonado 7d", "OUTCOME_SALES", "remarketing", "meta_remarketing", "2023-10-01", FIM, 140, 1.00),
    ("[SAZ] Black Friday 2023", "OUTCOME_SALES", "sazonal", "meta_prospeccao", "2023-11-06", "2023-11-28", 750, 1.00),
    ("[SAZ] Black Friday 2024", "OUTCOME_SALES", "sazonal", "meta_prospeccao", "2024-11-08", "2024-12-03", 850, 1.20),
    ("[SAZ] Black Friday 2025", "OUTCOME_SALES", "sazonal", "meta_prospeccao", "2025-11-07", "2025-12-02", 950, 1.05),
    ("[SAZ] Festa Junina 2024 Chitas", "OUTCOME_SALES", "sazonal", "meta_prospeccao", "2024-04-29", "2024-06-24", 380, 1.70),
    ("[SAZ] Festa Junina 2025 Chitas e Xadrez", "OUTCOME_SALES", "sazonal", "meta_prospeccao", "2025-04-28", "2025-06-24", 420, 1.50),
    ("[SAZ] Festa Junina 2026", "OUTCOME_SALES", "sazonal", "meta_prospeccao", "2026-04-27", "2026-06-24", 450, 1.35),
    ("[SAZ] Natal 2024 Catálogo Amplo", "OUTCOME_SALES", "sazonal", "meta_prospeccao", "2024-11-25", "2024-12-20", 650, 0.30),
    ("[SAZ] Natal 2025 Kits Presente", "OUTCOME_SALES", "sazonal", "meta_prospeccao", "2025-11-28", "2025-12-19", 420, 1.00),
    ("[SAZ] Dia das Mães 2025 Vídeo", "OUTCOME_SALES", "sazonal", "meta_prospeccao", "2025-04-20", "2025-05-11", 360, 1.30),
    ("[SAZ] Volta às Aulas 2026", "OUTCOME_SALES", "sazonal", "meta_prospeccao", "2026-01-12", "2026-02-20", 320, 0.90),
]
# Teste de incrementalidade: toda a prospecção da Meta pausada por 3 semanas.
PAUSA_META_PROSP = ("2025-08-04", "2025-08-24")

# nome, tipo, lance, roas alvo, marca?, canal MMM, início, fim, orçamento/dia, eficiência, grupos
GOOGLE_CAMPANHAS = [
    ("Search | Marca", "SEARCH", "MAXIMIZE_CONVERSIONS", None, 1, "google_marca", "2023-10-01", FIM, 95, 1.0,
     [("Marca - Exata", ["tecelã tecidos", "tecela tecidos", "loja tecelã", "tecelã tecidos online"]),
      ("Marca - Frase", ["tecelã tecidos frete", "tecelã tecidos cupom", "site tecelã"])]),
    ("Search | Tecidos por Metro", "SEARCH", "TARGET_ROAS", 5.0, 0, "google_search", "2023-10-01", FIM, 460, 1.0,
     [("Linho", ["linho por metro", "tecido linho", "comprar linho puro", "linho misto metro"]),
      ("Tricoline", ["tricoline estampado", "tricoline por metro", "tecido tricoline liso"]),
      ("Viscose", ["viscose estampada", "tecido viscose metro", "viscolinho"]),
      ("Malha e Moletom", ["malha pv metro", "suedine", "moletom por metro", "ribana"]),
      ("Jeans e Sarja", ["tecido jeans metro", "sarja por metro", "brim"]),
      ("Tecido Online Amplo", ["loja de tecidos online", "comprar tecido online", "tecidos baratos"]),
      ("Chita", ["chita por metro", "tecido chita festa junina", "chita floral"])]),
    ("Search | Concorrentes", "SEARCH", "MANUAL_CPC", None, 0, "google_search", "2024-03-04", "2024-08-30", 180, 0.30,
     [("Concorrentes", ["loja de tecidos sp", "tecidos 25 de março online", "armarinho online"])]),
    ("Shopping | Catálogo", "SHOPPING", "TARGET_ROAS", 6.0, 0, "google_shopping_pmax", "2023-10-01", "2024-06-30", 560, 1.0,
     [("Todos os produtos", None), ("Mais vendidos", None)]),
    ("PMax | Catálogo Completo", "PERFORMANCE_MAX", "MAXIMIZE_CONVERSION_VALUE", 6.0, 0, "google_shopping_pmax", "2024-06-10", FIM, 700, 0.95,
     [("Asset group - Tecidos Planos", None), ("Asset group - Malhas", None), ("Asset group - Linho Premium", None)]),
    ("PMax | Festa Junina 2025", "PERFORMANCE_MAX", "MAXIMIZE_CONVERSION_VALUE", None, 0, "google_shopping_pmax", "2025-04-22", "2025-06-26", 220, 1.30,
     [("Asset group - Chitas e Xadrez", None)]),
    ("Demand Gen | Vídeos YouTube", "DEMAND_GEN", "MAXIMIZE_CONVERSIONS", None, 0, "google_demand_gen", "2025-05-05", "2025-10-05", 320, 0.25,
     [("Público - Interesse em costura", None), ("Público - Semelhantes a compradores", None)]),
]

FATOR_ORCAMENTO = 0.88  # ajuste fino do nível de investimento total

TEMAS = ["Lançamento de coleção", "Tutorial de costura", "Antes e depois", "Depoimento de cliente",
         "Promoção relâmpago", "Frete grátis", "Kit de tecidos", "Bastidores do ateliê",
         "Paleta de cores da estação", "Catálogo dinâmico"]


@dataclass
class Midia:
    meta_contas: pd.DataFrame
    meta_campanhas: pd.DataFrame
    meta_conjuntos: pd.DataFrame
    meta_anuncios: pd.DataFrame   # + colunas internas: _eff, _canal, _campanha_idx
    meta_entrega: pd.DataFrame    # data, anuncio_id, investimento, impressoes, alcance, cliques_todos, cliques_link
    google_contas: pd.DataFrame
    google_campanhas: pd.DataFrame
    google_grupos: pd.DataFrame   # + _eff, _canal
    google_palavras: pd.DataFrame  # + _peso
    google_entrega: pd.DataFrame  # data, grupo_id, investimento, impressoes, cliques, parcela_impressoes
    google_kw_entrega: pd.DataFrame
    investimento_canal: pd.DataFrame      # [data x canal] investimento
    investimento_efetivo: pd.DataFrame    # [data x canal] investimento x eficiência


def _ativo(datas, ini, fim):
    return (datas >= pd.Timestamp(ini)) & (datas <= pd.Timestamp(fim))


def _sazonal_orcamento(datas: pd.DatetimeIndex) -> np.ndarray:
    """Gestores sobem orçamento em datas fortes."""
    m = np.ones(len(datas))
    for bf in BLACK_FRIDAY:
        t = pd.Timestamp(bf)
        m[(datas >= t - pd.Timedelta(days=10)) & (datas <= t + pd.Timedelta(days=3))] *= 1.6
    m[(datas.month == 12) & (datas.day > 20)] *= 0.6
    m[(datas.month == 1) & (datas.day < 8)] *= 0.7
    m[(datas.month == 5) | ((datas.month == 6) & (datas.day < 25))] *= 1.15
    return m


def _cpm_sazonal(datas):
    """Leilão mais caro no 4º trimestre."""
    m = np.ones(len(datas))
    m[datas.month == 11] = 1.35
    m[datas.month == 12] = 1.25
    for bf in BLACK_FRIDAY:
        t = pd.Timestamp(bf)
        m[(datas >= t - pd.Timedelta(days=3)) & (datas <= t + pd.Timedelta(days=3))] = 1.7
    return m


def gerar_midia() -> Midia:
    rng = CFG.rng("midia")
    datas = CFG.datas
    nd = len(datas)
    t_anos = np.arange(nd) / 365.25
    cresc_orc = 1.24 ** t_anos  # orçamento cresce ~24% a.a.
    saz_orc = _sazonal_orcamento(datas)
    cpm_saz = _cpm_sazonal(datas)
    esc = CFG.escala * FATOR_ORCAMENTO

    # ------------------------------------------------------------------ META
    meta_contas = pd.DataFrame([{"conta_id": "act_1029384756102938", "nome": "Tecelã Tecidos - Principal",
                                 "moeda": "BRL", "fuso_horario": "America/Sao_Paulo"}])
    camp_rows, conj_rows, ad_rows, entrega = [], [], [], []
    cid_base, sid_base, aid_base = 120200000000000000, 120210000000000000, 120220000000000000
    n_cj, n_ad = 0, 0
    for ci, (nome, obj, estr, canal, ini, fim, orc, eff) in enumerate(META_CAMPANHAS):
        cid = cid_base + (ci + 1) * 7919
        fim_ts = pd.Timestamp(fim)
        status = "ACTIVE" if fim_ts >= CFG.fim else ("PAUSED" if estr in ("prospeccao", "teste") else "ARCHIVED")
        camp_rows.append({"campanha_id": cid, "conta_id": meta_contas.conta_id[0], "nome": nome,
                          "objetivo": obj, "estrategia": estr, "status": status,
                          "orcamento_diario": float(orc) if estr in ("advantage_plus", "sazonal", "teste") else None,
                          "inicio": pd.Timestamp(ini).date(), "fim": None if fim_ts >= CFG.fim else fim_ts.date()})
        ativo = _ativo(datas, ini, fim)
        if canal == "meta_prospeccao" and estr != "sazonal":
            ativo &= ~_ativo(datas, *PAUSA_META_PROSP)
        orc_dia = orc * esc * cresc_orc * saz_orc * rng.lognormal(0, 0.08, nd) * ativo
        if estr == "sazonal":
            orc_dia = orc * esc * rng.lognormal(0, 0.08, nd) * ativo * np.where(
                np.isin(datas, pd.to_datetime(BLACK_FRIDAY)), 1.8, 1.0)
        # conjuntos
        publicos = {
            "prospeccao": ["Interesse: costura, corte e costura, moda autoral", "Lookalike 3% compradores 180d",
                           "Interesse: artesanato, patchwork", "Amplo 25-55 mulheres"],
            "advantage_plus": ["Advantage+ público amplo"],
            "catalogo": ["Visitantes 14d sem compra", "Visualizaram produto 7d"],
            "remarketing": ["Adicionaram ao carrinho 7d"],
            "sazonal": ["Amplo + interesse costura", "Lookalike compradores 1%"],
            "teste": ["Interesse: moda feminina, tendências", "Amplo 18-65"],
        }[estr]
        ncj = 1 if estr in ("advantage_plus", "remarketing") else int(rng.integers(1, min(3, len(publicos)) + 1))
        pesos_cj = rng.dirichlet(np.ones(ncj) * 3)
        for j in range(ncj):
            n_cj += 1
            sid = sid_base + n_cj * 6151
            conj_rows.append({"conjunto_id": sid, "campanha_id": cid,
                              "nome": f"{nome.split('] ')[-1]} | {publicos[j][:60]}",
                              "publico": publicos[j],
                              "otimizacao": "LINK_CLICKS" if obj == "OUTCOME_TRAFFIC" else
                              ("VALUE" if estr == "advantage_plus" else "OFFSITE_CONVERSIONS"),
                              "posicionamentos": "Advantage+ (automático)" if rng.random() < 0.7 else
                              "Instagram Feed, Stories, Reels",
                              "status": status})
            # anúncios com janelas escalonadas (renovação criativa)
            dur = max(int(ativo.sum()), 1)
            nads = int(np.clip(round(dur / 75), 2, 9)) if estr not in ("catalogo",) else 2
            idx_ativos = np.where(ativo)[0]
            for a in range(nads):
                n_ad += 1
                aid = aid_base + n_ad * 4099
                formato = "catalogo" if estr in ("catalogo", "advantage_plus") and a == 0 else \
                    str(rng.choice(["imagem", "video", "carrossel", "reels"], p=[0.3, 0.2, 0.25, 0.25]))
                if "Reels" in nome:
                    formato = "reels"
                tema = "Catálogo dinâmico" if formato == "catalogo" else str(rng.choice(TEMAS[:-1]))
                if "Tutoriais" in nome:
                    tema = "Tutorial de costura"
                q = rng.lognormal(0, 0.35) * (1.25 if tema in ("Tutorial de costura", "Depoimento de cliente") else 1)
                if len(idx_ativos):
                    lo = idx_ativos[0] + int(a * len(idx_ativos) / nads * 0.85)
                    hi = idx_ativos[-1] if a >= nads - 2 else min(idx_ativos[-1], lo + int(rng.integers(90, 240)))
                else:
                    lo = hi = 0
                camp_slug = f"{{{{campaign.id}}}}"
                ad_rows.append({"anuncio_id": aid, "conjunto_id": sid,
                                "nome": f"{formato.upper()} | {tema} | v{a + 1}",
                                "formato": formato, "tema_criativo": tema,
                                "url_destino": "https://www.tecelatecidos.com.br/?utm_source={{site_source_name}}"
                                               f"&utm_medium=paid_social&utm_campaign={camp_slug}"
                                               "&utm_content={{ad.id}}&utm_term={{adset.id}}",
                                "status": "ACTIVE" if hi >= nd - 1 and status == "ACTIVE" else "PAUSED",
                                "_lo": lo, "_hi": hi, "_q": q, "_eff": eff * q ** 0.5,
                                "_canal": canal, "_campanha_id": cid, "_conj_peso": pesos_cj[j],
                                "_orc_camp_idx": ci, "_estr": estr, "_obj": obj})
        camp_rows[-1]["_orc"] = orc_dia
    meta_campanhas = pd.DataFrame(camp_rows)
    meta_conjuntos = pd.DataFrame(conj_rows)
    meta_anuncios = pd.DataFrame(ad_rows)

    # entrega diária por anúncio
    dias_idx = np.arange(nd)
    for ci, camp in meta_campanhas.iterrows():
        ads = meta_anuncios[meta_anuncios._campanha_id == camp.campanha_id]
        orc = camp["_orc"]
        if orc.sum() == 0:
            continue
        # peso do anúncio: qualidade x fadiga (decai com a idade) x conjunto
        W = np.zeros((len(ads), nd))
        for k, (_, ad) in enumerate(ads.iterrows()):
            viva = (dias_idx >= ad._lo) & (dias_idx <= ad._hi)
            idade = np.clip(dias_idx - ad._lo, 0, None)
            W[k] = viva * ad._q * np.exp(-idade / 160) * ad._conj_peso
        tot = W.sum(0)
        sem_ad = tot == 0
        if sem_ad.any():  # garante que todo dia com orçamento tenha anúncio rodando
            W[-1, sem_ad] = 1
            tot = W.sum(0)
        share = W / tot
        estr = ads._estr.iloc[0]
        cpm_base = {"prospeccao": 21, "advantage_plus": 19, "catalogo": 27, "remarketing": 31,
                    "sazonal": 22, "teste": 17}[estr]
        ctr_base = {"prospeccao": 0.011, "advantage_plus": 0.012, "catalogo": 0.016, "remarketing": 0.019,
                    "sazonal": 0.012, "teste": 0.009}[estr]
        if ads._obj.iloc[0] == "OUTCOME_TRAFFIC":
            ctr_base, cpm_base = 0.024, 12
        freq = {"catalogo": 2.6, "remarketing": 3.1}.get(estr, 1.35)
        for k, (_, ad) in enumerate(ads.iterrows()):
            inv = orc * share[k] * rng.uniform(0.88, 1.0, nd)
            inv = np.round(inv, 2)
            m = inv >= 0.5
            if not m.any():
                continue
            cpm = cpm_base * cpm_saz * rng.lognormal(0, 0.12, nd)
            imp = np.floor(inv / cpm * 1000)
            idade = np.clip(dias_idx - ad._lo, 0, None)
            ctr = ctr_base * ad._q ** 0.4 * (0.75 + 0.25 * np.exp(-idade / 45)) * rng.lognormal(0, 0.15, nd)
            fmt_ctr = {"video": 0.85, "reels": 1.15, "carrossel": 1.05, "imagem": 0.95, "catalogo": 1.1}[ad.formato]
            cl_link = rng.binomial(imp.astype(np.int64), np.clip(ctr * fmt_ctr, 0, 0.2))
            cl_todos = np.floor(cl_link * rng.uniform(1.5, 2.4, nd)).astype(np.int64)
            alcance = np.floor(imp / (freq * rng.uniform(0.85, 1.15, nd))).astype(np.int64)
            entrega.append(pd.DataFrame({
                "data": datas[m], "anuncio_id": ad.anuncio_id, "investimento": inv[m],
                "impressoes": imp[m].astype(np.int64), "alcance": alcance[m],
                "cliques_todos": np.maximum(cl_todos[m], cl_link[m]), "cliques_link": cl_link[m],
                "_eff": ad._eff, "_canal": ad._canal}))
    meta_entrega = pd.concat(entrega, ignore_index=True)
    meta_campanhas = meta_campanhas.drop(columns=["_orc"])

    # ---------------------------------------------------------------- GOOGLE
    google_contas = pd.DataFrame([{"conta_id": "482-913-5570", "nome": "Tecelã Tecidos",
                                   "moeda": "BRL", "fuso_horario": "America/Sao_Paulo"}])
    gc_rows, gg_rows, kw_rows, g_ent, kw_ent = [], [], [], [], []
    gid, kid = 0, 0
    tipo_grupo = {"SEARCH": "SEARCH_STANDARD", "SHOPPING": "SHOPPING_PRODUCT_ADS",
                  "PERFORMANCE_MAX": "ASSET_GROUP", "DEMAND_GEN": "DEMAND_GEN"}
    for ci, (nome, tipo, lance, roas, marca, canal, ini, fim, orc, eff, grupos) in enumerate(GOOGLE_CAMPANHAS):
        cid = 21000000000 + (ci + 1) * 104729
        fim_ts = pd.Timestamp(fim)
        ativo = _ativo(datas, ini, fim)
        gc_rows.append({"campanha_id": cid, "conta_id": google_contas.conta_id[0], "nome": nome,
                        "tipo_canal": tipo, "estrategia_lance": lance, "roas_alvo": roas,
                        "campanha_marca": marca, "orcamento_diario": float(orc),
                        "status": "ENABLED" if fim_ts >= CFG.fim else "PAUSED",
                        "inicio": pd.Timestamp(ini).date(), "fim": None if fim_ts >= CFG.fim else fim_ts.date()})
        if marca:
            # busca de marca acompanha a demanda da loja, não o orçamento
            orc_dia = orc * esc * (1.30 ** t_anos) * saz_orc * rng.lognormal(0, 0.1, nd) * ativo
        else:
            orc_dia = orc * esc * cresc_orc * saz_orc * rng.lognormal(0, 0.08, nd) * ativo
        cpc_base = {"SEARCH": 0.45 if marca else 1.25, "SHOPPING": 0.95, "PERFORMANCE_MAX": 1.0,
                    "DEMAND_GEN": 0.52}[tipo]
        ctr_base = {"SEARCH": 0.26 if marca else 0.065, "SHOPPING": 0.012, "PERFORMANCE_MAX": 0.016,
                    "DEMAND_GEN": 0.0045}[tipo]
        pesos = rng.dirichlet(np.ones(len(grupos)) * 4)
        for gi, (gnome, kws) in enumerate(grupos):
            gid += 1
            grupo_id = 15000000000 + gid * 7333
            g_ativo = ativo.copy()
            peso_dia = np.full(nd, pesos[gi])
            if gnome == "Chita":
                g_ativo &= np.isin(datas.month, [4, 5, 6])
                peso_dia = peso_dia * 2.5
            g_eff = eff * (0.45 if gnome == "Tecido Online Amplo" else 1.25 if gnome in ("Linho", "Chita") else 1.0)
            gg_rows.append({"grupo_id": grupo_id, "campanha_id": cid, "nome": gnome, "tipo": tipo_grupo[tipo],
                            "status": gc_rows[-1]["status"], "_eff": g_eff, "_canal": canal,
                            "_marca": marca, "_tipo_canal": tipo, "_ativo": g_ativo, "_peso": peso_dia})
            if kws:
                kp = rng.dirichlet(np.ones(len(kws)) * 2)
                for kj, txt in enumerate(kws):
                    kid += 1
                    kw_rows.append({"palavra_chave_id": 300000000000 + kid * 977, "grupo_id": grupo_id,
                                    "texto": txt,
                                    "tipo_correspondencia": "EXACT" if "Exata" in gnome else
                                    str(rng.choice(["PHRASE", "BROAD", "EXACT"], p=[0.5, 0.3, 0.2])),
                                    "indice_qualidade": None if rng.random() < 0.15 else
                                    int(np.clip(rng.normal(9 if marca else 6, 1.5), 1, 10)),
                                    "status": gc_rows[-1]["status"], "_peso": kp[kj]})
        # distribui orçamento da campanha entre grupos ativos
        grupos_c = [g for g in gg_rows if g["campanha_id"] == cid]
        P = np.array([g["_peso"] * g["_ativo"] for g in grupos_c])
        P = P / np.where(P.sum(0) == 0, 1, P.sum(0))
        for k, g in enumerate(grupos_c):
            inv = np.round(orc_dia * P[k] * rng.uniform(0.9, 1.0, nd), 2)
            m = inv >= 0.5
            if not m.any():
                continue
            cpc = cpc_base * cpm_saz ** 0.6 * rng.lognormal(0, 0.12, nd)
            cliques = np.floor(inv / cpc).astype(np.int64)
            ctr = ctr_base * rng.lognormal(0, 0.15, nd)
            imp = np.maximum(np.floor(cliques / ctr), cliques).astype(np.int64)
            share = np.clip(rng.normal(0.92 if g["_marca"] else 0.55, 0.06, nd), 0.1, 0.99) \
                if tipo == "SEARCH" else np.full(nd, np.nan)
            df = pd.DataFrame({"data": datas[m], "grupo_id": g["grupo_id"], "investimento": inv[m],
                               "impressoes": imp[m], "cliques": cliques[m],
                               "parcela_impressoes": np.round(share[m], 4),
                               "_eff": g["_eff"], "_canal": canal})
            g_ent.append(df)
            kws_g = [k_ for k_ in kw_rows if k_["grupo_id"] == g["grupo_id"]]
            if kws_g:
                kp = np.array([k_["_peso"] for k_ in kws_g])
                for k_, p_ in zip(kws_g, kp):
                    pass
                # cliques por palavra: multinomial, investimento proporcional com CPC variando
                cl = df["cliques"].values
                mult = np.array([rng.multinomial(c, kp) for c in cl])
                cpc_fator = rng.lognormal(0, 0.25, len(kws_g))
                inv_k = mult * cpc_fator[None, :]
                inv_k = inv_k / np.where(inv_k.sum(1, keepdims=True) == 0, 1, inv_k.sum(1, keepdims=True)) \
                    * df["investimento"].values[:, None]
                imp_k = np.array([rng.multinomial(i, kp) for i in df["impressoes"].values])
                imp_k = np.maximum(imp_k, mult)
                for j, k_ in enumerate(kws_g):
                    kw_ent.append(pd.DataFrame({"data": df["data"].values, "palavra_chave_id": k_["palavra_chave_id"],
                                                "investimento": np.round(inv_k[:, j], 2),
                                                "impressoes": imp_k[:, j], "cliques": mult[:, j],
                                                "_grupo_id": g["grupo_id"]}))
    google_campanhas = pd.DataFrame(gc_rows)
    google_grupos = pd.DataFrame(gg_rows).drop(columns=["_ativo", "_peso"])
    google_palavras = pd.DataFrame(kw_rows)
    google_entrega = pd.concat(g_ent, ignore_index=True)
    google_kw_entrega = pd.concat(kw_ent, ignore_index=True)
    google_kw_entrega = google_kw_entrega[(google_kw_entrega.impressoes > 0)].reset_index(drop=True)
    # ajusta centavos para a soma por grupo bater com a tabela de grupo
    soma = google_kw_entrega.groupby(["data", "_grupo_id"]).investimento.transform("sum")
    ultimo = ~google_kw_entrega.duplicated(["data", "_grupo_id"], keep="last")
    alvo = google_kw_entrega.merge(google_entrega[["data", "grupo_id", "investimento"]].rename(
        columns={"grupo_id": "_grupo_id", "investimento": "_alvo"}), on=["data", "_grupo_id"], how="left")["_alvo"].values
    google_kw_entrega.loc[ultimo, "investimento"] = np.round(
        google_kw_entrega.loc[ultimo, "investimento"].values + (alvo - soma.values)[ultimo.values], 2)
    google_kw_entrega["investimento"] = google_kw_entrega["investimento"].clip(lower=0)

    # ---------------------------------------------------------- investimento por canal
    inv_canal = pd.DataFrame(0.0, index=datas, columns=CANAIS_MMM)
    inv_ef = pd.DataFrame(0.0, index=datas, columns=CANAIS_MMM)
    for df in (meta_entrega, google_entrega):
        g = df.assign(ef=df.investimento * df._eff).groupby(["data", "_canal"])[["investimento", "ef"]].sum()
        inv_canal = inv_canal.add(g["investimento"].unstack(fill_value=0), fill_value=0)
        inv_ef = inv_ef.add(g["ef"].unstack(fill_value=0), fill_value=0)

    return Midia(meta_contas, meta_campanhas, meta_conjuntos, meta_anuncios, meta_entrega,
                 google_contas, google_campanhas, google_grupos, google_palavras, google_entrega,
                 google_kw_entrega, inv_canal[CANAIS_MMM], inv_ef[CANAIS_MMM])
