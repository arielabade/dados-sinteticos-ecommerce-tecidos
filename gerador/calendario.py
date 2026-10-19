"""Calendário de demanda: tendência, dia da semana, datas comerciais e
sazonalidade por categoria de tecido."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CFG

# Segunda a domingo. Costureiras e ateliês compram no início da semana para
# produzir; o sábado é o dia mais fraco do varejo online de tecidos.
MULT_DIA_SEMANA = np.array([1.13, 1.10, 1.04, 1.00, 0.92, 0.82, 0.99])

BLACK_FRIDAY = ["2023-11-24", "2024-11-29", "2025-11-28"]
CARNAVAL = ["2024-02-13", "2025-03-04", "2026-02-17"]
DIA_DAS_MAES = ["2024-05-12", "2025-05-11", "2026-05-10"]
SAO_JOAO = ["2024-06-24", "2025-06-24", "2026-06-24"]


def _janela(datas: pd.DatetimeIndex, centro: str, antes: int, depois: int, pico: float,
            forma: str = "rampa") -> np.ndarray:
    """Multiplicador (>=1) que sobe até `pico` no dia central e decai depois."""
    c = pd.Timestamp(centro)
    dias = (datas - c).days.values.astype(float)
    m = np.ones(len(datas))
    pre = (dias >= -antes) & (dias <= 0)
    pos = (dias > 0) & (dias <= depois)
    if forma == "rampa":
        m[pre] = 1 + (pico - 1) * (1 - (-dias[pre]) / (antes + 1)) ** 1.5
        m[pos] = 1 + (pico - 1) * (1 - dias[pos] / (depois + 1)) ** 2
    else:  # platô
        m[pre | pos] = pico
    return m


def calendario() -> pd.DataFrame:
    d = CFG.datas
    n = len(d)
    t_anos = (d - d[0]).days.values / 365.25

    # Tendência: crescimento composto com leve desaceleração no 3º ano.
    tendencia = (1 + CFG.crescimento_anual) ** t_anos * (1 - 0.035 * np.maximum(t_anos - 2, 0))

    dia_semana = MULT_DIA_SEMANA[d.dayofweek.values]

    ev = np.ones(n)
    rotulo = np.array([""] * n, dtype=object)

    def aplica(m: np.ndarray, nome: str):
        nonlocal ev
        ev = ev * m
        rotulo[m > 1.05] = np.where(rotulo[m > 1.05] == "", nome, rotulo[m > 1.05] + "|" + nome)

    for bf in BLACK_FRIDAY:
        bf_t = pd.Timestamp(bf)
        m = _janela(d, bf, 10, 0, 1.6)  # esquenta
        m[d == bf_t] = 3.4
        m[d == bf_t + pd.Timedelta(days=1)] = 2.1
        m[d == bf_t + pd.Timedelta(days=2)] = 1.7
        m[d == bf_t + pd.Timedelta(days=3)] = 2.0  # Cyber Monday
        # ressaca pós-BF
        ress = (d > bf_t + pd.Timedelta(days=3)) & (d <= bf_t + pd.Timedelta(days=9))
        m[ress] = 0.88
        aplica(m, "black_friday")

    for ano in (2023, 2024, 2025):
        # Natal: costura de presentes e enfeites até ~18/12, depois queda forte.
        m = np.ones(n)
        natal = (d >= f"{ano}-12-01") & (d <= f"{ano}-12-18")
        m[natal] = 1.22
        fim_ano = (d >= f"{ano}-12-22") & (d <= f"{ano+1}-01-06")
        m[fim_ano] = 0.62
        aplica(m, "natal")

    for ano in (2024, 2025, 2026):
        # Volta às aulas: uniformes, aventais escolares, material de artesanato.
        aplica(_janela(d, f"{ano}-02-05", 18, 18, 1.18), "volta_as_aulas")
        aplica(_janela(d, f"{ano}-07-28", 8, 8, 1.07), "volta_as_aulas")
        # Dia do Consumidor (15/03) e Dia da Costureira (25/05): datas promocionais da loja.
        aplica(_janela(d, f"{ano}-03-15", 3, 1, 1.35), "dia_do_consumidor")
        aplica(_janela(d, f"{ano}-05-25", 2, 0, 1.45), "dia_da_costureira")

    for c in CARNAVAL:
        aplica(_janela(d, c, 21, 0, 1.20), "carnaval")
    for c in DIA_DAS_MAES:
        aplica(_janela(d, c, 16, 0, 1.22), "dia_das_maes")
    for c in SAO_JOAO:
        aplica(_janela(d, c, 40, 10, 1.30), "festa_junina")

    # Efeito salário: dias 5-10 do mês.
    salario = np.where((d.day >= 5) & (d.day <= 10), 1.06, 1.0)

    return pd.DataFrame(
        {
            "tendencia": tendencia,
            "dia_semana": dia_semana,
            "eventos": ev,
            "salario": salario,
            "rotulo_evento": rotulo,
        },
        index=d,
    )


# Sazonalidade por família de tecido (multiplicador mensal da preferência
# relativa no mix de itens, jan..dez). Malha e moletom no frio; linho e
# viscose no verão; chita e xadrez em maio-junho.
SAZONALIDADE_CATEGORIA = {
    "algodao":   [1.00, 1.05, 1.00, 0.98, 1.00, 1.02, 0.98, 1.00, 1.00, 1.00, 1.02, 1.05],
    "chita":     [0.70, 1.20, 0.80, 0.90, 1.90, 2.80, 1.30, 0.70, 0.60, 0.60, 0.70, 0.80],
    "linho":     [1.25, 1.20, 1.05, 0.90, 0.80, 0.70, 0.70, 0.80, 0.95, 1.10, 1.25, 1.35],
    "viscose":   [1.25, 1.20, 1.05, 0.90, 0.80, 0.75, 0.75, 0.85, 1.00, 1.15, 1.25, 1.20],
    "malha":     [0.80, 0.85, 0.95, 1.15, 1.30, 1.35, 1.30, 1.15, 0.95, 0.85, 0.80, 0.80],
    "sintetico": [1.05, 1.60, 1.00, 0.95, 0.95, 1.00, 0.95, 0.95, 0.95, 1.05, 1.10, 1.35],
    "jeans":     [0.95, 1.00, 1.05, 1.05, 1.05, 1.05, 1.00, 1.00, 1.00, 0.95, 0.95, 0.95],
}


def mult_categoria(familia: str, datas: pd.DatetimeIndex) -> np.ndarray:
    return np.asarray(SAZONALIDADE_CATEGORIA[familia])[datas.month.values - 1]
