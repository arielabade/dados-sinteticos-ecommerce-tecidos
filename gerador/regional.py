"""Camada regional da mídia, canais novos (TikTok, afiliados, CRM), teste
geográfico (geo-lift) e calendário comercial.

Papel no gerador
----------------
* Distribui o investimento diário de cada canal entre as 27 UFs. A demanda
  (demanda.py) responde ao investimento de cada UF, então as vendas por UF
  carregam o efeito da mídia daquela UF.
* Gera os canais que não existiam na versão anterior: TikTok Ads (comprado
  junto com a Meta, por isso muito correlacionado com ela), afiliados e
  disparos de CRM.
* Aplica o teste geográfico: a Meta é desligada nas UFs de tratamento.
* Monta as tabelas novas do banco: canais_midia, regioes,
  midia_regional_diaria, calendario_comercial, testes_geo e
  testes_geo_regioes.

Parâmetros em gerador/parametros_mmm.yaml. Este módulo não importa midia.py
(midia.py importa daqui), para evitar import circular.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .clientes import REGIAO, UF_LISTA, UF_PESO
from .config import CFG

PARAM = yaml.safe_load(Path(__file__).with_name("parametros_mmm.yaml").read_text(encoding="utf-8"))
CANAIS = list(PARAM["canais"])                       # canais finos, na ordem do canal_id
CANAIS_NOVOS = ["tiktok", "afiliados", "email_crm"]
NUF = len(UF_LISTA)
REG_UF = np.array([REGIAO[u] for u in UF_LISTA])

UF_NOME = {
    "SP": "São Paulo", "RJ": "Rio de Janeiro", "MG": "Minas Gerais", "PR": "Paraná", "SC": "Santa Catarina",
    "RS": "Rio Grande do Sul", "BA": "Bahia", "PE": "Pernambuco", "DF": "Distrito Federal", "GO": "Goiás",
    "CE": "Ceará", "ES": "Espírito Santo", "PA": "Pará", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "PB": "Paraíba", "RN": "Rio Grande do Norte", "AM": "Amazonas", "MA": "Maranhão", "AL": "Alagoas",
    "PI": "Piauí", "SE": "Sergipe", "RO": "Rondônia", "TO": "Tocantins", "AC": "Acre", "AP": "Amapá",
    "RR": "Roraima",
}
MACRO_NOME = {"SE": "Sudeste", "S": "Sul", "CO": "Centro-Oeste", "NE": "Nordeste", "N": "Norte"}


# ---------------------------------------------------------------- geografia
def geo_alvo(canal: str) -> np.ndarray:
    """Participação de longo prazo de cada UF no investimento do canal (soma 1)."""
    incl = PARAM["regional"]["inclinacao"][canal]
    w = UF_PESO * np.array([incl[r] for r in REG_UF])
    return w / w.sum()


def ufs_tratamento() -> np.ndarray:
    """Máscara booleana (27) das UFs de tratamento do teste geográfico."""
    return np.isin(UF_LISTA, PARAM["teste_geo"]["ufs_tratamento"])


def janela_teste(datas: pd.DatetimeIndex) -> np.ndarray:
    t = PARAM["teste_geo"]
    return (datas >= pd.Timestamp(t["inicio"])) & (datas <= pd.Timestamp(t["fim"]))


def fator_teste_geo(datas: pd.DatetimeIndex) -> pd.DataFrame:
    """Multiplicador do investimento NACIONAL de cada canal por dia.

    Fora do teste é 1. Durante o teste, os canais testados perdem a fatia das
    UFs de tratamento (a verba não é realocada para o controle).
    """
    f = pd.DataFrame(1.0, index=datas, columns=CANAIS)
    t = PARAM["teste_geo"]
    trat = ufs_tratamento()
    jan = janela_teste(datas)
    for c in t["canais_finos"]:
        fatia = geo_alvo(c)[trat].sum()
        f.loc[jan, c] = 1 - fatia * (1 - t["multiplicador_investimento"])
    return f


def participacoes(datas: pd.DatetimeIndex) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Participação diária de cada UF no investimento de cada canal.

    Retorna (com_teste, sem_teste), cada um {canal: array [dia x UF]} com linhas
    somando 1. `sem_teste` é o contrafactual usado só no ground truth do
    geo-lift: o que teria acontecido se a Meta não tivesse sido desligada.
    """
    rng = CFG.rng("regional_participacao")
    nd = len(datas)
    sig = PARAM["regional"]["ruido_participacao"]
    trat = ufs_tratamento()
    jan = janela_teste(datas)
    t = PARAM["teste_geo"]
    com, sem = {}, {}
    for c in CANAIS:
        pi = geo_alvo(c)
        sh = pi[None, :] * rng.lognormal(0, sig, (nd, NUF))
        sh = sh / sh.sum(1, keepdims=True)
        sem[c] = sh
        if c in t["canais_finos"]:
            sh = sh.copy()
            sh[np.ix_(jan, trat)] *= t["multiplicador_investimento"]
            sh = sh / sh.sum(1, keepdims=True)
        com[c] = sh
    return com, sem


