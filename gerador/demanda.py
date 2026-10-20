"""Verdade de negócio: pedidos diários por UF = base orgânica (tendência,
sazonalidade, datas comerciais, preço, feriados) + efeito incremental de cada
canal de mídia naquela UF (adstock geométrico + saturação de Hill).

Por UF r, dia t e canal c:

    A[c,r,t]   = adstock(investimento efetivo do canal c na UF r)
    inc[c,r,t] = beta_c * pi[c,r] * hill(A[c,r,t] / pi[c,r]; K_c, a_c) * sazon_t^0.6
    base[r,t]  = base_t * peso_r * exp(AR(1) da UF)
    base_t     = nível * tendência * sazonalidade * (índice de preço)^-elasticidade * feriado * ruído

pi[c,r] é a participação de longo prazo da UF no investimento do canal. Quando
a UF recebe exatamente essa participação, a soma nacional é beta * hill(A
nacional), a mesma resposta da versão anterior do gerador. Quando o teste
geográfico zera a Meta numa UF, só aquela UF perde o efeito.

Esses parâmetros são a resposta certa que o MMM tenta recuperar. Eles são
salvos em data/ground_truth/ e não vão para o MySQL.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import CFG
from .midia import CANAIS_MMM, Midia
from .regional import CANAIS, NUF, PARAM, CanaisNovos, feriados, geo_alvo

TICKET_REFERENCIA = 270.0  # R$, usado só para calibrar o efeito em pedidos

MOTORES = ["base"] + CANAIS
# Probabilidade de o pedido ser de cliente novo, por "motor" do pedido.
PESO_NOVO = {"base": 0.19, **{c: p["peso_novo"] for c, p in PARAM["canais"].items()}}


@dataclass
class Demanda:
    diario: pd.DataFrame       # nacional: base, inc_<canal>, esperado, pedidos_alvo
    params: pd.DataFrame       # parâmetros verdadeiros por canal
    base_uf: np.ndarray        # [dia x UF] pedidos esperados da base
    inc_uf: dict               # {canal: [dia x UF]} pedidos incrementais esperados
    inc_uf_sem_teste: dict     # idem, contrafactual sem o teste geográfico (só canais testados)
    componentes_base: pd.DataFrame  # decomposição multiplicativa da base nacional
    investimento: pd.DataFrame      # [dia x canal] investimento nacional
    efetivo: pd.DataFrame           # [dia x canal] dose efetiva nacional
    part: dict                      # {canal: [dia x UF]} participação diária das UFs
    sazon: np.ndarray

    def simular_canal(self, canal: str, multiplicador: np.ndarray) -> np.ndarray:
        """Pedidos incrementais esperados por dia (nacional) se o investimento do
        canal fosse multiplicado por `multiplicador` (vetor por dia).

        Usado só no ground truth: curvas de resposta e ROI marginal verdadeiros.
        """
        p = PARAM["canais"][canal]
        row = self.params.set_index("canal").loc[canal]
        pi = geo_alvo(canal)
        ef = self.efetivo[canal].values * multiplicador
        A = adstock(ef[:, None] * self.part[canal], p["decaimento"])
        r = pi[None, :] * hill(A / pi[None, :], row["hill_k"], p["hill_expoente"]) * self.sazon[:, None] ** 0.6
        return row["beta_pedidos_dia"] * r.sum(1)


def adstock(x: np.ndarray, decay: float) -> np.ndarray:
    """Adstock geométrico ao longo do eixo 0 (aceita vetor ou matriz dia x UF)."""
    out = np.zeros_like(x, dtype=float)
    acc = np.zeros(x.shape[1:]) if x.ndim > 1 else 0.0
    for i in range(x.shape[0]):
        acc = x[i] + decay * acc
        out[i] = acc
    return out


def hill(x: np.ndarray, k: float, a: float) -> np.ndarray:
    x = np.maximum(x, 0)
    return x ** a / (x ** a + k ** a)


def indice_preco(cat) -> np.ndarray:
    """Preço efetivo / preço de tabela, ponderado pela popularidade das variantes ativas."""
    preco_ef = np.where(np.isnan(cat.preco_promo), cat.preco_tabela, cat.preco_promo)
    w = cat.variantes["_pop"].values[:, None] * cat.ativo
    return (w * preco_ef / cat.preco_tabela).sum(0) / w.sum(0)


def gerar_demanda(cal: pd.DataFrame, cat, midia: Midia, novos: CanaisNovos,
                  part: dict, part_sem_teste: dict) -> Demanda:
    rng = CFG.rng("demanda")
    datas = CFG.datas
    n = len(cal)
    sazon = (cal["dia_semana"] * cal["eventos"] * cal["salario"]).values
    ruido = np.exp(_ar1(rng, n, 0.6, 0.07))
    idx = indice_preco(cat)
    efeito_preco = (idx / np.median(idx)) ** (-PARAM["preco"]["elasticidade"])
    efeito_feriado = np.where(feriados(datas) != "", PARAM["feriado"]["multiplicador"], 1.0)
    nivel = CFG.pedidos_dia_inicio * PARAM["fator_base"] * CFG.escala
    base = nivel * cal["tendencia"].values * sazon * efeito_preco * efeito_feriado * ruido

    # base por UF: peso populacional x choque regional persistente
    reg = PARAM["regional"]
    peso = geo_alvo("email_crm")  # inclinação neutra = peso populacional
    choque = np.exp(_ar1_matriz(rng, n, NUF, reg["ar_base_uf"], reg["ruido_base_uf"]))
    choque = choque / choque.mean(0, keepdims=True)
    base_uf = base[:, None] * peso[None, :] * choque

    # investimento nacional por canal fino (pago) e "dose" efetiva
    inv = pd.concat([midia.investimento_canal, novos.nacional[["tiktok", "afiliados", "email_crm"]]], axis=1)[CANAIS]
    ef = pd.concat([midia.investimento_efetivo, novos.efetivo[["tiktok", "afiliados", "email_crm"]]], axis=1)[CANAIS]
    sem_teste = midia.fator_teste.reindex(columns=CANAIS).fillna(1.0)

    canais_teste = PARAM["teste_geo"]["canais_finos"]
    inc_uf, inc_sem, S, prm = {}, {}, {}, []
    for c in CANAIS:
        p = PARAM["canais"][c]
        pi = geo_alvo(c)
        A_nat = adstock(ef[c].values, p["decaimento"])
        ativo = A_nat > 1e-6
        k = p["k_rel"] * (A_nat[ativo].mean() if ativo.any() else 1.0)
        fator = sazon[:, None] ** 0.6

        def resposta(ef_nat, sh):
            A = adstock(ef_nat[:, None] * sh, p["decaimento"])
            return pi[None, :] * hill(A / pi[None, :], k, p["hill_expoente"]) * fator

        S[c] = resposta(ef[c].values, part[c])
        if c in canais_teste:
            # contrafactual: investimento nacional sem o corte e participação sem o zero nas UFs tratadas
            S[c + "_sem"] = resposta(ef[c].values / sem_teste[c].values, part_sem_teste[c])
        prm.append({"canal": c, "canal_mmm": p["canal_mmm"], "decaimento_adstock": p["decaimento"],
                    "hill_expoente": p["hill_expoente"], "hill_k": k, "iroas_alvo": p.get("iroas"),
                    "investimento_total": inv[c].values.sum()})

    # calibra beta: receita incremental total = iROAS-alvo x investimento total
    for c, row in zip(CANAIS, prm):
        if c == "email_crm":
            continue
        receita_alvo = row["iroas_alvo"] * row["investimento_total"]
        beta = receita_alvo / TICKET_REFERENCIA / max(S[c].sum(), 1e-9)
        row["beta_pedidos_dia"] = beta
        inc_uf[c] = beta * S[c]
        if c in canais_teste:
            inc_sem[c] = beta * S[c + "_sem"]
    # CRM: beta tal que o e-mail responda por ~participacao_pedidos dos pedidos
    outros = base_uf.sum() + sum(v.sum() for v in inc_uf.values())
    sh_email = PARAM["canais"]["email_crm"]["participacao_pedidos"]
    beta_e = sh_email / (1 - sh_email) * outros / max(S["email_crm"].sum(), 1e-9)
    prm[CANAIS.index("email_crm")]["beta_pedidos_dia"] = beta_e
    inc_uf["email_crm"] = beta_e * S["email_crm"]

    out = {"base": base_uf.sum(1)}
    for c in CANAIS:
        out[f"inc_{c}"] = inc_uf[c].sum(1)
    df = pd.DataFrame(out, index=cal.index)
    df["esperado"] = df.sum(axis=1)
    df["pedidos_alvo"] = rng.poisson(df["esperado"].values)
    comp = pd.DataFrame({"nivel": nivel, "tendencia": cal["tendencia"].values, "dia_semana": cal["dia_semana"].values,
                         "eventos": cal["eventos"].values, "salario": cal["salario"].values,
                         "indice_preco": idx, "efeito_preco": efeito_preco, "efeito_feriado": efeito_feriado,
                         "ruido": ruido, "base": base}, index=cal.index)
    return Demanda(df, pd.DataFrame(prm), base_uf, inc_uf, inc_sem, comp, inv, ef, part, sazon)


def _ar1(rng, n, phi, sigma):
    e = rng.normal(0, sigma, n)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def _ar1_matriz(rng, n, k, phi, sigma):
    e = rng.normal(0, sigma, (n, k))
    x = np.zeros((n, k))
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


# mantidos para compatibilidade com quem importava daqui
__all__ = ["Demanda", "adstock", "hill", "gerar_demanda", "MOTORES", "PESO_NOVO", "CANAIS_MMM"]
