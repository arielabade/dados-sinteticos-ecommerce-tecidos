"""Gravação de CSVs prontos para LOAD DATA INFILE (NULL = \\N)."""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CFG


class Escritor:
    def __init__(self, pasta: Path | None = None):
        self.pasta = Path(pasta or CFG.saida)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self._iniciados: set[str] = set()
        self.linhas: dict[str, int] = {}

    def caminho(self, tabela: str) -> Path:
        return self.pasta / f"{tabela}.csv"

    def gravar(self, tabela: str, df: pd.DataFrame, colunas: list[str] | None = None):
        """Grava (ou acrescenta, se já iniciado) o DataFrame. Colunas com prefixo _ são internas."""
        cols = colunas or [c for c in df.columns if not c.startswith("_")]
        out = df[cols].copy()
        for c in out.columns:
            s = out[c]
            if pd.api.types.is_datetime64_any_dtype(s):
                ms = s.dt.strftime("%Y-%m-%d %H:%M:%S.%f").str[:-3]
                out[c] = ms.where(s.notna(), None)
            elif s.dtype == object:
                # objetos podem conter Timestamp/date/None misturados
                out[c] = s.map(_fmt)
            elif pd.api.types.is_float_dtype(s):
                out[c] = s.round(6)
            elif pd.api.types.is_bool_dtype(s):
                out[c] = s.astype(int)
        modo = "a" if tabela in self._iniciados else "w"
        out.to_csv(self.caminho(tabela), mode=modo, header=(modo == "w"), index=False, na_rep="\\N",
                   quoting=csv.QUOTE_MINIMAL, lineterminator="\n", float_format="%.6g" if False else None)
        self._iniciados.add(tabela)
        self.linhas[tabela] = self.linhas.get(tabela, 0) + len(out)


def _fmt(v):
    if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NaT:
        return None
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, (np.bool_, bool)):
        return int(v)
    return v
