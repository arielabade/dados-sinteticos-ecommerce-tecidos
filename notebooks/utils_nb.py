"""Funções compartilhadas pelos notebooks: conexão, consultas e tema dos gráficos."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from sqlalchemy import create_engine, text

RAIZ = Path(__file__).resolve().parents[1]
VERDADE = Path(os.environ.get("SAIDA_GROUND_TRUTH", RAIZ / "data" / "ground_truth"))

# Paleta: cores acessíveis e distinguíveis em claro e escuro
CORES = ["#2E6F95", "#E07A3F", "#3C9D74", "#B5485E", "#7B61A8", "#C9A227", "#5B8C99", "#8C6D52"]
COR_REAL, COR_PREVISTO, COR_DESTAQUE = "#2E6F95", "#E07A3F", "#B5485E"


def engine():
    url = (f"mysql+pymysql://{os.environ.get('MYSQL_USER', 'analista')}:{os.environ.get('MYSQL_PASSWORD', 'analista123')}"
           f"@{os.environ.get('MYSQL_HOST', '127.0.0.1')}:{os.environ.get('MYSQL_PORT', '3336')}/tecidos?charset=utf8mb4")
    return create_engine(url, pool_pre_ping=True)


_ENG = None


def sql(consulta: str, **params) -> pd.DataFrame:
    global _ENG
    _ENG = _ENG or engine()
    with _ENG.connect() as con:
        return pd.read_sql(text(consulta), con, params=params)


def configurar_graficos():
    """Tema único. Gera PNG estático (aparece no GitHub); cai para HTML se o
    kaleido não encontrar um Chrome (rode `plotly_get_chrome` ou defina BROWSER_PATH)."""
    tpl = go.layout.Template(pio.templates["plotly_white"])
    tpl.layout.colorway = CORES
    tpl.layout.font = dict(family="Inter, Segoe UI, Helvetica, Arial", size=13, color="#2b2b2b")
    tpl.layout.title = dict(font=dict(size=17), x=0.01, xanchor="left")
    tpl.layout.margin = dict(l=60, r=30, t=70, b=50)
    tpl.layout.legend = dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0)
    tpl.layout.xaxis = dict(showgrid=False, linecolor="#999")
    tpl.layout.yaxis = dict(gridcolor="#e9e9e9", zeroline=False)
    pio.templates["tecidos"] = tpl
    pio.templates.default = "tecidos"
    try:
        go.Figure().to_image(format="png")
        pio.renderers.default = "png"
        pio.renderers["png"].width, pio.renderers["png"].height, pio.renderers["png"].scale = 1000, 480, 1.5
    except Exception:  # sem Chrome disponível
        pio.renderers.default = "notebook_connected"


def brl(v: float, casas: int = 0) -> str:
    s = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def verdade(arquivo: str) -> pd.DataFrame:
    """Arquivos de verdade do gerador (parâmetros reais do MMM, motor de cada pedido...)."""
    return pd.read_csv(VERDADE / arquivo)
