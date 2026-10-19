"""Verdade de negócio: pedidos diários = base orgânica + efeito incremental
de cada canal de mídia (adstock geométrico + saturação de Hill).

Esses parâmetros são a resposta certa que o notebook de MMM tenta recuperar.
Eles são salvos em data/verdade/ e não vão para o MySQL.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import CFG
from .midia import CANAIS_MMM, Midia

TICKET_REFERENCIA = 270.0  # R$, usado só para calibrar o efeito em pedidos

# canal: (decaimento do adstock, expoente Hill, K relativo à média, iROAS-alvo médio)
PARAMS_CANAL = {
    "meta_prospeccao":      (0.55, 1.15, 1.10, 2.40),
    "meta_remarketing":     (0.20, 1.00, 0.80, 0.80),
    "google_marca":         (0.10, 1.00, 0.70, 0.60),
    "google_search":        (0.25, 1.10, 1.00, 2.00),
    "google_shopping_pmax": (0.35, 1.10, 1.00, 1.90),
    "google_demand_gen":    (0.60, 1.20, 1.00, 0.35),
}

# Probabilidade de o pedido ser de cliente novo, por "motor" do pedido.
PESO_NOVO = {"base": 0.19, "meta_prospeccao": 0.66, "meta_remarketing": 0.24, "google_marca": 0.22,
             "google_search": 0.52, "google_shopping_pmax": 0.45, "google_demand_gen": 0.65}


@dataclass
class Demanda:
    diario: pd.DataFrame       # base, inc_<canal>, esperado, pedidos_alvo
    params: pd.DataFrame       # parâmetros verdadeiros por canal


def adstock(x: np.ndarray, decay: float) -> np.ndarray:
    out = np.zeros_like(x, dtype=float)
    acc = 0.0
    for i, v in enumerate(x):
        acc = v + decay * acc
        out[i] = acc
    return out


def hill(x: np.ndarray, k: float, a: float) -> np.ndarray:
    x = np.maximum(x, 0)
    return x ** a / (x ** a + k ** a)


def gerar_demanda(cal: pd.DataFrame, midia: Midia) -> Demanda:
    rng = CFG.rng("demanda")
    n = len(cal)
    sazon = (cal["dia_semana"] * cal["eventos"] * cal["salario"]).values
    ruido = np.exp(_ar1(rng, n, 0.6, 0.07))
    base = CFG.pedidos_dia_inicio * 0.78 * CFG.escala * cal["tendencia"].values * sazon * ruido

    out = {"base": base}
    prm = []
    inv = midia.investimento_canal
    ef = midia.investimento_efetivo
    for c in CANAIS_MMM:
        decay, a, krel, iroas = PARAMS_CANAL[c]
        A = adstock(ef[c].values, decay)
        ativo = A > 1e-6
        k = krel * (A[ativo].mean() if ativo.any() else 1.0)
        s = hill(A, k, a) * sazon ** 0.6
        # calibra beta para o iROAS médio-alvo do canal
        receita_alvo = iroas * inv[c].values.sum()
        beta = receita_alvo / TICKET_REFERENCIA / max(s.sum(), 1e-9)
        out[f"inc_{c}"] = beta * s
        prm.append({"canal": c, "decaimento_adstock": decay, "hill_expoente": a, "hill_k": k,
                    "beta_pedidos_dia": beta, "iroas_alvo": iroas,
                    "investimento_total": inv[c].values.sum()})
    df = pd.DataFrame(out, index=cal.index)
    df["esperado"] = df.sum(axis=1)
    df["pedidos_alvo"] = rng.poisson(df["esperado"].values)
    return Demanda(df, pd.DataFrame(prm))


def _ar1(rng, n, phi, sigma):
    e = rng.normal(0, sigma, n)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x