def _reparte_inteiro(total: np.ndarray, pesos: np.ndarray) -> np.ndarray:
    """Divide inteiros por linha segundo pesos, preservando a soma (maiores restos)."""
    total = np.asarray(total, dtype=np.int64)
    p = pesos / np.where(pesos.sum(1, keepdims=True) == 0, 1, pesos.sum(1, keepdims=True))
    bruto = total[:, None] * p
    base = np.floor(bruto).astype(np.int64)
    falta = total - base.sum(1)
    resto = bruto - base
    ordem = np.argsort(-resto, axis=1)
    for i in np.where(falta > 0)[0]:
        base[i, ordem[i, :falta[i]]] += 1
    return base


def _reparte_centavos(total: np.ndarray, pesos: np.ndarray) -> np.ndarray:
    """Divide valores em R$ por linha preservando a soma em centavos."""
    cent = np.round(np.asarray(total) * 100).astype(np.int64)
    return _reparte_inteiro(cent, pesos) / 100.0


# ---------------------------------------------------------------- canais novos
@dataclass
class CanaisNovos:
    tiktok_campanhas: pd.DataFrame
    tiktok_entrega: pd.DataFrame       # data, campanha_id, investimento, impressoes, cliques
    afiliados_parceiros: pd.DataFrame
    afiliados_entrega: pd.DataFrame    # data, parceiro_id, investimento, cliques
    crm_disparos: pd.DataFrame         # um disparo por (data, tipo de campanha)
    nacional: pd.DataFrame             # [data x canal novo] investimento (CRM: custo)
    efetivo: pd.DataFrame              # [data x canal novo] "dose" que move a demanda (CRM: e-mails entregues)


