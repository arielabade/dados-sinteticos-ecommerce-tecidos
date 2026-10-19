"""Atribuição multi-toque e conversões reportadas pelas plataformas."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CFG
from .midia import Midia
from .tracking import UTC_OFFSET, Tracking

LOOKBACK = pd.Timedelta(days=30)
MEIA_VIDA_DD = 7.0  # dias


def gerar_atribuicao(trk: Tracking, pedidos: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por (pedido, modelo, sessão) com peso e receita atribuída.

    last_click  = último clique não direto (padrão GA4/Universal), cai para o
                  último toque se a jornada for toda direta;
    first_click = primeiro toque;
    linear      = peso igual entre os toques;
    data_driven = simplificado: peso proporcional ao "lift" do canal
                  (participação nas jornadas que convertem / participação no
                  total de sessões) x decaimento temporal (meia-vida 7 dias) x
                  bônus de 20% para primeiro e último toque.
    """
    J = trk.jornadas
    J = J[J.sessao_id > 0].copy()
    compra = J[J.compra].set_index("pedido_id")["inicio_utc"]
    J["_t_compra"] = J.pedido_id.map(compra)
    J = J[J._t_compra.notna() & (J.inicio_utc >= J._t_compra - LOOKBACK)]
    J = J.sort_values(["pedido_id", "inicio_utc"]).reset_index(drop=True)
    J["posicao"] = J.groupby("pedido_id").cumcount() + 1
    J["total_toques"] = J.groupby("pedido_id")["posicao"].transform("max")
    total = pedidos.set_index("pedido_id")["total"]
    J["_total"] = J.pedido_id.map(total).values

    # lift por canal para o data-driven
    tot_sess = pd.Series(trk.resumo["canais_sessoes"], dtype=float)
    share_sess = tot_sess / tot_sess.sum()
    share_jorn = J.canal.value_counts(normalize=True)
    lift = (share_jorn / share_sess.reindex(share_jorn.index)).fillna(1.0).clip(0.2, 8)

    out = []
    # last non-direct click
    nd = J[J.canal != "Direct"]
    ult_nd = nd.groupby("pedido_id").tail(1)
    sem_nd = ~J.pedido_id.isin(ult_nd.pedido_id)
    ult = pd.concat([ult_nd, J[sem_nd].groupby("pedido_id").tail(1)])
    out.append(ult.assign(modelo="last_click", peso=1.0))
    out.append(J[J.posicao == 1].assign(modelo="first_click", peso=1.0))
    out.append(J.assign(modelo="linear", peso=1.0 / J.total_toques))
    dias_antes = (J._t_compra - J.inicio_utc).dt.total_seconds() / 86400
    w = J.canal.map(lift).values * 0.5 ** (dias_antes.values / MEIA_VIDA_DD) * \
        np.where((J.posicao == 1) | (J.posicao == J.total_toques), 1.2, 1.0)
    dd = J.assign(modelo="data_driven", _w=w)
    dd["peso"] = dd._w / dd.groupby("pedido_id")._w.transform("sum")
    out.append(dd)

    A = pd.concat(out, ignore_index=True)
    A["peso"] = A.peso.round(6)
    # garante soma exata = 1 por pedido/modelo ajustando o último toque
    soma = A.groupby(["pedido_id", "modelo"]).peso.transform("sum")
    ultimo = ~A.duplicated(["pedido_id", "modelo"], keep="last")
    A.loc[ultimo, "peso"] = (A.loc[ultimo, "peso"] + (1 - soma[ultimo])).round(6)
    A["receita_atribuida"] = (A.peso * A._total).round(2)
    A = A.sort_values(["pedido_id", "modelo", "posicao"]).reset_index(drop=True)
    A.insert(0, "atribuicao_id", np.arange(1, len(A) + 1))
    A["meta_campanha_id"] = pd.array(A.meta_campanha_id, dtype="Int64")
    A["google_campanha_id"] = pd.array(A.google_campanha_id, dtype="Int64")
    return A[["atribuicao_id", "pedido_id", "modelo", "sessao_id", "posicao", "total_toques", "canal",
              "meta_campanha_id", "google_campanha_id", "peso", "receita_atribuida"]]


