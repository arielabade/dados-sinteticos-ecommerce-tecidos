"""Ground truth do gerador: o efeito verdadeiro de cada canal e do teste
geográfico, gravado em data/ground_truth/ (fora do MySQL).

Nada aqui deve ser lido por código de modelagem. Serve para uma pergunta só,
depois que o modelo já foi ajustado: ele recuperou os efeitos plantados?

Conversão de pedidos em receita: a demanda é gerada em pedidos esperados. A
receita incremental verdadeira de um canal é o número de pedidos incrementais
esperados x a receita paga realizada por pedido esperado no mesmo mês (que já
desconta cancelamentos, ruptura de estoque e muda com o ticket sazonal).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .clientes import UF_LISTA
from .config import CFG
from .midia import GOOGLE_CAMPANHAS, META_CAMPANHAS
from .regional import CANAIS, PARAM, janela_teste, ufs_tratamento

PAGOS = ["pago", "enviado", "entregue", "devolvido"]
JANELA_CURVA_DIAS = 91          # últimas 13 semanas: janela das curvas de resposta e do ROI marginal
MULTIPLICADORES = np.round(np.arange(0, 2.01, 0.1), 2)


def _receita_por_pedido_esperado(dem, P) -> np.ndarray:
    datas = CFG.datas
    pagos = P[P.status.isin(PAGOS) & (P.pedido_teste == 0)]
    receita_mes = pagos.groupby(pd.to_datetime(pagos.criado_em).dt.to_period("M")).total.sum()
    esperado_mes = dem.diario["esperado"].groupby(datas.to_period("M")).sum()
    rpo = (receita_mes.reindex(esperado_mes.index) / esperado_mes).ffill().bfill()
    return rpo.reindex(datas.to_period("M")).values


def gravar_ground_truth(dem, midia, novos, ped, P, Pt, esc) -> None:
    vd = CFG.verdade
    vd.mkdir(parents=True, exist_ok=True)
    datas = CFG.datas
    canal_mmm = {c: PARAM["canais"][c]["canal_mmm"] for c in CANAIS}
    rpo = _receita_por_pedido_esperado(dem, P)

    # ---- arquivos da versão anterior (mesmo formato, agora com os canais novos)
    dem.diario.rename_axis("data").to_csv(vd / "demanda_diaria.csv")
    dem.params.to_csv(vd / "parametros_mmm.csv", index=False)
    pd.concat([dem.investimento.add_prefix("inv_"), dem.efetivo.add_prefix("inv_efetivo_")], axis=1) \
        .rename_axis("data").to_csv(vd / "investimento_canal_diario.csv")
    dem.componentes_base.rename_axis("data").to_csv(vd / "componentes_base_diaria.csv")
    ped.perdas_ruptura.to_csv(vd / "pedidos_perdidos_ruptura.csv", index=False)
    Pt[["pedido_id", "_motor", "_novo", "_uf"]].rename(
        columns={"_motor": "motor_verdadeiro", "_novo": "cliente_novo", "_uf": "uf_demanda"}) \
        .to_csv(vd / "pedidos_motor.csv", index=False)
    pd.DataFrame([{"plataforma": "meta", "campanha": c[0], "eficiencia": c[7]} for c in META_CAMPANHAS] +
                 [{"plataforma": "google", "campanha": c[0], "eficiencia": c[9]} for c in GOOGLE_CAMPANHAS]) \
        .to_csv(vd / "eficiencia_campanhas.csv", index=False)

    # ---- contribuição diária verdadeira por canal (pedidos e receita)
    linhas = []
    for c in CANAIS:
        inc = dem.diario[f"inc_{c}"].values
        linhas.append(pd.DataFrame({"data": datas.date, "canal": c, "canal_mmm": canal_mmm[c],
                                    "investimento": dem.investimento[c].values.round(2),
                                    "pedidos_incrementais": inc.round(4),
                                    "receita_incremental": (inc * rpo).round(2)}))
    linhas.append(pd.DataFrame({"data": datas.date, "canal": "base", "canal_mmm": "base", "investimento": 0.0,
                                "pedidos_incrementais": dem.diario["base"].values.round(4),
                                "receita_incremental": (dem.diario["base"].values * rpo).round(2)}))
    contrib = pd.concat(linhas, ignore_index=True)
    contrib.to_csv(vd / "contribuicao_diaria.csv", index=False)

    # por UF (componentes da demanda esperada)
    reg = [pd.DataFrame({"data": np.repeat(datas.date, len(UF_LISTA)), "uf": np.tile(UF_LISTA, len(datas)),
                         "componente": "base", "pedidos_esperados": dem.base_uf.ravel().round(5)})]
    for c in CANAIS:
        reg.append(pd.DataFrame({"data": np.repeat(datas.date, len(UF_LISTA)), "uf": np.tile(UF_LISTA, len(datas)),
                                 "componente": c, "pedidos_esperados": dem.inc_uf[c].ravel().round(5)}))
    pd.concat(reg, ignore_index=True).to_csv(vd / "contribuicao_regional_diaria.csv.gz", index=False)

    # ---- ROI médio e marginal por canal do MMM; curvas de resposta nas últimas 13 semanas
    janela = np.zeros(len(datas), bool)
    janela[-JANELA_CURVA_DIAS:] = True
    rois, curvas = [], []
    grupos = sorted(set(canal_mmm.values()) - {"email_crm"})
    for g in grupos:
        finos = [c for c in CANAIS if canal_mmm[c] == g]
        inv_total = sum(dem.investimento[c].values.sum() for c in finos)
        rec_total = contrib[contrib.canal_mmm == g].receita_incremental.sum()
        inv_jan = sum(dem.investimento[c].values[janela].sum() for c in finos)

        def receita_janela(m):
            mult = np.where(janela, m, 1.0)
            return sum((dem.simular_canal(c, mult) * rpo)[janela].sum() for c in finos)

        r_jan = receita_janela(1.0)
        marg = (receita_janela(1.05) - receita_janela(0.95)) / (0.10 * inv_jan) if inv_jan > 0 else np.nan
        rois.append({"canal_mmm": g, "investimento_total": round(inv_total, 2),
                     "receita_incremental_total": round(rec_total, 2), "roi_total": rec_total / inv_total,
                     "investimento_13s": round(inv_jan, 2), "receita_incremental_13s": round(r_jan, 2),
                     "roi_13s": r_jan / inv_jan if inv_jan > 0 else np.nan, "roi_marginal_13s": marg})
        for m in MULTIPLICADORES:
            curvas.append({"canal_mmm": g, "multiplicador": m, "investimento_13s": round(inv_jan * m, 2),
                           "receita_incremental_13s": round(receita_janela(m), 2)})
    pd.DataFrame(rois).to_csv(vd / "roi_canal_mmm.csv", index=False)
    pd.DataFrame(curvas).to_csv(vd / "curvas_resposta.csv", index=False)

    # ---- efeito verdadeiro do geo-lift
    t = PARAM["teste_geo"]
    trat = ufs_tratamento()
    jan_teste = janela_teste(datas)
    jan_resf = (datas >= pd.Timestamp(t["inicio"])) & (datas <= pd.Timestamp(t["resfriamento_fim"]))
    perdido = sum((dem.inc_uf_sem_teste[c] - dem.inc_uf[c])[:, trat].sum(1) for c in t["canais_finos"])
    real_trat = dem.base_uf[:, trat].sum(1) + sum(dem.inc_uf[c][:, trat].sum(1) for c in CANAIS)
    cf_trat = real_trat + perdido
    inv_removido = sum((dem.investimento[c].values / midia.fator_teste[c].values - dem.investimento[c].values)
                       for c in t["canais_finos"])
    serie = pd.DataFrame({"data": datas.date, "receita_esperada_tratamento": (real_trat * rpo).round(2),
                          "receita_esperada_tratamento_sem_teste": (cf_trat * rpo).round(2),
                          "investimento_meta_removido": inv_removido.round(2)})
    pre = (datas >= pd.Timestamp(t["pre_inicio"])) & (datas < pd.Timestamp(t["inicio"]))
    serie[pre | jan_resf].to_csv(vd / "geolift_serie_verdade.csv", index=False)
    res = {
        "teste_id": t["teste_id"], "canal": t["canal"], "ufs_tratamento": t["ufs_tratamento"],
        "inicio": t["inicio"], "fim": t["fim"], "resfriamento_fim": t["resfriamento_fim"],
        "receita_perdida_teste": round(float((perdido * rpo)[jan_teste].sum()), 2),
        "receita_perdida_teste_mais_resfriamento": round(float((perdido * rpo)[jan_resf].sum()), 2),
        "pedidos_perdidos_teste": round(float(perdido[jan_teste].sum()), 2),
        "lift_relativo_teste": float(perdido[jan_teste].sum() / cf_trat[jan_teste].sum()),
        "investimento_removido": round(float(inv_removido[jan_teste].sum()), 2),
        "iroas_teste": float((perdido * rpo)[jan_resf].sum() / inv_removido[jan_teste].sum()),
        "receita_media_dia_tratamento_sem_teste": round(float((cf_trat * rpo)[jan_teste].mean()), 2),
        "nota": "Receita perdida = contrafactual sem o teste - real, nas UFs de tratamento, em receita esperada. "
                "iroas_teste usa a janela com resfriamento (carryover do adstock) sobre o investimento removido.",
    }
    (vd / "geolift_verdade.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    (vd / "resumo.json").write_text(json.dumps({"escala": CFG.escala, "seed": CFG.seed, "linhas": esc.linhas},
                                               indent=2, ensure_ascii=False))