def gerar_canais_novos(inv_meta_planejado: np.ndarray) -> CanaisNovos:
    """TikTok, afiliados e CRM em nível nacional diário.

    `inv_meta_planejado` é o investimento diário da Meta antes do corte do
    teste geográfico: o TikTok segue o plano da equipe de social, não o teste.
    """
    datas = CFG.datas
    nd = len(datas)
    esc = CFG.escala

    # ---- TikTok: ~32% do orçamento da Meta, todo dia (o par correlacionado)
    rng = CFG.rng("tiktok")
    tk = PARAM["tiktok"]
    total = tk["razao_orcamento_meta"] * inv_meta_planejado * rng.lognormal(0, tk["ruido"], nd)
    cpm_saz = np.where(datas.month == 11, 1.3, np.where(datas.month == 12, 1.2, 1.0))
    camp_rows, ent = [], []
    pesos = []
    for i, (nome, obj, ini, fim, part) in enumerate(tk["campanhas"]):
        ativo = (datas >= pd.Timestamp(ini)) & (datas <= (pd.Timestamp(fim) if fim else CFG.fim))
        pesos.append(part * ativo)
        camp_rows.append({"campanha_id": 1790000000000000 + (i + 1) * 7577, "conta_id": tk["conta_id"],
                          "nome": nome, "objetivo": obj, "status": "ENABLE" if fim is None else "DISABLE",
                          "inicio": pd.Timestamp(ini).date(), "fim": None if fim is None else pd.Timestamp(fim).date()})
    W = np.array(pesos)
    W = W / np.where(W.sum(0) == 0, 1, W.sum(0))
    for i, c in enumerate(camp_rows):
        inv = np.round(total * W[i], 2)
        m = inv >= 0.5
        cpm = tk["cpm"] * cpm_saz * rng.lognormal(0, 0.12, nd) * (0.8 if c["objetivo"] == "REACH" else 1.0)
        imp = np.floor(inv / cpm * 1000).astype(np.int64)
        ctr = tk["ctr"] * rng.lognormal(0, 0.15, nd) * (0.45 if c["objetivo"] == "REACH" else 1.0)
        cli = rng.binomial(imp, np.clip(ctr, 0, 0.2))
        ent.append(pd.DataFrame({"data": datas[m], "campanha_id": c["campanha_id"], "investimento": inv[m],
                                 "impressoes": imp[m], "cliques": cli[m]}))
    tiktok_entrega = pd.concat(ent, ignore_index=True)
    tiktok_campanhas = pd.DataFrame(camp_rows)

    # ---- Afiliados: orçamento mensal negociado em degraus + bônus em promoções
    rng = CFG.rng("afiliados")
    af = PARAM["afiliados"]
    trimestre = ((datas.year - datas[0].year) * 12 + datas.month - datas[0].month) // 3
    orc_mes = np.array(af["orcamento_mensal"])[np.clip(trimestre, 0, len(af["orcamento_mensal"]) - 1)]
    promo = calendario_promocoes(datas)
    orc_dia = orc_mes / datas.days_in_month * esc * np.where(promo != "", af["bonus_promocao"], 1.0)
    par_rows, ent = [], []
    for i, (nome, tipo, com, part, ini) in enumerate(af["parceiros"]):
        par_rows.append({"parceiro_id": i + 1, "nome": nome, "tipo": tipo, "comissao_pct": com,
                         "inicio": pd.Timestamp(ini).date(), "ativo": 1})
    W = np.array([p[3] * (datas >= pd.Timestamp(p[4])) for p in af["parceiros"]], float)
    W = W / W.sum(0)
    for i, p in enumerate(par_rows):
        inv = np.round(orc_dia * W[i] * rng.lognormal(0, 0.25, nd), 2)
        m = inv >= 0.5
        cli = rng.poisson(inv / af["cpc"] * rng.lognormal(0, 0.15, nd))
        ent.append(pd.DataFrame({"data": datas[m], "parceiro_id": p["parceiro_id"], "investimento": inv[m],
                                 "cliques": cli[m]}))
    afiliados_entrega = pd.concat(ent, ignore_index=True)

    # ---- CRM: base de contatos crescendo; newsletter ter/qui, réguas diárias
    rng = CFG.rng("crm")
    cr = PARAM["crm"]
    meses = (datas.year - datas[0].year) * 12 + datas.month - datas[0].month + (datas.day - 1) / datas.days_in_month
    base = cr["base_inicial"] * esc * (1 + cr["crescimento_mensal"]) ** meses.values
    disp = []
    for tipo, dias_semana, frac in cr["campanhas"]:
        m = np.isin(datas.dayofweek, dias_semana)
        env = np.floor(base * frac * rng.lognormal(0, 0.06, nd)).astype(np.int64) * m
        entr = rng.binomial(env, cr["taxa_entrega"])
        abert = rng.binomial(entr, np.clip(cr["taxa_abertura"] * rng.lognormal(0, 0.1, nd), 0, 0.9))
        cli = rng.binomial(entr, np.clip(cr["taxa_clique"] * rng.lognormal(0, 0.15, nd), 0, 0.5))
        cli = np.minimum(cli, abert)
        desc = rng.binomial(entr, 0.0012)
        disp.append(pd.DataFrame({"data": datas[m], "tipo_campanha": tipo, "enviados": env[m], "entregues": entr[m],
                                  "aberturas": abert[m], "cliques": cli[m], "descadastros": desc[m],
                                  "custo": np.round(env[m] / 1000 * cr["custo_mil_envios"], 2)}))
    crm = pd.concat(disp, ignore_index=True).sort_values(["data", "tipo_campanha"]).reset_index(drop=True)
    crm.insert(0, "disparo_id", np.arange(1, len(crm) + 1))

    nacional = pd.DataFrame(0.0, index=datas, columns=CANAIS_NOVOS)
    nacional["tiktok"] = tiktok_entrega.groupby("data").investimento.sum().reindex(datas, fill_value=0).values
    nacional["afiliados"] = afiliados_entrega.groupby("data").investimento.sum().reindex(datas, fill_value=0).values
    nacional["email_crm"] = crm.groupby("data").custo.sum().reindex(datas, fill_value=0).values
    efetivo = nacional.copy()
    efetivo["email_crm"] = crm.groupby("data").entregues.sum().reindex(datas, fill_value=0).values.astype(float)
    return CanaisNovos(tiktok_campanhas, tiktok_entrega, pd.DataFrame(par_rows), afiliados_entrega, crm,
                       nacional, efetivo)