def metricas_reportadas(trk: Tracking, pedidos: pd.DataFrame, midia: Midia):
    """Conversões que Meta e Google reportariam. Divergem dos pedidos reais por:
    janelas e modelos de atribuição próprios, view-through, conversões
    modeladas, pedidos depois cancelados, data do clique x data da compra."""
    rng = CFG.rng("plataformas")
    datas = CFG.datas
    J = trk.jornadas
    P = pedidos.set_index("pedido_id")
    ped_rast = set(trk.pedido_sessao.index)
    compra = J[J.compra].set_index("pedido_id")
    t_compra = compra["inicio_utc"] + pd.to_timedelta(compra["dur_compra"].fillna(0), unit="s")

    # ------------------------------------------------------------------ META
    me = midia.meta_entrega.copy()
    me["dia"] = (me.data - datas[0]).dt.days
    me["_w_vt"] = me.impressoes * me._eff
    imp_dia = {d: (g.anuncio_id.values, g._w_vt.values / g._w_vt.sum())
               for d, g in me[(me._canal == "meta_prospeccao") & (me.impressoes > 0)].groupby("dia")}
    meta_cred = []  # (dia, anuncio_id, valor)
    mt = J[J.key.isin(["meta_prosp", "meta_rmkt"]) & J.eid.notna()]
    mt = mt.assign(_tc=mt.pedido_id.map(t_compra))
    mt = mt[(mt._tc - mt.inicio_utc <= pd.Timedelta(days=7)) & (mt._tc >= mt.inicio_utc)]
    ult_meta = mt.sort_values("inicio_utc").groupby("pedido_id").tail(1)
    consent = compra["consent_ad"]
    for r in ult_meta.itertuples(index=False):
        ok = consent.get(r.pedido_id) == "granted" or rng.random() < 0.6  # conversões modeladas
        if ok:
            dia_c = int(P.at[r.pedido_id, "_dia"])
            meta_cred.append((dia_c, r.eid, P.at[r.pedido_id, "total"]))
    com_click = set(ult_meta.pedido_id)
    # view-through 1 dia: pedidos influenciados sem clique + reivindicação de pedidos orgânicos
    for pid, r in P[["_dia", "_motor", "total", "canal_venda"]].iterrows():
        if pid in com_click or r.canal_venda != "site":
            continue
        d = int(r._dia)
        if d not in imp_dia:
            continue
        p = 0.7 if r._motor == "meta_prospeccao" else (0.35 if r._motor == "meta_remarketing" else 0.15)
        if pid not in ped_rast:
            p *= 0.5  # sem pixel, só CAPI de backend ou modelagem
        if rng.random() < p:
            ids, w = imp_dia[d]
            meta_cred.append((d, ids[rng.choice(len(ids), p=w)], r.total))
    mc = pd.DataFrame(meta_cred, columns=["dia", "anuncio_id", "valor"])
    mc["valor"] = mc.valor * rng.lognormal(0, 0.02, len(mc))
    agg = mc.groupby(["dia", "anuncio_id"]).agg(compras=("valor", "size"), valor_compras=("valor", "sum"))
    me = me.set_index(["dia", "anuncio_id"]).join(agg).reset_index()
    me["compras"] = me.compras.fillna(0).astype(int)
    me["valor_compras"] = me.valor_compras.fillna(0).round(2)
    me["visualizacoes_pagina_destino"] = np.floor(me.cliques_link * rng.uniform(0.62, 0.8, len(me))).astype(int)
    atc_rate = np.where(me._canal == "meta_remarketing", 0.11, 0.055) * me._eff.clip(0.2, 2) ** 0.5
    me["adicoes_carrinho"] = rng.binomial(me.visualizacoes_pagina_destino.values, np.clip(atc_rate, 0, 0.5))
    me["adicoes_carrinho"] = np.maximum(me.adicoes_carrinho, me.compras)
    meta_metricas = me[["data", "anuncio_id", "investimento", "impressoes", "alcance", "cliques_todos", "cliques_link",
                        "visualizacoes_pagina_destino", "adicoes_carrinho", "compras", "valor_compras"]]

    # ---------------------------------------------------------------- GOOGLE
    ge = midia.google_entrega.copy()
    ge["dia"] = (ge.data - datas[0]).dt.days
    gt = J[J.key.isin(["g_marca", "g_search", "g_pmax", "g_dg"]) & J.eid.notna()]
    gt = gt.assign(_tc=gt.pedido_id.map(t_compra))
    gt = gt[(gt._tc - gt.inicio_utc <= pd.Timedelta(days=30)) & (gt._tc >= gt.inicio_utc)]
    # crédito fracionado entre cliques Google (DDA da plataforma ~ decaimento)
    dias_antes = (gt._tc - gt.inicio_utc).dt.total_seconds() / 86400
    gt = gt.assign(_w=0.5 ** (dias_antes / 4))
    gt["_cred"] = gt._w / gt.groupby("pedido_id")._w.transform("sum")
    aud = compra["consent_aud"]
    ok = gt.pedido_id.map(lambda p: aud.get(p) == "granted").values | (rng.random(len(gt)) < 0.7)
    gt = gt[ok]
    gt["_cred"] = gt._cred * rng.choice([1.0, 1.0, 1.0, 1.1], len(gt))  # conversões modeladas cross-device
    gt["_valor"] = gt._cred * gt.pedido_id.map(P["total"]).values
    gt["kw"] = gt.kw
    cred_g = gt.groupby(["dia", "eid"]).agg(conversoes=("_cred", "sum"), valor_conversao=("_valor", "sum"))
    # engaged-view / view-through de PMax e Demand Gen (YouTube, Display, Discover)
    extra = []
    ativos = {k: {d: (g.grupo_id.values, g.impressoes.values / g.impressoes.sum())
                  for d, g in ge[(ge.grupo_id.isin(midia.google_grupos.grupo_id[midia.google_grupos._tipo_canal == k]))
                                 & (ge.impressoes > 0)].groupby("dia")}
              for k in ["PERFORMANCE_MAX", "DEMAND_GEN"]}
    com_gclick = set(gt.pedido_id)
    for pid, r in P[["_dia", "_motor", "total", "canal_venda"]].iterrows():
        if pid in com_gclick or r.canal_venda != "site":
            continue
        d = int(r._dia)
        for tipo, p in (("DEMAND_GEN", 0.55 if r._motor == "google_demand_gen" else 0.02), ("PERFORMANCE_MAX", 0.06)):
            if d in ativos[tipo] and rng.random() < p:
                ids, w = ativos[tipo][d]
                extra.append((d, ids[rng.choice(len(ids), p=w)], 1.0, r.total))
                break
    ex = pd.DataFrame(extra, columns=["dia", "eid", "conversoes", "valor_conversao"]).groupby(["dia", "eid"]).sum()
    cred_g = cred_g.add(ex, fill_value=0)
    cred_g.index.names = ["dia", "grupo_id"]
    ge = ge.set_index(["dia", "grupo_id"]).join(cred_g).reset_index()
    ge["conversoes"] = ge.conversoes.fillna(0).round(2)
    ge["valor_conversao"] = ge.valor_conversao.fillna(0).round(2)
    google_metricas = ge[["data", "grupo_id", "investimento", "impressoes", "cliques", "conversoes", "valor_conversao",
                          "parcela_impressoes"]]

    # palavras-chave: conversões por palavra do clique; distribui o resto pelo share de cliques
    kwe = midia.google_kw_entrega.copy()
    kwe["dia"] = (kwe.data - datas[0]).dt.days
    gk = gt[gt.kw.notna()].groupby(["dia", "kw"]).agg(conv=("_cred", "sum"), val=("_valor", "sum"))
    gk.index.names = ["dia", "palavra_chave_id"]
    kwe = kwe.set_index(["dia", "palavra_chave_id"]).join(gk).reset_index()
    kwe["conversoes"] = kwe.conv.fillna(0).round(2)
    kwe["valor_conversao"] = kwe.val.fillna(0).round(2)
    # coerência: soma das palavras <= grupo (o resto vem de termos fora da lista / cliques sem kw)
    kw_metricas = kwe[["data", "palavra_chave_id", "investimento", "impressoes", "cliques", "conversoes",
                       "valor_conversao"]]
    return meta_metricas, google_metricas, kw_metricas
