"""Parâmetros globais da geração.

Tudo que é aleatório sai de geradores numpy derivados de SEED, então a mesma
versão do código com a mesma ESCALA produz exatamente os mesmos arquivos.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Config:
    seed: int = 20231001
    inicio: pd.Timestamp = pd.Timestamp("2023-10-01")
    fim: pd.Timestamp = pd.Timestamp("2026-10-13")  # último dia completo antes de 14/10/2026
    # ESCALA multiplica volumes (pedidos, sessões, clientes, investimento).
    # 1.0 = ~150 mil pedidos / ~4 milhões de sessões. Use 0.05 para testes rápidos.
    escala: float = float(os.environ.get("ESCALA", "1.0"))
    saida: Path = Path(os.environ.get("SAIDA_DADOS", RAIZ / "data" / "csv"))
    verdade: Path = Path(os.environ.get("SAIDA_VERDADE", RAIZ / "data" / "verdade"))

    # Volume-alvo na escala 1.0
    pedidos_dia_inicio: float = 84.0  # out/2023, antes de sazonalidade e mídia
    crescimento_anual: float = 0.30
    clientes_legado: int = 3200  # base importada da plataforma anterior
    taxa_pedido_sem_rastreio: float = 0.13  # adblock, ITP, navegador sem JS
    taxa_pedido_whatsapp: float = 0.045

    datas: pd.DatetimeIndex = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "datas", pd.date_range(self.inicio, self.fim, freq="D"))

    def rng(self, nome: str) -> np.random.Generator:
        """Gerador independente por módulo: mudar um módulo não altera os outros."""
        sub = sum(ord(c) * (i + 1) for i, c in enumerate(nome))
        return np.random.default_rng([self.seed, sub])


CFG = Config()