# ---------------------------------------------------------------- calendário
def calendario_promocoes(datas: pd.DatetimeIndex) -> np.ndarray:
    """Nome da promoção da loja vigente em cada dia ('' = nenhuma)."""
    out = np.full(len(datas), "", dtype=object)
    md = datas.strftime("%m-%d")
    for nome, ini, fim in PARAM["promocoes"]:
        if ini <= fim:
            m = (md >= ini) & (md <= fim)
        else:  # atravessa a virada do ano
            m = (md >= ini) | (md <= fim)
        out[m & (out == "")] = nome
    return out


def feriados(datas: pd.DatetimeIndex) -> np.ndarray:
    nomes = dict((pd.Timestamp(d), n) for d, n in PARAM["feriados_nacionais"])
    return np.array([nomes.get(d, "") for d in datas], dtype=object)


def calendario_comercial(cal: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por dia: feriado nacional, data comercial e promoção da loja."""
    datas = CFG.datas
    fer = feriados(datas)
    promo = calendario_promocoes(datas)
    ev = cal["rotulo_evento"].values
    return pd.DataFrame({
        "data": datas.date,
        "dia_semana": datas.dayofweek + 1,  # 1 = segunda
        "feriado_nacional": (fer != "").astype(int),
        "nome_feriado": np.where(fer != "", fer, None),
        "evento_comercial": np.where(ev != "", ev, None),
        "promocao_loja": (promo != "").astype(int),
        "nome_promocao": np.where(promo != "", promo, None),
    })


# ---------------------------------------------------------------- tabelas do banco
def tabela_canais() -> pd.DataFrame:
    rows = []
    for c, p in PARAM["canais"].items():
        rows.append({"canal_id": p["canal_id"], "canal": c, "canal_mmm": p["canal_mmm"],
                     "plataforma": p["plataforma"], "tipo_investimento": p["tipo"]})
    return pd.DataFrame(rows)


def tabela_regioes() -> pd.DataFrame:
    return pd.DataFrame({
        "uf": UF_LISTA, "nome": [UF_NOME[u] for u in UF_LISTA], "macrorregiao": [MACRO_NOME[r] for r in REG_UF],
        "sigla_macrorregiao": REG_UF, "peso_populacional": np.round(UF_PESO, 6),
        "entrega_disponivel": 1,
    })


def tabelas_teste_geo() -> tuple[pd.DataFrame, pd.DataFrame]:
    t = PARAM["teste_geo"]
    canal_id = {p["canal_mmm"]: p["canal_id"] for p in PARAM["canais"].values()}[t["canal"]]
    teste = pd.DataFrame([{
        "teste_id": t["teste_id"], "nome": t["nome"], "canal_id": canal_id, "canal_mmm": t["canal"],
        "tipo_mudanca": t["tipo_mudanca"], "multiplicador_investimento": t["multiplicador_investimento"],
        "pre_inicio": pd.Timestamp(t["pre_inicio"]).date(), "inicio": pd.Timestamp(t["inicio"]).date(),
        "fim": pd.Timestamp(t["fim"]).date(), "resfriamento_fim": pd.Timestamp(t["resfriamento_fim"]).date(),
        "metrica_principal": "receita_paga",
        "descricao": "Meta Ads (prospecção, remarketing e sazonais) desligada nas UFs de tratamento. "
                     "A verba não foi realocada para as UFs de controle.",
    }])
    trat = ufs_tratamento()
    grupos = pd.DataFrame({"teste_id": t["teste_id"], "uf": UF_LISTA,
                           "grupo": np.where(trat, "tratamento", "controle")})
    return teste, grupos


def tabela_regional(datas: pd.DatetimeIndex, part: dict[str, np.ndarray], nacional: pd.DataFrame) -> pd.DataFrame:
    """Linha por (data, canal, UF) com investimento, impressões, cliques e conversões.

    `nacional` tem uma linha por (data, canal) com os totais que as plataformas
    reportam. A divisão por UF preserva as somas: investimento em centavos,
    impressões e cliques em unidades. Impressões custam menos fora do Sudeste
    (CPM) e o CTR varia por macrorregião.

    Conversões por UF: o relatório geográfico das plataformas só atribui
    conversões por clique, então o valor por UF é limitado aos cliques da UF.
    """
    rng = CFG.rng("regional_tabela")
    cpm = np.array([PARAM["regional"]["indice_cpm"][r] for r in REG_UF])
    ctr = np.array([PARAM["regional"]["indice_ctr"][r] for r in REG_UF])
    ids = tabela_canais().set_index("canal")["canal_id"]
    pos = pd.Series(np.arange(len(datas)), index=datas)
    out = []
    for c, g in nacional.groupby("canal"):
        g = g.sort_values("data")
        idx = pos.loc[g["data"]].values
        sh = part[c][idx]
        inv = _reparte_centavos(g["investimento"].values, sh)
        w_imp = sh / cpm[None, :] * rng.lognormal(0, 0.05, sh.shape)
        imp_nat = g["impressoes"].values
        tem_imp = ~pd.isna(imp_nat)
        imp = np.full(sh.shape, -1, np.int64)
        if tem_imp.any():
            imp[tem_imp] = _reparte_inteiro(imp_nat[tem_imp].astype(np.int64), w_imp[tem_imp])
        w_cli = np.where(imp >= 0, np.maximum(imp, 0), sh * 1000) * ctr[None, :]
        cli = _reparte_inteiro(g["cliques"].values.astype(np.int64), w_cli)
        conv_nat = g["conversoes"].values
        conv = np.round(np.minimum(conv_nat[:, None] * cli / np.maximum(cli.sum(1, keepdims=True), 1), cli), 2)
        conv = np.where(pd.isna(conv_nat)[:, None], np.nan, conv)
        n = sh.shape[0]
        out.append(pd.DataFrame({
            "data": np.repeat(g["data"].values, NUF), "canal_id": int(ids[c]), "uf": np.tile(UF_LISTA, n),
            "investimento": inv.ravel(), "impressoes": imp.ravel(), "cliques": cli.ravel(),
            "conversoes_plataforma": conv.ravel(),
        }))
    T = pd.concat(out, ignore_index=True)
    T["impressoes"] = pd.array(np.where(T.impressoes.values < 0, -1, T.impressoes.values), dtype="Int64")
    T.loc[T.impressoes == -1, "impressoes"] = pd.NA
    return T.sort_values(["data", "canal_id", "uf"]).reset_index(drop=True)


# ---------------------------------------------------------------- métricas reportadas
def metricas_canais_novos(novos: CanaisNovos, pedidos: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Conversões que TikTok e afiliados reportam, a partir dos pedidos reais.

    TikTok: reporta 75% dos pedidos que ele de fato gerou (clique ou
    visualização) e ainda reivindica ~4% dos demais pedidos do site em dias de
    veiculação (janela de visualização). Afiliados: reportam o pedido quando o
    último clique foi no link do parceiro, o que inclui sites de cupom
    capturando pedidos que já iam acontecer.
    """
    rng = CFG.rng("metricas_novos")
    datas = CFG.datas
    P = pedidos[(pedidos.canal_venda == "site") & (pedidos.pedido_teste == 0)]
    dia = P["_dia"].values.astype(int)
    motor = P["_motor"].values
    total = P["total"].values

    def credita(entrega: pd.DataFrame, chave: str, p_proprio: float, p_outros: float, motor_proprio: str):
        ids = entrega[chave].unique()
        W = np.zeros((len(ids), len(datas)))
        pos = {v: i for i, v in enumerate(ids)}
        dd = (entrega.data - datas[0]).dt.days.values
        W[[pos[v] for v in entrega[chave].values], dd] = entrega["cliques"].values + 1e-9
        ativo = W.sum(0) > 0
        p = np.where(motor == motor_proprio, p_proprio, p_outros) * ativo[dia]
        sel = rng.random(len(P)) < p
        cum = np.cumsum(W / np.where(W.sum(0) == 0, 1, W.sum(0)), axis=0)
        u = rng.random(sel.sum())
        quem = ids[np.argmax(cum[:, dia[sel]] > u[None, :], axis=0)]
        cred = pd.DataFrame({"data": datas[dia[sel]], chave: quem, "valor": total[sel]})
        agg = cred.groupby(["data", chave]).agg(conversoes=("valor", "size"), valor=("valor", "sum")).reset_index()
        out = entrega.merge(agg, on=["data", chave], how="left")
        out["conversoes"] = out.conversoes.fillna(0).astype(int)
        out["valor"] = out.valor.fillna(0).round(2)
        return out

    tk = credita(novos.tiktok_entrega, "campanha_id", 0.75, 0.04, "tiktok")
    tk = tk.rename(columns={"valor": "valor_conversoes"})
    # conversão reportada nunca passa de cliques + visualizações; no relatório diário
    # da campanha mantemos conversões <= cliques (atribuição por clique de 7 dias).
    tk["conversoes"] = np.minimum(tk.conversoes, tk.cliques)
    af = credita(novos.afiliados_entrega, "parceiro_id", 0.85, 0.015, "afiliados")
    af = af.rename(columns={"conversoes": "pedidos_atribuidos", "valor": "receita_atribuida"})
    af["pedidos_atribuidos"] = np.minimum(af.pedidos_atribuidos, af.cliques)
    return (tk[["data", "campanha_id", "investimento", "impressoes", "cliques", "conversoes", "valor_conversoes"]],
            af[["data", "parceiro_id", "investimento", "cliques", "pedidos_atribuidos", "receita_atribuida"]])


def totais_nacionais(midia, novos: CanaisNovos, meta_m: pd.DataFrame, google_m: pd.DataFrame,
                     tiktok_m: pd.DataFrame, afil_m: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por (data, canal fino) com os totais reportados pelas plataformas."""
    ad_canal = midia.meta_anuncios.set_index("anuncio_id")["_canal"]
    me = meta_m.assign(canal=meta_m.anuncio_id.map(ad_canal)).groupby(["data", "canal"]).agg(
        investimento=("investimento", "sum"), impressoes=("impressoes", "sum"), cliques=("cliques_link", "sum"),
        conversoes=("compras", "sum")).reset_index()
    gr_canal = midia.google_grupos.set_index("grupo_id")
    canal_g = np.where(gr_canal["_marca"] == 1, "google_marca", gr_canal["_canal"])
    canal_g = pd.Series(canal_g, index=gr_canal.index)
    ge = google_m.assign(canal=google_m.grupo_id.map(canal_g)).groupby(["data", "canal"]).agg(
        investimento=("investimento", "sum"), impressoes=("impressoes", "sum"), cliques=("cliques", "sum"),
        conversoes=("conversoes", "sum")).reset_index()
    tk = tiktok_m.groupby("data").agg(investimento=("investimento", "sum"), impressoes=("impressoes", "sum"),
                                      cliques=("cliques", "sum"), conversoes=("conversoes", "sum")).reset_index()
    tk["canal"] = "tiktok"
    af = afil_m.groupby("data").agg(investimento=("investimento", "sum"), cliques=("cliques", "sum"),
                                    conversoes=("pedidos_atribuidos", "sum")).reset_index()
    af["canal"] = "afiliados"
    af["impressoes"] = np.nan
    crm = novos.crm_disparos.groupby("data").agg(investimento=("custo", "sum"), impressoes=("entregues", "sum"),
                                                 cliques=("cliques", "sum")).reset_index()
    crm["canal"] = "email_crm"
    crm["conversoes"] = np.nan
    T = pd.concat([me, ge, tk, af, crm], ignore_index=True)
    T["data"] = pd.to_datetime(T["data"])
    T["impressoes"] = T["impressoes"].astype(float)
    return T[T.investimento > 0].reset_index(drop=True)
