"""Tracking server-side: jornadas, sessões, eventos GA4, cliques e envios
para Meta CAPI / Google Ads Enhanced Conversions.

Gera os dados mês a mês e grava direto em CSV para caber em pouca memória.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .catalogo import Catalogo
from .clientes import UF_LISTA, UF_PESO
from .config import CFG
from .exportar import Escritor
from .midia import Midia
from .pedidos import ResultadoPedidos

UTC_OFFSET = pd.Timedelta(hours=3)  # America/Sao_Paulo = UTC-3 (sem horário de verão desde 2019)
SITE = "https://www.tecelatecidos.com.br"

PAGOS = ["meta_prosp", "meta_rmkt", "g_marca", "g_search", "g_pmax", "g_dg"]
ORGANICOS = ["direct", "organic_search", "organic_social", "email", "whatsapp", "referral"]

# Defeito documentado: container sGTM v2.3 gravou event_timestamp em horário local.
BUG_TZ = (pd.Timestamp("2024-03-01"), pd.Timestamp("2024-06-15 23:59:59"))
# Incidente documentado: token da CAPI expirado após deploy do container v3.0.
INCIDENTE_CAPI = (pd.Timestamp("2025-07-14 15:00"), pd.Timestamp("2025-07-17 11:00"))
VERSOES = [(pd.Timestamp("2023-01-01"), "v2.1"), (pd.Timestamp("2024-03-01"), "v2.3"),
           (pd.Timestamp("2024-06-16"), "v2.4"), (pd.Timestamp("2025-07-14"), "v3.0"),
           (pd.Timestamp("2026-02-02"), "v3.1")]

TAXA_SESSAO_CLIQUE = {"meta": 0.70, "google": 0.88}


@dataclass
class Tracking:
    jornadas: pd.DataFrame      # toques das jornadas de pedidos rastreados (com sessao_id final)
    pedido_sessao: pd.Series    # pedido_id -> sessao_id da compra
    resumo: dict


# ---------------------------------------------------------------- utilidades
def _uuid_simples(rng, n):
    a = rng.integers(0, 2**62, size=n, dtype=np.int64)
    c = rng.integers(0, 2**62, size=n, dtype=np.int64)
    sa = [f"{x:016x}" for x in a]
    sc = [f"{x:016x}" for x in c]
    return np.array([f"{x[:8]}-{x[8:12]}-4{x[13:16]}-a{y[1:4]}-{y[4:16]}" for x, y in zip(sa, sc)], dtype=object)


def _token(rng, n, tam, alfabeto="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"):
    alf = np.array(list(alfabeto))
    m = alf[rng.integers(0, len(alf), size=(n, tam))]
    return np.array(["".join(r) for r in m], dtype=object)


def _int64_sentinela(arr) -> pd.arrays.IntegerArray:
    """IDs grandes (18 dígitos) não cabem em float: usa Int64 com -1 como nulo."""
    arr = np.asarray(arr, dtype=np.int64)
    out = pd.array(arr, dtype="Int64")
    out[arr < 0] = pd.NA
    return out


def _hash01(s: str) -> float:
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16) / 2**32


def _versao(ts_local: pd.Series) -> np.ndarray:
    out = np.full(len(ts_local), VERSOES[0][1], dtype=object)
    for ini, v in VERSOES:
        out[(ts_local >= ini).values] = v
    return out


# ---------------------------------------------------------------- entidades por dia
class Entidades:
    """Anúncios (Meta) e grupos (Google) ativos por dia e canal, para sortear cliques."""

    def __init__(self, midia: Midia):
        datas = CFG.datas
        ad = midia.meta_anuncios.set_index("anuncio_id")
        me = midia.meta_entrega.copy()
        me["key"] = np.where(me["_canal"] == "meta_prospeccao", "meta_prosp", "meta_rmkt")
        me["dia"] = (me["data"] - datas[0]).dt.days
        me["eid"] = me["anuncio_id"]
        me["cl"] = me["cliques_link"]
        ge = midia.google_entrega.merge(midia.google_grupos[["grupo_id", "_marca", "_tipo_canal"]], on="grupo_id")
        ge["key"] = np.select([ge._tipo_canal.eq("SEARCH") & ge._marca.eq(1), ge._tipo_canal.eq("SEARCH"),
                               ge._tipo_canal.eq("DEMAND_GEN")], ["g_marca", "g_search", "g_dg"], "g_pmax")
        ge["dia"] = (ge["data"] - datas[0]).dt.days
        ge["eid"] = ge["grupo_id"]
        ge["cl"] = ge["cliques"]
        self.tabela = pd.concat([me[["dia", "key", "eid", "cl", "_eff"]], ge[["dia", "key", "eid", "cl", "_eff"]]])
        self.tabela = self.tabela[self.tabela.cl > 0]
        self.idx = {}
        for (dia, key), g in self.tabela.groupby(["dia", "key"]):
            w_cl = g.cl.values.astype(float)
            w_ef = w_cl * g._eff.values
            w_mx = w_cl * np.sqrt(g._eff.values)
            self.idx[(dia, key)] = (g.eid.values, w_mx / w_mx.sum(), w_ef / w_ef.sum() if w_ef.sum() > 0 else w_cl / w_cl.sum())
        # palavra-chave por (dia, grupo)
        kw = midia.google_kw_entrega
        kw = kw[kw.cliques > 0].assign(dia=(kw["data"] - datas[0]).dt.days)
        self.kw = {(d, g): (x.palavra_chave_id.values, x.cliques.values / x.cliques.sum())
                   for (d, g), x in kw.groupby(["dia", "_grupo_id"])}
        self.kw_texto = midia.google_palavras.set_index("palavra_chave_id")["texto"].to_dict()

    def ativo(self, dia, key):
        return (dia, key) in self.idx

    def sorteia(self, rng, dia, key, por_eficiencia=True):
        ids, wc, we = self.idx[(dia, key)]
        return ids[rng.choice(len(ids), p=we if por_eficiencia else wc)]

    def palavra(self, rng, dia, grupo):
        k = self.kw.get((dia, grupo))
        if k is None:
            return None
        return k[0][rng.choice(len(k[0]), p=k[1])]


# ---------------------------------------------------------------- jornadas
ULTIMO_TOQUE_BASE = {"g_marca": 0.13, "meta_rmkt": 0.07, "g_pmax": 0.06, "g_search": 0.03,
                     "direct": 0.28, "organic_search": 0.20, "organic_social": 0.11,
                     "email": 0.07, "whatsapp": 0.04, "referral": 0.03}
ANTERIORES_NOVO = {"meta_prosp": 0.24, "organic_social": 0.15, "organic_search": 0.18, "g_search": 0.10,
                   "g_pmax": 0.10, "direct": 0.12, "referral": 0.05, "meta_rmkt": 0.06}
ANTERIORES_RET = {"direct": 0.30, "email": 0.18, "organic_search": 0.14, "meta_rmkt": 0.10, "g_marca": 0.10,
                  "organic_social": 0.10, "whatsapp": 0.05, "g_pmax": 0.03}
MOTOR_KEY = {"meta_prospeccao": "meta_prosp", "meta_remarketing": "meta_rmkt", "google_marca": "g_marca",
             "google_search": "g_search", "google_shopping_pmax": "g_pmax", "google_demand_gen": "g_dg",
             "tiktok": "tiktok", "afiliados": "afiliado", "email_crm": "email"}


def _sorteia_dict(rng, d: dict, excluir=()):
    ks = [k for k in d if k not in excluir]
    p = np.array([d[k] for k in ks], float)
    return ks[rng.choice(len(ks), p=p / p.sum())]


def construir_jornadas(rng, ped: ResultadoPedidos, ent: Entidades):
    P = ped.pedidos
    datas = CFG.datas
    rastreado = (P.canal_venda.values == "site") & (rng.random(len(P)) >= CFG.taxa_pedido_sem_rastreio)
    P = P.assign(_rastreado=rastreado)
    rows = []
    cols = list(P.columns)
    i_motor, i_novo, i_dia = cols.index("_motor"), cols.index("_novo"), cols.index("_dia")
    i_ts, i_pid, i_cli = cols.index("criado_em"), cols.index("pedido_id"), cols.index("cliente_id")
    for r in P[rastreado].itertuples(index=False, name=None):
        motor, novo, dia = r[i_motor], r[i_novo], r[i_dia]
        ts_compra_utc = r[i_ts] + UTC_OFFSET
        k = 1 + int(min(rng.geometric(0.45 if novo else 0.62) - 1, 7))
        toques = [None] * k
        view_through = False
        mk = MOTOR_KEY.get(motor)
        # ---- último toque
        if motor == "base":
            ult = _sorteia_dict(rng, ULTIMO_TOQUE_BASE, excluir=() if not novo else ("email",))
        elif motor == "meta_prospeccao":
            u = rng.random()
            if u < 0.55:
                ult = "meta_prosp"
            elif u < 0.80:
                view_through = True
                ult = _sorteia_dict(rng, {"direct": 0.4, "organic_social": 0.3, "organic_search": 0.2, "g_marca": 0.1})
            else:
                ult = _sorteia_dict(rng, {"direct": 0.35, "g_marca": 0.3, "meta_rmkt": 0.2, "organic_search": 0.15})
                if k == 1:
                    k += 1
                    toques = [None] * k
                toques[0] = "meta_prosp"
        elif motor == "tiktok":
            # vídeo curto: a maior parte da influência não passa por clique
            if rng.random() < 0.4:
                ult = "tiktok"
            else:
                view_through = True
                ult = _sorteia_dict(rng, {"direct": 0.35, "organic_social": 0.3, "organic_search": 0.25, "g_marca": 0.1})
        elif motor == "google_demand_gen":
            if rng.random() < 0.3:
                ult = "g_dg"
            else:
                view_through = True
                ult = _sorteia_dict(rng, {"direct": 0.4, "g_marca": 0.3, "organic_search": 0.3})
        else:
            p_ult = {"meta_remarketing": 0.75, "google_marca": 0.85, "google_search": 0.80,
                     "google_shopping_pmax": 0.80, "afiliados": 0.88, "email_crm": 0.85}[motor]
            ult = mk if rng.random() < p_ult else _sorteia_dict(rng, {"direct": 0.5, "g_marca": 0.3, "organic_search": 0.2})
            if ult != mk:
                toques[0] = mk if k > 1 else toques[0]
        toques[-1] = ult
        excl = ("meta_prosp", "meta_rmkt") if (view_through and motor.startswith("meta")) else ()
        for j in range(k - 1):
            if toques[j] is None:
                toques[j] = _sorteia_dict(rng, ANTERIORES_NOVO if novo else ANTERIORES_RET, excluir=excl)
        # ---- horários (UTC): compra no fim da última sessão
        dur_compra = float(rng.uniform(240, 1800))
        inicio = [ts_compra_utc - pd.Timedelta(seconds=dur_compra)]
        t = inicio[0]
        for j in range(k - 1):
            t = t - pd.Timedelta(hours=float(rng.exponential(60)) + 0.5)
            inicio.append(t)
        inicio = inicio[::-1]
        lim = datas[0] + pd.Timedelta(hours=3)
        for j in range(k):
            key = toques[j]
            ts = inicio[j]
            if ts < lim:
                continue
            dia_t = int((ts - UTC_OFFSET).normalize().value - datas[0].value) // 86_400_000_000_000
            dia_t = max(0, min(dia_t, len(datas) - 1))
            eid = kw = None
            if key in PAGOS:
                if ent.ativo(dia_t, key):
                    eid = ent.sorteia(rng, dia_t, key, por_eficiencia=(key == mk))
                    if key in ("g_marca", "g_search"):
                        kw = ent.palavra(rng, dia_t, eid)
                else:
                    key = "direct"
            rows.append((r[i_pid], r[i_cli], j + 1, k, key, ts, dia_t, -1 if eid is None else int(eid),
                         -1 if kw is None else int(kw), j == k - 1, novo,
                         dur_compra if j == k - 1 else np.nan, motor, view_through))
    J = pd.DataFrame(rows, columns=["pedido_id", "cliente_id", "posicao", "total_toques", "key", "inicio_utc", "dia",
                                    "eid", "kw", "compra", "novo", "dur_compra", "motor", "view_through"])
    J["eid"] = _int64_sentinela(J["eid"].values)
    J["kw"] = _int64_sentinela(J["kw"].values)
    # renumera posição após descartar toques anteriores ao período
    J["posicao"] = J.groupby("pedido_id").cumcount() + 1
    J["total_toques"] = J.groupby("pedido_id")["posicao"].transform("max")
    J["tmp"] = np.arange(len(J))
    return J, P


# ---------------------------------------------------------------- atributos de sessão
DISP_P = {"meta_prosp": [0.95, 0.04, 0.01], "meta_rmkt": [0.93, 0.06, 0.01], "g_marca": [0.80, 0.18, 0.02],
          "g_search": [0.76, 0.22, 0.02], "g_pmax": [0.86, 0.12, 0.02], "g_dg": [0.92, 0.06, 0.02],
          "direct": [0.84, 0.14, 0.02], "organic_search": [0.78, 0.20, 0.02], "organic_social": [0.96, 0.03, 0.01],
          "email": [0.80, 0.18, 0.02], "whatsapp": [0.97, 0.02, 0.01], "referral": [0.70, 0.28, 0.02],
          "tiktok": [0.97, 0.02, 0.01], "afiliado": [0.74, 0.24, 0.02]}

REF_BUSCA = (["https://www.google.com/", "https://www.bing.com/", "https://duckduckgo.com/", "https://br.search.yahoo.com/"],
             [0.90, 0.06, 0.03, 0.01])
REF_SOCIAL = (["https://l.instagram.com/", "https://www.instagram.com/", "https://m.facebook.com/",
               "https://br.pinterest.com/", "https://www.tiktok.com/", "https://www.youtube.com/"],
              [0.45, 0.15, 0.12, 0.12, 0.10, 0.06])
REF_SITES = ["https://blog.costuraemcasa.example/", "https://forum.patchwork.example/",
             "https://guia.moldes.example/", "https://www.comparador-precos.example/"]
REF_IA = ["https://chatgpt.com/", "https://www.perplexity.ai/", "https://gemini.google.com/"]


def preencher_atributos(rng, S: pd.DataFrame, ent: Entidades, midia_maps: dict, slugs_cat: np.ndarray,
                        skus: np.ndarray, pesos_sku: np.ndarray):
    """Preenche dispositivo, UTMs, click ids, consentimento, landing page etc. (vetorizado)."""
    n = len(S)
    key = S["key"].values
    data_local = (S["inicio_utc"] - UTC_OFFSET)

    # dispositivo / SO / navegador
    disp = np.empty(n, dtype=object)
    for k_, p in DISP_P.items():
        m = key == k_
        if m.any():
            disp[m] = rng.choice(["mobile", "desktop", "tablet"], size=m.sum(), p=p)
    so = np.where(disp == "desktop", rng.choice(["Windows", "Macintosh", "Linux", "ChromeOS"], n, p=[0.78, 0.16, 0.03, 0.03]),
                  rng.choice(["Android", "iOS"], n, p=[0.74, 0.26]))
    nav = np.where(so == "iOS", "Safari", np.where(disp == "desktop", rng.choice(["Chrome", "Edge", "Firefox", "Safari"], n, p=[0.72, 0.15, 0.05, 0.08]),
                                                    rng.choice(["Chrome", "Samsung Internet", "Firefox"], n, p=[0.84, 0.13, 0.03])))
    meta = np.isin(key, ["meta_prosp", "meta_rmkt"])
    inapp = meta & (rng.random(n) < 0.58)
    nav = np.where(inapp, np.where(rng.random(n) < 0.8, "Instagram App", "Facebook App"), nav)
    nav = np.where(key == "organic_social", np.where(rng.random(n) < 0.4, "Instagram App", nav), nav)
    nulo_disp = rng.random(n) < 0.008
    disp[nulo_disp] = None
    so = np.where(nulo_disp, None, so)
    nav = np.where(nulo_disp | (rng.random(n) < 0.004), None, nav)

    # UF
    uf = S["_uf"].values.copy() if "_uf" in S else np.full(n, None, dtype=object)
    sem = pd.isna(uf)
    uf[sem] = rng.choice(UF_LISTA, size=sem.sum(), p=UF_PESO)
    uf[rng.random(n) < 0.07] = None  # geolocalização falhou

    # landing page
    sku_rand = skus[rng.choice(len(skus), size=n, p=pesos_sku)]
    cat_rand = slugs_cat[rng.integers(0, len(slugs_cat), n)]
    lp_prod = np.char.add(f"{SITE}/produto/", np.char.lower(sku_rand.astype(str)))
    lp_cat = np.char.add(f"{SITE}/categoria/", cat_rand.astype(str))
    lp_home = np.full(n, f"{SITE}/", dtype=object)
    u = rng.random(n)
    p_prod = np.select([key == "g_pmax", meta, np.isin(key, ["g_search", "g_dg"]), key == "email"],
                       [0.92, 0.6, 0.25, 0.45], 0.25)
    p_cat = np.select([np.isin(key, ["g_search"]), meta, key == "direct"], [0.65, 0.25, 0.1], 0.35)
    landing = np.where(u < p_prod, lp_prod, np.where(u < p_prod + p_cat, lp_cat, lp_home)).astype(object)

    referrer = np.full(n, None, dtype=object)
    utm_s = np.full(n, None, dtype=object)
    utm_m = np.full(n, None, dtype=object)
    utm_c = np.full(n, None, dtype=object)
    utm_ct = np.full(n, None, dtype=object)
    utm_t = np.full(n, None, dtype=object)
    gclid = np.full(n, None, dtype=object)
    fbclid = np.full(n, None, dtype=object)

    # ---- Meta
    eid = S["eid"].values
    if meta.any():
        idx = np.where(meta)[0]
        perde = rng.random(len(idx)) < 0.12  # anúncio sem parâmetros / in-app removeu
        fb = _token(rng, len(idx), 60)
        fbclid[idx[~perde]] = np.char.add("IwAR", fb[~perde].astype(str)).astype(object)
        ok = idx[~perde]
        ads = eid[ok]
        camp = np.array([midia_maps["meta_ad_camp"][a] for a in ads])
        conj = np.array([midia_maps["meta_ad_conj"][a] for a in ads])
        nome = np.array([midia_maps["meta_camp_nome"][c] for c in camp], dtype=object)
        catalogo = np.array([midia_maps["meta_ad_fmt"][a] == "catalogo" for a in ads])
        src = rng.choice(["ig", "fb", "an", "instagram", "facebook", "Instagram"], len(ok),
                         p=[0.56, 0.24, 0.02, 0.07, 0.06, 0.05]).astype(object)
        src[catalogo & (rng.random(len(ok)) < 0.4)] = "IGShopping"
        med = rng.choice(["paid_social", "paid", "cpc", "Social"], len(ok), p=[0.72, 0.18, 0.05, 0.05])
        antes = (data_local.values[ok] < np.datetime64("2024-06-01"))
        cmp = np.where(antes, np.char.replace(np.char.lower(nome.astype(str)), " ", "_"), camp.astype(str))
        utm_s[ok], utm_m[ok], utm_c[ok] = src, med, cmp
        utm_ct[ok] = ads.astype(str)
        utm_t[ok] = conj.astype(str)
        # sem UTM: parte vira referral do Instagram, parte vira direto
        sem = idx[perde]
        referrer[sem] = np.where(rng.random(len(sem)) < 0.5, "https://l.instagram.com/", None)

    # ---- Google
    goo = np.isin(key, ["g_marca", "g_search", "g_pmax", "g_dg"])
    if goo.any():
        idx = np.where(goo)[0]
        perde = rng.random(len(idx)) < 0.03  # gclid perdido em redirecionamento
        gc = _token(rng, len(idx), 56)
        gclid[idx[~perde]] = np.char.add("Cj0KCQjw", gc[~perde].astype(str)).astype(object)
        referrer[idx] = "https://www.google.com/"
        manual = idx[(rng.random(len(idx)) < 0.55) & ~perde]
        utm_s[manual] = "google"
        utm_m[manual] = "cpc"
        grupos = eid[manual]
        utm_c[manual] = np.array([midia_maps["g_grupo_camp_nome"][g] for g in grupos], dtype=object)
        kws = S["kw"].values[manual]
        utm_t[manual] = np.array([ent.kw_texto.get(k_) if k_ is not None and not pd.isna(k_) else None for k_ in kws], dtype=object)

    # ---- Orgânicos
    m = key == "organic_search"
    referrer[m] = rng.choice(REF_BUSCA[0], m.sum(), p=REF_BUSCA[1])
    m = np.where(key == "organic_social")[0]
    referrer[m] = rng.choice(REF_SOCIAL[0], len(m), p=REF_SOCIAL[1])
    bio = m[rng.random(len(m)) < 0.5]
    utm_s[bio] = rng.choice(["ig", "instagram", "IG", "linktree"], len(bio), p=[0.6, 0.2, 0.1, 0.1])
    utm_m[bio] = rng.choice(["social", "Social", "bio", None], len(bio), p=[0.6, 0.2, 0.1, 0.1])
    utm_c[bio] = rng.choice(["bio_link", "stories", "destaque_frete"], len(bio))
    m = np.where(key == "email")[0]
    utm_s[m] = rng.choice(["newsletter", "email", "Email", "rdstation"], len(m), p=[0.5, 0.25, 0.1, 0.15])
    utm_m[m] = "email"
    ds = data_local.values[m].astype("datetime64[D]").astype(str)
    utm_c[m] = np.where(rng.random(len(m)) < 0.7, np.char.add("news_", np.char.replace(ds.astype(str), "-", "_")),
                        rng.choice(["carrinho_abandonado", "reativacao_90d", "boas_vindas"], len(m)))
    m = np.where(key == "whatsapp")[0]
    com_utm = m[rng.random(len(m)) < 0.6]
    utm_s[com_utm] = rng.choice(["whatsapp", "WhatsApp", "wpp"], len(com_utm), p=[0.7, 0.2, 0.1])
    utm_m[com_utm] = rng.choice(["social", "chat", "referral"], len(com_utm), p=[0.5, 0.3, 0.2])
    utm_c[com_utm] = "lista_transmissao"
    m = np.where(key == "referral")[0]
    ia = (data_local.values[m] >= np.datetime64("2025-01-01")) & (rng.random(len(m)) < 0.35)
    referrer[m] = np.where(ia, rng.choice(REF_IA, len(m), p=[0.75, 0.15, 0.10]), rng.choice(REF_SITES, len(m)))

    # ---- TikTok Ads (sem click id na tabela de sessões: só UTM)
    dia_s = S["dia"].values.astype(int)
    m = np.where(key == "tiktok")[0]
    if len(m):
        nomes, cum = midia_maps["tiktok_camp"]
        u = rng.random(len(m))
        escolha = np.argmax(cum[:, dia_s[m]] > u[None, :], axis=0)
        perde = rng.random(len(m)) < 0.10
        ok = m[~perde]
        utm_s[ok] = rng.choice(["tiktok", "TikTok", "tiktok_ads"], len(ok), p=[0.8, 0.12, 0.08])
        utm_m[ok] = rng.choice(["paid_social", "cpc"], len(ok), p=[0.85, 0.15])
        utm_c[ok] = nomes[escolha[~perde]]
        referrer[m] = np.where(rng.random(len(m)) < 0.3, "https://www.tiktok.com/", None)
    # ---- Afiliados: link com UTM do parceiro, vindo do site do parceiro
    m = np.where(key == "afiliado")[0]
    if len(m):
        slugs, dominios, cum = midia_maps["afiliados"]
        u = rng.random(len(m))
        escolha = np.argmax(cum[:, dia_s[m]] > u[None, :], axis=0)
        utm_s[m] = slugs[escolha]
        utm_m[m] = rng.choice(["afiliados", "affiliate"], len(m), p=[0.9, 0.1])
        utm_c[m] = "parceria"
        referrer[m] = dominios[escolha]

    # ---- identidade e consentimento
    cid_col = S["client_id"].values
    cons = S["_consent"].values  # 0 = tudo negado, 1 = só analytics, 2 = tudo concedido
    a_st = np.where(cons >= 1, "granted", "denied")
    ad_st = np.where(cons >= 2, "granted", "denied")
    ad_ud = np.where((cons >= 2) & (rng.random(n) > 0.03), "granted", "denied")
    ad_pz = np.where((cons >= 2) & (rng.random(n) > 0.08), "granted", "denied")
    client_id = np.where(cons >= 1, cid_col, None)
    ts_ms = (S["inicio_utc"].values.astype("datetime64[ms]").astype(np.int64))
    fbp = np.where(ad_st == "granted", np.char.add(np.char.add("fb.1.", (ts_ms - rng.integers(0, 10**9, n)).astype(str)),
                                                   np.char.add(".", rng.integers(10**9, 2 * 10**9, n).astype(str))), None).astype(object)
    tem_fbclid = pd.notna(fbclid)
    fbc = np.where(tem_fbclid & (ad_st == "granted"),
                   np.char.add(np.char.add(np.char.add("fb.1.", ts_ms.astype(str)), "."), fbclid.astype(str)), None).astype(object)

    S = S.assign(dispositivo=disp, sistema_operacional=so, navegador=nav, uf=uf, landing_page=landing,
                 referrer=referrer, utm_source=utm_s, utm_medium=utm_m, utm_campaign=utm_c, utm_content=utm_ct,
                 utm_term=utm_t, gclid=gclid, fbclid=fbclid, fbp=fbp, fbc=fbc, client_id=client_id,
                 consent_analytics_storage=a_st, consent_ad_storage=ad_st, consent_ad_user_data=ad_ud,
                 consent_ad_personalization=ad_pz)
    return S


# ---------------------------------------------------------------- principal
def _cum_por_dia(pesos: np.ndarray) -> np.ndarray:
    """Pesos [entidade x dia] -> distribuição acumulada por dia (para sortear vetorizado)."""
    tot = pesos.sum(0)
    w = pesos / np.where(tot == 0, 1, tot)
    w[:, tot == 0] = 1.0 / len(pesos)
    return np.cumsum(w, axis=0)


def _slug(s: str) -> str:
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def gerar_tracking(cat: Catalogo, midia: Midia, ped: ResultadoPedidos, cal: pd.DataFrame, esc: Escritor,
                   novos=None) -> Tracking:
    rng = CFG.rng("tracking")
    datas = CFG.datas
    nd = len(datas)
    ent = Entidades(midia)

    ad = midia.meta_anuncios
    conj = midia.meta_conjuntos.set_index("conjunto_id")["campanha_id"]
    midia_maps = {
        "meta_ad_camp": dict(zip(ad.anuncio_id, ad.conjunto_id.map(conj))),
        "meta_ad_conj": dict(zip(ad.anuncio_id, ad.conjunto_id)),
        "meta_ad_fmt": dict(zip(ad.anuncio_id, ad.formato)),
        "meta_camp_nome": dict(zip(midia.meta_campanhas.campanha_id, midia.meta_campanhas.nome)),
        "g_grupo_camp": dict(zip(midia.google_grupos.grupo_id, midia.google_grupos.campanha_id)),
        "g_grupo_tipo": dict(zip(midia.google_grupos.grupo_id, midia.google_grupos._tipo_canal)),
        "g_grupo_camp_nome": dict(zip(midia.google_grupos.grupo_id,
                                      midia.google_grupos.campanha_id.map(
                                          midia.google_campanhas.set_index("campanha_id")["nome"])
                                      .str.lower().str.replace(r"[^a-z0-9]+", "_", regex=True).str.strip("_"))),
    }
    # TikTok e afiliados: cliques diários por campanha/parceiro (sorteio das UTMs e sessões não conversoras)
    cli_tiktok = np.zeros(nd, np.int64)
    cli_afil = np.zeros(nd, np.int64)
    if novos is not None:
        te = novos.tiktok_entrega.assign(dia=lambda x: (x.data - datas[0]).dt.days)
        camp = novos.tiktok_campanhas.campanha_id.values
        Wt = np.zeros((len(camp), nd))
        for i, c in enumerate(camp):
            g = te[te.campanha_id == c]
            Wt[i, g.dia.values] = g.cliques.values
        midia_maps["tiktok_camp"] = (np.array([_slug(n) for n in novos.tiktok_campanhas.nome], dtype=object),
                                     _cum_por_dia(Wt))
        cli_tiktok = Wt.sum(0).astype(np.int64)
        ae = novos.afiliados_entrega.assign(dia=lambda x: (x.data - datas[0]).dt.days)
        par = novos.afiliados_parceiros
        Wa = np.zeros((len(par), nd))
        for i, pid in enumerate(par.parceiro_id.values):
            g = ae[ae.parceiro_id == pid]
            Wa[i, g.dia.values] = g.cliques.values
        midia_maps["afiliados"] = (np.array([_slug(n) for n in par.nome], dtype=object),
                                   np.array([f"https://www.{_slug(n).replace('_', '')}.example/" for n in par.nome],
                                            dtype=object),
                                   _cum_por_dia(Wa))
        cli_afil = Wa.sum(0).astype(np.int64)

    V = cat.variantes
    skus = np.asarray(V["sku"].tolist(), dtype=str)
    pesos_sku = (V["_pop"].values / V["_pop"].sum())
    slugs_cat = np.asarray(cat.categorias[cat.categorias.categoria_pai_id.notna()]["slug"].tolist(), dtype=str)
    var_id = V["variante_id"].values
    preco_ef = np.where(np.isnan(cat.preco_promo), cat.preco_tabela, cat.preco_promo)

    J, P = construir_jornadas(rng, ped, ent)

    clientes = ped.clientes
    c_uf = clientes["_uf"].values
    c_tel = clientes["telefone"].notna().values

    # dispositivos (client_id) por cliente e consentimento por client_id
    disp_cli: dict[int, list] = {}

    def client_ids_do_cliente(cli: int, ts_utc) -> str:
        lst = disp_cli.get(cli)
        if lst is None or (rng.random() < 0.06):  # ITP/limpeza de cookies gera novo client_id
            novo = f"{rng.integers(10**8, 2 * 10**9)}.{int(ts_utc.timestamp())}"
            lst = (lst or []) + [novo]
            disp_cli[cli] = lst[-3:]
            return novo
        return lst[int(rng.integers(0, len(lst)))] if rng.random() < 0.25 else lst[-1]

    def consent_de(cid: str) -> int:
        h = _hash01(cid)
        return 2 if h < 0.72 else (1 if h < 0.83 else 0)

    # ---- identidade das sessões das jornadas
    J = J.sort_values(["pedido_id", "posicao"]).reset_index(drop=True)
    J["tmp"] = np.arange(len(J))
    cids, ucli, consent = [], [], []
    for r in J.itertuples(index=False):
        mesmo_disp = r.compra or rng.random() < 0.75
        cid = client_ids_do_cliente(r.cliente_id, r.inicio_utc) if mesmo_disp else \
            f"{rng.integers(10**8, 2 * 10**9)}.{int(r.inicio_utc.timestamp())}"
        cids.append(cid)
        logado = r.compra or ((not r.novo) and rng.random() < 0.4)
        ucli.append(r.cliente_id if logado else None)
        consent.append(consent_de(cid))
    J["client_id"] = cids
    J["cliente_sessao"] = pd.array(ucli, dtype="Int64")
    J["_consent"] = consent
    J["_uf"] = c_uf[J["cliente_id"].values - 1]

    # ---- sessões pagas por entidade/dia (cliques -> sessões), descontando as de jornada
    usadas = J[J.eid.notna()].groupby(["dia", "eid"]).size()
    T = ent.tabela.copy()
    plat = np.where(T.key.str.startswith("meta"), "meta", "google")
    T["sess"] = rng.binomial(T.cl.values.astype(np.int64), np.where(plat == "meta", TAXA_SESSAO_CLIQUE["meta"],
                                                                    TAXA_SESSAO_CLIQUE["google"]))
    T = T.set_index(["dia", "eid"])
    T["usadas"] = usadas.reindex(T.index).fillna(0).values
    T["nc"] = np.maximum(T["sess"] - T["usadas"], 0).astype(np.int64)
    T = T.reset_index()

    # ---- tráfego não pago (não conversor)
    t_anos = np.arange(nd) / 365.25
    sazon = (cal["dia_semana"] * cal["eventos"] ** 0.7).values
    org_dia = 1500 * CFG.escala * (1.28 ** t_anos) * sazon * rng.lognormal(0, 0.06, nd)
    org_share = {"direct": 0.30, "organic_search": 0.28, "organic_social": 0.22, "email": 0.09,
                 "referral": 0.06, "whatsapp": 0.05}
    # e-mails disparados em dias de newsletter (ter/qui) geram picos
    news = np.isin(datas.dayofweek, [1, 3])

    # clientes adquiridos até cada dia (para sessões de clientes conhecidos)
    cad_dia = ((pd.to_datetime(clientes["cadastrado_em"]) - datas[0]).dt.days.values).clip(min=-1)

    # pedido -> sessão da compra
    pedido_sessao = {}
    prox_id = 1
    resumo = {"sessoes": 0, "eventos": 0, "envios": 0, "cliques": 0}
    J["sessao_id"] = np.int64(0)
    J["canal"] = None
    J["meta_campanha_id"] = pd.array([pd.NA] * len(J), dtype="Int64")
    J["google_campanha_id"] = pd.array([pd.NA] * len(J), dtype="Int64")
    J["consent_ad"] = None
    J["consent_aud"] = None
    canais_total: dict[str, int] = {}

    meses = pd.period_range(datas[0], datas[-1], freq="M")
    itens = ped.itens
    itens_por_pedido = itens.groupby("pedido_id")
    total_pedido = ped.pedidos.set_index("pedido_id")["total"]
    numero_pedido = ped.pedidos.set_index("pedido_id")["numero_pedido"] if "numero_pedido" in ped.pedidos else None
    J_mes = (J["inicio_utc"] - UTC_OFFSET).dt.to_period("M")
    evento_id_global = 0
    envio_id_global = 0
    clique_id_global = 0

    for mes in meses:
        dias_mes = np.where(datas.to_period("M") == mes)[0]
        d0, d1 = dias_mes[0], dias_mes[-1]
        # --- sessões pagas não conversoras
        Tm = T[(T.dia >= d0) & (T.dia <= d1) & (T.nc > 0)]
        rep = np.repeat(np.arange(len(Tm)), Tm.nc.values)
        pagas = pd.DataFrame({"key": Tm.key.values[rep], "eid": pd.array(Tm.eid.values[rep].astype(np.int64), dtype="Int64"),
                              "dia": Tm.dia.values[rep]})
        # --- orgânicas
        orgs = []
        for c, sh in org_share.items():
            lam = org_dia[d0:d1 + 1] * sh * (np.where(news[d0:d1 + 1], 1.8, 0.7) if c == "email" else 1)
            cnt = rng.poisson(lam)
            dd_ = np.repeat(np.arange(d0, d1 + 1), cnt)
            orgs.append(pd.DataFrame({"key": c, "eid": pd.array([pd.NA] * len(dd_), dtype="Int64"), "dia": dd_}))
        # TikTok e afiliados: sessões de clique sem compra (cliques x taxa de sessão - jornadas)
        for key_n, cli_n, taxa in (("tiktok", cli_tiktok, 0.62), ("afiliado", cli_afil, 0.8)):
            usadas_n = np.bincount(J.dia.values[(J.key.values == key_n)].astype(int), minlength=nd)[d0:d1 + 1]
            cnt = np.maximum(rng.binomial(cli_n[d0:d1 + 1], taxa) - usadas_n, 0)
            dd_ = np.repeat(np.arange(d0, d1 + 1), cnt)
            orgs.append(pd.DataFrame({"key": key_n, "eid": pd.array([pd.NA] * len(dd_), dtype="Int64"), "dia": dd_}))
        NC = pd.concat([pagas] + orgs, ignore_index=True)
        m = len(NC)
        # horário: perfil diário (local) -> UTC
        hora = rng.choice(24, size=m, p=_PERFIL_HORA)
        NC["inicio_utc"] = datas[NC.dia.values] + pd.to_timedelta(hora * 3600 + rng.integers(0, 3600, m), unit="s") + UTC_OFFSET
        # palavras-chave para search
        srch = np.where(np.isin(NC.key.values, ["g_marca", "g_search"]))[0]
        kwv = np.full(m, None, dtype=object)
        for i in srch:
            kwv[i] = ent.palavra(rng, NC.dia.values[i], NC.eid.values[i])
        NC["kw"] = kwv
        # visitante conhecido?
        p_conh = pd.Series(NC.key).map({"meta_rmkt": 0.45, "g_marca": 0.35, "email": 0.92, "whatsapp": 0.7,
                                        "direct": 0.33, "organic_search": 0.12, "organic_social": 0.15,
                                        "meta_prosp": 0.06, "g_search": 0.1, "g_pmax": 0.12, "g_dg": 0.04,
                                        "referral": 0.1, "tiktok": 0.05, "afiliado": 0.22}).values
        conhecido = rng.random(m) < p_conh
        n_disp = int(((cad_dia <= d1) & (cad_dia >= -10**6)).sum())
        cli = np.full(m, -1)
        if n_disp:
            elegiveis = np.where(cad_dia <= d0)[0]
            if len(elegiveis):
                w = 1.0 + clientes["_n_pedidos"].values[elegiveis]
                cli[conhecido] = elegiveis[rng.choice(len(elegiveis), size=conhecido.sum(), p=w / w.sum())] + 1
        conhecido &= cli > 0
        cids = np.empty(m, dtype=object)
        anon_n = (~conhecido).sum()
        base_ts = NC["inicio_utc"].values.astype("datetime64[s]").astype(np.int64)
        cids[~conhecido] = np.char.add(np.char.add(rng.integers(10**8, 2 * 10**9, anon_n).astype(str), "."),
                                       base_ts[~conhecido].astype(str))
        for i in np.where(conhecido)[0]:
            cids[i] = client_ids_do_cliente(int(cli[i]), NC["inicio_utc"].iat[i])
        NC["client_id"] = cids
        NC["cliente_sessao"] = pd.array(np.where(conhecido & (rng.random(m) < 0.4), cli, -1), dtype="Int64")
        NC.loc[NC.cliente_sessao == -1, "cliente_sessao"] = pd.NA
        NC["_consent"] = np.where(rng.random(m) < 0.72, 2, np.where(rng.random(m) < 0.39, 1, 0))
        if conhecido.any():
            NC.loc[conhecido, "_consent"] = [consent_de(c) for c in cids[conhecido]]
        NC["_uf"] = np.where(conhecido, c_uf[np.clip(cli - 1, 0, None)], None)
        NC["pedido_id"] = pd.NA
        NC["posicao"] = 0
        NC["compra"] = False
        NC["novo"] = ~conhecido
        NC["tmp"] = -1
        NC["dur_compra"] = np.nan

        # --- sessões de jornada que começam neste mês
        Jm_idx = np.where(J_mes.values == mes)[0]
        Jm = J.iloc[Jm_idx]
        S = pd.concat([Jm[["key", "eid", "dia", "inicio_utc", "kw", "client_id", "cliente_sessao", "_consent", "_uf",
                           "pedido_id", "posicao", "compra", "novo", "tmp", "dur_compra"]], NC], ignore_index=True)
        S = S.sort_values("inicio_utc", kind="stable").reset_index(drop=True)
        S["sessao_id"] = np.arange(prox_id, prox_id + len(S), dtype=np.int64)
        prox_id += len(S)
        jt = S.tmp.values >= 0
        J.loc[S.tmp.values[jt], "sessao_id"] = S.sessao_id.values[jt]

        S = preencher_atributos(rng, S, ent, midia_maps, slugs_cat, skus, pesos_sku)
        S["canal"] = canal_padrao(S, midia_maps)
        for c_, q_ in S["canal"].value_counts().items():
            canais_total[c_] = canais_total.get(c_, 0) + int(q_)
        jt = S.tmp.values >= 0
        tmp_j = S.tmp.values[jt].astype(int)
        J.loc[tmp_j, "canal"] = S.canal.values[jt]
        tem_ck = pd.notna(S.gclid.values[jt]) | pd.notna(S.fbclid.values[jt])
        eids = S.eid.values[jt]
        keys = S.key.values[jt]
        J.loc[tmp_j, "meta_campanha_id"] = pd.array(
            [midia_maps["meta_ad_camp"][e] if (ok and k.startswith("meta")) else pd.NA
             for e, k, ok in zip(eids, keys, tem_ck)], dtype="Int64")
        J.loc[tmp_j, "google_campanha_id"] = pd.array(
            [midia_maps["g_grupo_camp"][e] if (ok and k.startswith("g_")) else pd.NA
             for e, k, ok in zip(eids, keys, tem_ck)], dtype="Int64")
        J.loc[tmp_j, "consent_ad"] = S.consent_ad_storage.values[jt]
        J.loc[tmp_j, "consent_aud"] = S.consent_ad_user_data.values[jt]

        # --- cliques (sessões pagas com click id)
        tem_click = pd.notna(S.gclid.values) | pd.notna(S.fbclid.values)
        ci = np.where(tem_click)[0]
        clique_id = np.full(len(S), None, dtype=object)
        clique_id[ci] = np.arange(clique_id_global + 1, clique_id_global + 1 + len(ci))
        clique_id_global += len(ci)
        S["clique_id"] = pd.array(clique_id, dtype="Int64")
        is_meta = np.isin(S.key.values[ci], ["meta_prosp", "meta_rmkt"])
        kwc = S.kw.values[ci]
        CL = pd.DataFrame({
            "clique_id": clique_id[ci].astype(np.int64),
            "plataforma": np.where(is_meta, "meta", "google"),
            "click_id": np.where(is_meta, S.fbclid.values[ci], S.gclid.values[ci]),
            "meta_anuncio_id": pd.array([e if mm else pd.NA for e, mm in zip(S.eid.values[ci], is_meta)], dtype="Int64"),
            "google_grupo_id": pd.array([e if not mm else pd.NA for e, mm in zip(S.eid.values[ci], is_meta)], dtype="Int64"),
            "google_palavra_chave_id": pd.array([k_ if (k_ is not None and not pd.isna(k_) and not mm) else np.nan
                                                 for k_, mm in zip(kwc, is_meta)], dtype="Int64"),
            "clicado_em": S.inicio_utc.values[ci] - pd.to_timedelta(rng.uniform(0.5, 6, len(ci)), unit="s"),
        })
        esc.gravar("cliques_midia", CL)
        resumo["cliques"] += len(CL)

        # --- eventos
        E, S = _eventos(rng, S, itens_por_pedido, total_pedido, preco_ef, var_id, skus, pesos_sku, slugs_cat,
                        V, ped.pedidos)
        E["evento_id"] = np.arange(evento_id_global + 1, evento_id_global + 1 + len(E), dtype=np.int64)
        evento_id_global += len(E)

        # sessão: duração e engajamento
        S["ga_session_id"] = (S.inicio_utc.values.astype("datetime64[s]").astype(np.int64)).astype(np.int64)
        S["primeira_visita"] = (S.novo.values & ((S.posicao.values <= 1))).astype(int)
        cols_s = ["sessao_id", "ga_session_id", "client_id", "cliente_sessao", "inicio_utc", "duracao_seg",
                  "dispositivo", "sistema_operacional", "navegador", "uf", "landing_page", "referrer",
                  "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "gclid", "fbclid",
                  "fbp", "fbc", "clique_id", "consent_analytics_storage", "consent_ad_storage",
                  "consent_ad_user_data", "consent_ad_personalization", "primeira_visita", "engajada"]
        esc.gravar("sessoes", S[cols_s].rename(columns={"cliente_sessao": "cliente_id", "inicio_utc": "iniciada_em"}))
        resumo["sessoes"] += len(S)

        # pedido -> sessão da compra
        comp = S[S.compra.values.astype(bool)]
        pedido_sessao.update(dict(zip(comp.pedido_id.astype(int), comp.sessao_id)))

        # --- envios server-side
        EN = _envios(rng, E, S, c_tel)
        EN["envio_id"] = np.arange(envio_id_global + 1, envio_id_global + 1 + len(EN), dtype=np.int64)
        envio_id_global += len(EN)
        esc.gravar("eventos", E[["evento_id", "event_id", "sessao_id", "cliente_id", "event_name", "event_timestamp",
                                 "page_location", "variante_id", "quantidade", "valor", "moeda", "transaction_id",
                                 "pedido_id", "fonte", "versao_container"]])
        esc.gravar("envios_conversao", EN[["envio_id", "evento_id", "plataforma", "status", "http_status", "enviado_em",
                                           "email_hash_enviado", "telefone_hash_enviado", "fbp_enviado", "fbc_enviado",
                                           "gclid_enviado", "event_match_quality", "mensagem_erro"]])
        resumo["eventos"] += len(E)
        resumo["envios"] += len(EN)
        print(f"  tracking {mes}: {len(S):>7} sessões, {len(E):>8} eventos", flush=True)

    # canais observáveis da jornada (para atribuição) vêm das sessões gravadas
    resumo["canais_sessoes"] = canais_total
    return Tracking(J, pd.Series(pedido_sessao), resumo)


SOCIAL_REF = ("instagram.com", "facebook.com", "pinterest.com", "tiktok.com", "youtube.com")
BUSCA_REF = ("google.", "bing.com", "duckduckgo.com", "search.yahoo")
TIPO_GOOGLE_CANAL = {"SEARCH": "Paid Search", "SHOPPING": "Paid Shopping", "PERFORMANCE_MAX": "Cross-network",
                     "DEMAND_GEN": "Paid Video"}


def canal_padrao(S: pd.DataFrame, midia_maps: dict) -> np.ndarray:
    """Agrupamento de canais a partir do que é observável na sessão.
    Mesma regra do modelo dbt int_sessoes_canal."""
    src = S.utm_source.fillna("").str.lower().values
    med = S.utm_medium.fillna("").str.lower().values
    ref = S.referrer.fillna("").values
    gcl = pd.notna(S.gclid.values)
    fbc = pd.notna(S.fbclid.values)
    tipo_g = np.array([midia_maps["g_grupo_tipo"].get(e, "SEARCH") if g else "" for e, g in zip(S.eid.values, gcl)])
    social_src = np.isin(src, ["fb", "ig", "an", "facebook", "instagram", "igshopping", "tiktok", "tiktok_ads"])
    ref_social = np.array([any(d in r for d in SOCIAL_REF) for r in ref])
    ref_busca = np.array([any(d in r for d in BUSCA_REF) for r in ref])
    conds = [
        gcl,
        fbc | (social_src & np.isin(med, ["paid_social", "paid", "cpc"])),
        (src == "google") & (med == "cpc"),
        np.isin(med, ["afiliados", "affiliate"]),
        (med == "email") | np.isin(src, ["newsletter", "email", "rdstation"]),
        np.isin(src, ["whatsapp", "wpp"]),
        np.isin(med, ["social", "bio"]) | np.isin(src, ["ig", "instagram", "linktree"]) | ref_social,
        ref_busca,
        ref != "",
        (src == "") & (med == ""),
    ]
    escolhas = [np.array([TIPO_GOOGLE_CANAL[t] if t else "" for t in tipo_g]), "Paid Social", "Paid Search", "Affiliates",
                "Email",
                "WhatsApp", "Organic Social", "Organic Search", "Referral", "Direct"]
    return np.select(conds, escolhas, "Unassigned")


_PERFIL_HORA = np.array([1.2, 0.7, 0.4, 0.25, 0.2, 0.3, 0.8, 1.8, 3.2, 4.6, 5.4, 5.6, 5.2, 5.4, 5.6, 5.5,
                         5.3, 5.2, 5.6, 6.4, 7.4, 7.8, 6.6, 3.6])
_PERFIL_HORA = _PERFIL_HORA / _PERFIL_HORA.sum()


def _eventos(rng, S, itens_por_pedido, total_pedido, preco_ef, var_id, skus, pesos_sku, slugs_cat, V, pedidos):
    """Monta os eventos GA4 de todas as sessões do mês."""
    n = len(S)
    key = S.key.values
    compra = S.compra.values.astype(bool)
    jornada = (S.posicao.values > 0) & ~compra
    dia = S.dia.values.astype(int)

    # contagens genéricas
    n_pv = rng.geometric(0.62, n) + (rng.random(n) < 0.15)
    p_vi = pd.Series(key).map({"g_pmax": 0.82, "meta_prosp": 0.55, "meta_rmkt": 0.7, "g_search": 0.62,
                               "g_marca": 0.6, "g_dg": 0.35, "direct": 0.5, "organic_search": 0.6,
                               "organic_social": 0.45, "email": 0.62, "whatsapp": 0.7, "referral": 0.55,
                               "tiktok": 0.4, "afiliado": 0.6}).values
    p_vi = np.where(jornada, 0.85, p_vi)
    tem_vi = rng.random(n) < p_vi
    n_vi = np.where(tem_vi, 1 + rng.poisson(0.55, n), 0)
    disp = S.dispositivo.values
    fator = np.where(disp == "desktop", 1.35, 1.0)
    p_atc = np.where(jornada, 0.22, 0.095) * fator
    atc = tem_vi & (rng.random(n) < p_atc)
    bc = atc & (rng.random(n) < np.where(jornada, 0.45, 0.33))
    api = bc & (rng.random(n) < 0.48)
    # sessões de compra: funil completo, itens do pedido
    n_pv = np.where(compra, n_pv + 2, n_pv)

    blocos = []
    ini = S.inicio_utc.values
    # duração
    dur = np.round(rng.lognormal(np.log(25 + 45 * n_pv + 60 * n_vi), 0.5)).astype(np.int64)
    dur = np.where(n_pv + n_vi <= 1, np.where(rng.random(n) < 0.55, rng.integers(0, 9, n), dur), dur)
    dur = np.where(compra, np.nan_to_num(S["dur_compra"].values.astype(float), nan=240).astype(np.int64), dur)
    S["duracao_seg"] = dur
    S["engajada"] = ((dur > 10) | (n_pv >= 2) | compra | atc).astype(int)

    def bloco(sel_idx, nome, frac_ini, frac_fim, variante=None, quantidade=None, valor=None, transacao=None,
              pedido=None, page=None):
        k = len(sel_idx)
        if k == 0:
            return
        off = (rng.uniform(frac_ini, frac_fim, k) * dur[sel_idx] * 1000).astype(np.int64)
        blocos.append(pd.DataFrame({
            "sessao_id": S.sessao_id.values[sel_idx], "_i": sel_idx, "event_name": nome,
            "_ts": ini[sel_idx] + off.astype("timedelta64[ms]"),
            "page_location": page, "_v": variante, "quantidade": quantidade, "valor": valor,
            "transaction_id": transacao, "pedido_id": pedido}))

    # page_view
    rep = np.repeat(np.arange(n), n_pv)
    primeiro = np.r_[True, rep[1:] != rep[:-1]]
    paginas = np.where(primeiro, S.landing_page.values[rep],
                       np.where(rng.random(len(rep)) < 0.5,
                                np.char.add(f"{SITE}/produto/", np.char.lower(skus[rng.choice(len(skus), len(rep), p=pesos_sku)])),
                                np.char.add(f"{SITE}/categoria/", slugs_cat[rng.integers(0, len(slugs_cat), len(rep))])))
    frac_pv = np.where(primeiro, 0.0, 0.05)
    k = len(rep)
    off = (np.where(primeiro, 0, rng.uniform(0.05, 0.7, k)) * dur[rep] * 1000).astype(np.int64)
    blocos.append(pd.DataFrame({"sessao_id": S.sessao_id.values[rep], "_i": rep, "event_name": "page_view",
                                "_ts": ini[rep] + off.astype("timedelta64[ms]"), "page_location": paginas,
                                "_v": -1, "quantidade": np.nan, "valor": np.nan, "transaction_id": None,
                                "pedido_id": pd.NA}))
    # view_item genérico (sessões que não são de compra)
    rep = np.repeat(np.arange(n), np.where(compra, 0, n_vi))
    vv = rng.choice(len(skus), len(rep), p=pesos_sku)
    preco_v = preco_ef[vv, dia[rep]]
    bloco(rep, "view_item", 0.05, 0.7, variante=vv, quantidade=1.0, valor=np.round(preco_v, 2),
          page=np.char.add(f"{SITE}/produto/", np.char.lower(skus[vv])))
    # add_to_cart / begin_checkout / add_payment_info genéricos (último item visto)
    gi = np.where(atc & ~compra)[0]
    vv = rng.choice(len(skus), len(gi), p=pesos_sku)
    qtd = np.round(np.clip(rng.lognormal(np.log(2.5), 0.6, len(gi)) * 2, 1, 60)) / 2
    qtd = np.where(V["formato_venda"].values[vv] == "rolo", 1.0, qtd)
    val = np.round(qtd * preco_ef[vv, dia[gi]], 2)
    bloco(gi, "add_to_cart", 0.5, 0.8, variante=vv, quantidade=qtd, valor=val,
          page=np.char.add(f"{SITE}/produto/", np.char.lower(skus[vv])))
    gb = np.where(bc & ~compra)[0]
    vb = pd.Series(val, index=gi).reindex(gb).values
    bloco(gb, "begin_checkout", 0.82, 0.88, valor=vb, page=f"{SITE}/checkout")
    ga = np.where(api & ~compra)[0]
    va = pd.Series(val, index=gi).reindex(ga).values
    bloco(ga, "add_payment_info", 0.9, 0.97, valor=va, page=f"{SITE}/checkout/pagamento")

    # sessões de compra
    ci = np.where(compra)[0]
    if len(ci):
        pids = S.pedido_id.values[ci].astype(int)
        it = pd.concat([itens_por_pedido.get_group(p).assign(_i=i) for p, i in zip(pids, ci)])
        vidx = it["_v"].values
        vi_i = it["_i"].values
        bloco(vi_i, "view_item", 0.05, 0.5, variante=vidx, quantidade=1.0,
              valor=it["preco_unitario"].values, page=np.char.add(f"{SITE}/produto/", np.char.lower(skus[vidx])))
        bloco(vi_i, "add_to_cart", 0.5, 0.75, variante=vidx, quantidade=it["quantidade"].values,
              valor=it["total_item"].values, page=np.char.add(f"{SITE}/produto/", np.char.lower(skus[vidx])))
        tot = total_pedido.reindex(pids).values
        numero = pedidos.set_index("pedido_id")["numero_pedido"].reindex(pids).values
        bloco(ci, "begin_checkout", 0.80, 0.85, valor=tot, page=f"{SITE}/checkout")
        bloco(ci, "add_payment_info", 0.88, 0.95, valor=tot, page=f"{SITE}/checkout/pagamento")
        bloco(ci, "purchase", 1.0, 1.0, valor=tot, transacao=numero, pedido=pids,
              page=f"{SITE}/checkout/obrigado")

    E = pd.concat(blocos, ignore_index=True)
    E["_v"] = E["_v"].fillna(-1).astype(int)
    E["variante_id"] = pd.array(np.where(E["_v"].values >= 0, var_id[np.clip(E["_v"].values, 0, None)], -1), dtype="Int64")
    E.loc[E["_v"] < 0, "variante_id"] = pd.NA
    E.loc[E.event_name == "page_view", ["quantidade", "valor"]] = np.nan
    E["moeda"] = np.where(E.event_name == "page_view", None, "BRL")
    E["pedido_id"] = pd.array(E["pedido_id"], dtype="Int64")

    # user_id: em sessões de compra, só a partir do begin_checkout (login no checkout)
    ucli = S["cliente_sessao"].astype("Int64").values
    E["cliente_id"] = ucli[E["_i"].values]
    em_compra = compra[E["_i"].values]
    antes_login = em_compra & E.event_name.isin(["page_view", "view_item", "add_to_cart"]).values & \
        (S["novo"].values[E["_i"].values])
    E.loc[antes_login, "cliente_id"] = pd.NA

    # fonte: tudo chega do navegador (web); purchase também vem do backend (server) com o mesmo event_id
    E = E.sort_values(["sessao_id", "_ts"], kind="stable").reset_index(drop=True)
    E["event_id"] = _uuid_simples(rng, len(E))
    E["fonte"] = "web"
    pur = E[E.event_name == "purchase"]
    # navegador fechou antes da página de obrigado / bloqueio: só server
    so_server = rng.random(len(pur)) < 0.35
    E.loc[pur.index[so_server], "fonte"] = "server"
    srv = pur[~so_server].copy()
    srv["fonte"] = "server"
    srv["_ts"] = srv["_ts"] + pd.to_timedelta(rng.uniform(0.4, 8, len(srv)), unit="s")
    # recarregamento da página de obrigado: novo event_id, mesmo transaction_id
    rel = pur[~so_server].sample(frac=0.03, random_state=int(rng.integers(0, 2**31)))
    rel = rel.assign(event_id=_uuid_simples(rng, len(rel)),
                     _ts=rel["_ts"] + pd.to_timedelta(rng.uniform(20, 600, len(rel)), unit="s"))
    # retries de rede: mesmo event_id duplicado (0,8% dos demais eventos)
    ret = E[(E.event_name != "purchase")].sample(frac=0.008, random_state=int(rng.integers(0, 2**31)))
    ret = ret.assign(_ts=ret["_ts"] + pd.to_timedelta(rng.integers(1, 1500, len(ret)), unit="ms"))
    E = pd.concat([E, srv, rel, ret], ignore_index=True)
    E = E.sort_values(["sessao_id", "_ts"], kind="stable").reset_index(drop=True)

    # horário local para versão do container e defeito de fuso
    ts_local = pd.Series(E["_ts"].values - np.timedelta64(3, "h"))
    E["versao_container"] = _versao(ts_local)
    bug = (E["versao_container"].values == "v2.3")
    E["event_timestamp"] = np.where(bug, ts_local.values, E["_ts"].values)
    E["event_timestamp"] = pd.to_datetime(E["event_timestamp"])
    return E, S


def _envios(rng, E, S, c_tel):
    """Log de envio para Meta CAPI (add_to_cart, begin_checkout, add_payment_info, purchase)
    e Google Ads Enhanced Conversions (purchase)."""
    sess = S.set_index("sessao_id")
    alvo = E[E.event_name.isin(["add_to_cart", "begin_checkout", "add_payment_info", "purchase"])]
    s = sess.loc[alvo.sessao_id.values]
    ts_real = alvo["_ts"].values
    dup = alvo.duplicated("event_id", keep="first").values
    ident = alvo["cliente_id"].notna().values
    cli = alvo["cliente_id"].fillna(0).astype(int).values
    tel = np.where(cli > 0, c_tel[np.clip(cli - 1, 0, None)], False)
    fbp = s.fbp.notna().values
    fbc = s.fbc.notna().values
    gclid = s.gclid.notna().values
    ad_ok = (s.consent_ad_storage.values == "granted")
    aud_ok = (s.consent_ad_user_data.values == "granted")

    def monta(mask, plataforma, consent_ok, dup_):
        k = int(mask.sum())
        st = np.full(k, "enviado", dtype=object)
        http = np.full(k, 200.0)
        err = np.full(k, None, dtype=object)
        ts_env = ts_real[mask] + (rng.uniform(150, 3000, k)).astype("timedelta64[ms]")
        r = rng.random(k)
        e1 = r < 0.012
        st[e1], http[e1], err[e1] = "erro", 400, "Invalid parameter: event_time too old"
        e2 = (r >= 0.012) & (r < 0.018)
        st[e2], http[e2], err[e2] = "erro", 500, "Internal server error"
        e3 = (r >= 0.018) & (r < 0.021)
        st[e3], http[e3], err[e3] = "erro", 429, "Rate limit exceeded"
        if plataforma == "meta_capi":
            loc = pd.Series(ts_real[mask] - np.timedelta64(3, "h"))
            inc = ((loc >= INCIDENTE_CAPI[0]) & (loc <= INCIDENTE_CAPI[1])).values
            st[inc], http[inc], err[inc] = "erro", 401, "Invalid OAuth 2.0 access token"
        dd = dup_[mask]
        st[dd], http[dd], err[dd] = "deduplicado", 200, None
        bloq = ~consent_ok[mask]
        st[bloq], http[bloq], err[bloq] = "bloqueado_consentimento", np.nan, None
        ts_env = np.where(bloq, np.datetime64("NaT"), ts_env)
        envia = ~bloq
        email = envia & ident[mask]
        fone = envia & tel[mask] & (rng.random(k) < 0.9)
        out = pd.DataFrame({
            "evento_id": alvo.evento_id.values[mask], "plataforma": plataforma, "status": st,
            "http_status": pd.array(np.where(np.isnan(http), np.nan, http), dtype="Int64"),
            "enviado_em": pd.to_datetime(ts_env),
            "email_hash_enviado": email.astype(int), "telefone_hash_enviado": fone.astype(int),
            "fbp_enviado": (envia & fbp[mask] & (plataforma == "meta_capi")).astype(int),
            "fbc_enviado": (envia & fbc[mask] & (plataforma == "meta_capi")).astype(int),
            "gclid_enviado": (envia & gclid[mask] & (plataforma == "google_ads_ec")).astype(int),
            "mensagem_erro": err,
        })
        if plataforma == "meta_capi":
            emq = 3.2 + 2.6 * out.email_hash_enviado + 1.3 * out.telefone_hash_enviado + 0.9 * out.fbp_enviado \
                + 1.2 * out.fbc_enviado + rng.normal(0, 0.3, k)
            out["event_match_quality"] = np.where(envia, np.round(np.clip(emq, 1, 9.8), 1), np.nan)
        else:
            out["event_match_quality"] = np.nan
        return out

    todos = np.ones(len(alvo), bool)
    meta = monta(todos, "meta_capi", ad_ok, dup)
    pur = alvo.event_name.values == "purchase"
    goo = monta(pur, "google_ads_ec", aud_ok, dup)
    return pd.concat([meta, goo], ignore_index=True).sort_values("evento_id", kind="stable").reset_index(drop=True)
