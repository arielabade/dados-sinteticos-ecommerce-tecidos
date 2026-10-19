"""Simulação diária de pedidos, clientes e estoque."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .calendario import BLACK_FRIDAY
from .catalogo import TIPOS, Catalogo
from .clientes import REGIAO, FabricaClientes
from .config import CFG
from .demanda import PESO_NOVO, Demanda
from .midia import CANAIS_MMM

MOTORES = ["base"] + CANAIS_MMM

# Recompra: taxa diária enquanto "vivo", vida média (dias), mix de novos por motor
LAMBDA_TIPO = np.array([1 / 260, 1 / 85, 1 / 58, 1 / 50])
VIDA_TIPO = np.array([170, 260, 330, 360])
MIX_NOVOS = {
    "base": [0.50, 0.36, 0.10, 0.04],
    "meta_prospeccao": [0.60, 0.31, 0.07, 0.02],
    "meta_remarketing": [0.52, 0.34, 0.10, 0.04],
    "google_marca": [0.47, 0.37, 0.11, 0.05],
    "google_search": [0.44, 0.38, 0.12, 0.06],
    "google_shopping_pmax": [0.48, 0.36, 0.11, 0.05],
    "google_demand_gen": [0.60, 0.30, 0.08, 0.02],
}
LINHAS_EXTRA = np.array([0.6, 1.0, 1.3, 1.4])  # Poisson de itens adicionais por tipo
QTD_MEDIANA = np.array([1.5, 2.5, 3.0, 7.0])   # metros por linha
QTD_SIGMA = np.array([0.55, 0.6, 0.65, 0.6])
WHATSAPP_TIPO = np.array([0.02, 0.04, 0.08, 0.14])

# Hora do pedido (local): pico de manhã e à noite
HORA_P = np.array([0.6, 0.3, 0.15, 0.1, 0.1, 0.2, 0.6, 1.6, 3.2, 5.0, 6.0, 6.2, 5.0, 5.3, 5.8, 5.6,
                   5.4, 5.2, 5.4, 6.2, 7.2, 7.4, 5.6, 2.6])
HORA_P = HORA_P / HORA_P.sum()

CUPONS = [
    # codigo, descricao, tipo, valor, minimo, canal, de, ate, limite
    ("BEMVINDA10", "10% na primeira compra", "percentual", 10, None, "primeira_compra", "2022-01-01", None, None),
    ("FRETEGRATIS150", "Frete grátis acima de R$ 150", "frete_gratis", 0, 150, "geral", "2023-10-01", "2024-12-31", None),
    ("BLACK23", "Black Friday 2023 - 20% off", "percentual", 20, 99, "sazonal", "2023-11-20", "2023-11-28", None),
    ("BLACK24", "Black Friday 2024 - 25% off", "percentual", 25, 149, "sazonal", "2024-11-25", "2024-12-03", None),
    ("BLACK25", "Black Friday 2025 - 20% off", "percentual", 20, 129, "sazonal", "2025-11-24", "2025-12-02", None),
    ("CONSUMIDOR15", "Dia do Consumidor - 15% off", "percentual", 15, 120, "sazonal", "2024-03-13", None, None),
    ("COSTUREIRA20", "Dia da Costureira - 20% off", "percentual", 20, 150, "sazonal", "2024-05-22", None, None),
    ("ARRAIA10", "Festa junina - 10% em chitas", "percentual", 10, None, "sazonal", "2024-05-01", None, None),
    ("AGULHADEOURO15", "Parceria criadora de conteúdo (fictícia)", "percentual", 15, None, "influenciador", "2024-03-01", None, 4000),
    ("LINHAEPONTO10", "Parceria criadora de conteúdo (fictícia)", "percentual", 10, None, "influenciador", "2024-08-01", None, None),
    ("TESOURAMAGICA15", "Parceria criadora de conteúdo (fictícia)", "percentual", 15, 100, "influenciador", "2025-04-01", None, None),
    ("VOLTEI10", "Reativação por e-mail", "percentual", 10, 80, "email", "2023-10-01", None, None),
    ("CARRINHO5", "Recuperação de carrinho", "percentual", 5, None, "recuperacao_carrinho", "2023-10-01", None, None),
    ("WHATS5", "Desconto atendimento WhatsApp", "valor_fixo", 5, 60, "whatsapp", "2023-10-01", None, None),
    ("ATACADO8", "8% para pedidos acima de R$ 1.500", "percentual", 8, 1500, "geral", "2024-01-15", None, None),
]

TRANSP = {  # serviço: (transportadora, mult preço, prazo base por região)
    "PAC": ("Correios", 1.0, {"SE": 5, "S": 6, "CO": 7, "NE": 9, "N": 12}),
    "SEDEX": ("Correios", 1.85, {"SE": 2, "S": 3, "CO": 3, "NE": 4, "N": 6}),
    "Jadlog .Package": ("Jadlog", 0.95, {"SE": 4, "S": 5, "CO": 6, "NE": 8, "N": 11}),
    "Loggi Expresso": ("Loggi", 0.85, {"SE": 2, "S": 3, "CO": 3, "NE": 5, "N": 7}),
}
FRETE_BASE = {"SE": 15.9, "S": 18.9, "CO": 21.9, "NE": 25.9, "N": 30.9}
FRETE_KG = {"SE": 2.1, "S": 2.7, "CO": 3.4, "NE": 4.3, "N": 5.4}

COMENTARIOS = {
    5: [("Perfeito!", "Tecido lindo, exatamente como na foto. Já vou comprar outras cores."),
        ("Amei", "Caimento ótimo, chegou rápido e bem embalado."),
        ("Ótima qualidade", "Gramatura certinha, não desbota na lavagem."),
        (None, "Recomendo demais, cor fiel à foto."),
        ("Compro sempre", "Uso nas peças do ateliê, nunca decepciona.")],
    4: [("Muito bom", "Gostei bastante, só achei a cor um pouco mais escura."),
        ("Bom tecido", "Qualidade boa pelo preço. Entrega dentro do prazo."),
        (None, "Bom, mas amassa um pouco.")],
    3: [("Razoável", "O tecido é mais fino do que eu esperava."),
        (None, "Demorou para chegar, mas o tecido é ok.")],
    2: [("Não gostei", "A cor é bem diferente da foto."),
        ("Esperava mais", "Veio com uma pequena falha no meio do corte.")],
    1: [("Péssimo", "Metragem veio errada e o atendimento demorou a responder."),
        (None, "Tecido muito diferente do anunciado.")],
}


@dataclass
class ResultadoPedidos:
    clientes: pd.DataFrame
    enderecos: pd.DataFrame
    cupons: pd.DataFrame
    pedidos: pd.DataFrame
    itens: pd.DataFrame
    pagamentos: pd.DataFrame
    fretes: pd.DataFrame
    devolucoes: pd.DataFrame
    movimentacoes: pd.DataFrame
    avaliacoes: pd.DataFrame
    estoque: pd.DataFrame
    estoque_diario: pd.DataFrame
    perdas_ruptura: pd.DataFrame


def simular_pedidos(cal: pd.DataFrame, cat: Catalogo, dem: Demanda) -> ResultadoPedidos:
    rng = CFG.rng("pedidos")
    datas = CFG.datas
    nd = len(datas)
    V = cat.variantes
    nv = len(V)
    fab = FabricaClientes()

    # ---------------- matrizes de preferência por tipo de cliente
    preco_ef = np.where(np.isnan(cat.preco_promo), cat.preco_tabela, cat.preco_promo)
    fator_promo = (preco_ef / cat.preco_tabela) ** -2.2
    fator_tabela = (cat.preco_tabela / cat.preco_tabela[:, :1]) ** -1.0
    pop = V["_pop"].values
    afin = np.vstack(V["_afin"].values)  # nv x 4
    base_pref = (pop[:, None] * cat.sazonalidade * cat.ativo * fator_promo * fator_tabela).astype(np.float32)
    formato_rolo = (V["formato_venda"].values == "rolo")
    mpu = V["metros_por_unidade"].values.astype(float)
    produto_v = V["produto_id"].values
    var_do_produto: dict[int, np.ndarray] = {p: np.where(produto_v == p)[0] for p in np.unique(produto_v)}
    gram = V["gramatura_gm2"].values.astype(float)
    larg = V["produto_id"].map(cat.produtos.set_index("produto_id")["largura_cm"]).values / 100.0
    forn_v = V["_fornecedor_id"].values
    forn = cat.fornecedores.set_index("fornecedor_id")
    prazo_v = forn.loc[forn_v, "prazo_reposicao_dias"].values.astype(float)
    conf_v = forn.loc[forn_v, "confiabilidade"].values.astype(float)
    descont_v = V["_descont_idx"].fillna(10**9).values.astype(int)
    custo = cat.custo

    # ---------------- estoque inicial a partir da demanda esperada
    mix_ini = np.array([0.45, 0.33, 0.14, 0.08])
    linhas_dia = dem.diario["esperado"].values[:30].mean() * (1 + LINHAS_EXTRA) * mix_ini
    esperado = np.zeros(nv)
    for t in range(4):
        w = base_pref[:, 0] * afin[:, t]
        qtd = np.where(formato_rolo, 1.5, QTD_MEDIANA[t] * 1.15)
        esperado += linhas_dia[t] * w / w.sum() * qtd
    ewma = esperado.copy()
    estoque = np.where(cat.ativo[:, 0], np.ceil(esperado * rng.uniform(18, 45, nv)) + 5, 0.0)
    estoque = np.where(formato_rolo, np.ceil(estoque), np.round(estoque / 10) * 10 + 20)
    pipeline = np.zeros(nv)
    chegadas: dict[int, list[tuple[int, float]]] = {}

    est_ini = np.zeros((nv, nd), np.float32)
    entradas = np.zeros((nv, nd), np.float32)
    saidas = np.zeros((nv, nd), np.float32)
    perdida = np.zeros((nv, nd), np.float32)
    zerou = np.zeros((nv, nd), bool)
    movs: list[tuple] = []  # variante_idx, tipo, qtd, ts, pedido_id, fornecedor_id

    # ---------------- clientes (arrays com capacidade)
    cap = int(120000 * max(CFG.escala, 0.05)) + 20000
    c_tipo = np.zeros(cap, np.int8)
    c_lam = np.zeros(cap)
    c_fim = np.zeros(cap)
    c_ult = np.full(cap, -10**6, float)
    c_ped = np.zeros(cap, np.int32)
    n_cli = 0

    def novo_cliente(t: int, dia: int, ts, origem: str) -> int:
        nonlocal n_cli
        c = fab.novo(TIPOS[t], ts, origem)
        i = n_cli
        c_tipo[i] = t
        c_lam[i] = LAMBDA_TIPO[t] * rng.lognormal(0.05, 0.6)
        c_fim[i] = dia + rng.exponential(VIDA_TIPO[t])
        n_cli += 1
        assert c["cliente_id"] == n_cli
        return i

    # base legada: clientes importados da plataforma anterior
    n_leg = int(CFG.clientes_legado * CFG.escala)
    for _ in range(n_leg):
        t = int(rng.choice(4, p=[0.38, 0.36, 0.17, 0.09]))
        dias_atras = int(rng.integers(30, 720))
        ts = CFG.inicio - pd.Timedelta(days=dias_atras) + pd.Timedelta(minutes=int(rng.integers(0, 1440)))
        i = novo_cliente(t, -dias_atras, ts, "importacao_legado")
        c_ult[i] = -int(rng.integers(1, min(dias_atras, 200) + 1))
        c_fim[i] = c_ult[i] + rng.exponential(VIDA_TIPO[t]) + 30

    cupom_df = pd.DataFrame(CUPONS, columns=["codigo", "descricao", "tipo_desconto", "valor_desconto",
                                             "pedido_minimo", "canal", "valido_de", "valido_ate", "limite_usos"])
    cupom_df.insert(0, "cupom_id", np.arange(1, len(cupom_df) + 1))
    cup_id = dict(zip(cupom_df.codigo, cupom_df.cupom_id))
    cup_info = cupom_df.set_index("codigo")

    bf_janelas = [(pd.Timestamp(b) - pd.Timedelta(days=4), pd.Timestamp(b) + pd.Timedelta(days=4)) for b in BLACK_FRIDAY]

    ped_rows, item_rows = [], []
    perdas_dia = np.zeros(nd, np.int32)
    seas = (cal["dia_semana"] * cal["eventos"] * cal["salario"]).values
    inc_cols = [f"inc_{c}" for c in CANAIS_MMM]
    D = dem.diario
    pedido_id = 0
    item_id = 0

    for d in range(nd):
        data = datas[d]
        # chegadas de reposição
        for v, q in chegadas.pop(d, []):
            estoque[v] += q
            pipeline[v] -= q
            entradas[v, d] += q
            movs.append((v, "entrada_compra", q, data + pd.Timedelta(hours=float(rng.uniform(8, 11))), None, forn_v[v]))
        est_ini[:, d] = estoque
        # ajustes de inventário no dia 1 de cada mês
        if data.day == 1:
            sel = np.where((rng.random(nv) < 0.03) & (estoque > 20))[0]
            for v in sel:
                q = float(np.round(estoque[v] * rng.uniform(-0.05, 0.03), 0 if formato_rolo[v] else 1))
                if q != 0:
                    estoque[v] += q
                    movs.append((v, "ajuste_inventario", q, data + pd.Timedelta(hours=18), None, None))
            sel = np.where((rng.random(nv) < 0.006) & (estoque > 10) & ~formato_rolo)[0]
            for v in sel:
                q = -float(rng.integers(2, 8))
                estoque[v] += q
                movs.append((v, "perda_avaria", q, data + pd.Timedelta(hours=17), None, None))

        N = int(D["pedidos_alvo"].iloc[d])
        # ---- divide entre recompra e cliente novo
        n = n_cli
        gap = d - c_ult[:n]
        vivo = np.where(d <= c_fim[:n], 1.0, 0.04)
        h = c_lam[:n] * vivo * (1 - np.exp(-np.maximum(gap, 0) / 10.0))
        S = h.sum() * seas[d] ** 0.8
        rho = float(np.clip(S / max(N, 1), 0.30, 0.82))
        R = int(round(rho * N))
        R = min(R, int((h > 0).sum()))
        ret = rng.choice(n, size=R, replace=False, p=h / h.sum()) if R > 0 else np.array([], int)
        n_new = N - R

        inc = D.loc[data, inc_cols].values.astype(float)
        base = float(D["base"].iloc[d])
        w_all = np.concatenate([[base], inc])
        pn = np.array([PESO_NOVO[m] for m in MOTORES])
        w_new = w_all * pn
        w_ret = w_all * (1 - pn)
        mot_new = rng.choice(len(MOTORES), size=n_new, p=w_new / w_new.sum())
        mot_ret = rng.choice(len(MOTORES), size=R, p=w_ret / w_ret.sum())

        horas = rng.choice(24, size=N, p=HORA_P)
        ts_list = [data + pd.Timedelta(hours=int(hh), seconds=int(s))
                   for hh, s in zip(horas, rng.integers(0, 3600, N))]
        ordem = np.argsort(np.array(ts_list, dtype="datetime64[ns]"))

        clientes_dia, motores_dia, novos_dia = [], [], []
        for k in range(n_new):
            m = MOTORES[mot_new[k]]
            t = int(rng.choice(4, p=MIX_NOVOS[m]))
            clientes_dia.append((t, None))
            motores_dia.append(m)
            novos_dia.append(True)
        for k, i in enumerate(ret):
            clientes_dia.append((int(c_tipo[i]), int(i)))
            motores_dia.append(MOTORES[mot_ret[k]])
            novos_dia.append(False)

        # preferência do dia por tipo (cumulativa para amostragem rápida)
        prefs = [base_pref[:, d] * afin[:, t] for t in range(4)]
        prefs = [p / p.sum() for p in prefs]

        for oi in ordem:
            ts = ts_list[oi]
            t, ci = clientes_dia[oi]
            motor = motores_dia[oi]
            novo = novos_dia[oi]
            canal = "whatsapp" if rng.random() < WHATSAPP_TIPO[t] * (0.5 if novo else 1.2) else "site"
            # ---- itens
            n_lin = 1 + rng.poisson(LINHAS_EXTRA[t])
            vs = rng.choice(nv, size=n_lin, p=prefs[t])
            linhas = []
            usados = set()
            for v in vs:
                if v in usados:
                    continue
                if formato_rolo[v]:
                    q = float(1 + (rng.poisson(0.2) if t == 3 else 0))
                else:
                    q = float(np.clip(np.round(rng.lognormal(np.log(QTD_MEDIANA[t]), QTD_SIGMA[t]) * 2) / 2,
                                      0.5, 120))
                    if V["_chave"].iat[v] in ("linho_puro", "paete"):
                        q = max(0.5, np.round(q * 0.6 * 2) / 2)
                if estoque[v] < q:
                    perdida[v, d] += q
                    zerou[v, d] = True
                    # substituição por outra cor do mesmo artigo (35%)
                    alt = [a for a in var_do_produto[produto_v[v]]
                           if a != v and estoque[a] >= q and cat.ativo[a, d] and formato_rolo[a] == formato_rolo[v]]
                    if alt and rng.random() < 0.35:
                        v = int(rng.choice(alt))
                    else:
                        continue
                usados.add(v)
                linhas.append((v, q))
            if not linhas:
                perdas_dia[d] += 1
                continue

            # ---- cliente
            if ci is None:
                origem = "checkout" if canal == "site" else "whatsapp"
                if rng.random() < 0.12:
                    origem = "newsletter"
                cad = ts - pd.Timedelta(days=float(rng.exponential(20))) if origem == "newsletter" else \
                    ts - pd.Timedelta(minutes=float(rng.uniform(2, 12)))
                ci = novo_cliente(t, d, cad, origem)
            c_ult[ci] = d
            c_ped[ci] += 1
            cliente = fab.clientes[ci]

            pedido_id += 1
            subtotal_c = 0
            for v, q in linhas:
                pu = preco_ef[v, d]
                item_id += 1
                tot_c = int(round(q * pu * 100))
                subtotal_c += tot_c
                item_rows.append((item_id, pedido_id, v, q, round(pu, 2), round(cat.preco_tabela[v, d], 2),
                                  round(custo[v, d], 2), tot_c / 100))

            # ---- cupom
            cupom = _escolhe_cupom(rng, data, novo, motor, canal, cliente, subtotal_c / 100, bf_janelas)
            desc_c = 0
            frete_gratis_cupom = False
            if cupom:
                info = cup_info.loc[cupom]
                minimo = info.pedido_minimo
                if minimo is not None and not pd.isna(minimo) and subtotal_c / 100 < float(minimo):
                    cupom = None
                elif info.tipo_desconto == "percentual":
                    desc_c = int(round(subtotal_c * float(info.valor_desconto) / 100))
                elif info.tipo_desconto == "valor_fixo":
                    desc_c = min(int(float(info.valor_desconto) * 100), subtotal_c)
                else:
                    frete_gratis_cupom = True

            # ---- frete
            uf = cliente["_uf"]
            reg = REGIAO[uf]
            peso = sum(q * mpu[v] * (gram[v] if not np.isnan(gram[v]) else 150) / 1000 * larg[v] for v, q in linhas) + 0.15
            # política de frete grátis: limite sobe em mar/2025 (mudança de política documentada)
            limite = (149 if reg in ("SE", "S") else 249) if data < pd.Timestamp("2025-03-01") else \
                (199 if reg in ("SE", "S") else 299)
            retirada = (uf == "SP" and cliente["_cidade"] == "São Paulo" and rng.random() < 0.15) or \
                       (canal == "whatsapp" and uf == "SP" and rng.random() < 0.3)
            base_frete = (FRETE_BASE[reg] + FRETE_KG[reg] * max(peso - 0.3, 0)) * (1.03 ** (d / 365))
            if retirada:
                servico, transp, frete_c, prazo, custo_frete = "Retirada", "Retirada na loja", 0, 0, 0.0
                gratis = 1
            else:
                op = ["PAC", "SEDEX", "Jadlog .Package"] + (["Loggi Expresso"] if reg == "SE" else [])
                pp = np.array([0.52, 0.16, 0.22, 0.10][:len(op)])
                servico = str(rng.choice(op, p=pp / pp.sum()))
                transp, mult, prazos = TRANSP[servico]
                valor = base_frete * mult
                gratis = int(frete_gratis_cupom or ((subtotal_c - desc_c) / 100 >= limite and servico != "SEDEX"))
                frete_c = 0 if gratis else int(round(valor * 100))
                prazo = prazos[reg] + int(rng.integers(0, 3))
                custo_frete = round(valor * rng.uniform(0.82, 1.02), 2)
            total_c = subtotal_c - desc_c + frete_c
            pag = _sorteia_pagamento(rng, t, canal)
            if pag["pago"]:
                for v, q in linhas:
                    estoque[v] -= q
                    saidas[v, d] += q
                    movs.append((v, "saida_venda", -q, ts + pd.Timedelta(minutes=5), pedido_id, None))

            ped_rows.append({
                "pedido_id": pedido_id, "cliente_id": ci + 1,
                "endereco_entrega_id": None if retirada else cliente["_endereco_id"],
                "cupom_id": cup_id[cupom] if cupom else None, "canal_venda": canal,
                "criado_em": ts, "subtotal": subtotal_c / 100, "desconto": desc_c / 100,
                "frete": frete_c / 100, "total": total_c / 100,
                "_dia": d, "_motor": motor, "_novo": novo, "_tipo": t, "_uf": uf, "_regiao": reg,
                "_servico": servico, "_transp": transp, "_prazo": prazo, "_peso": round(peso, 3),
                "_custo_frete": custo_frete, "_gratis": gratis, "_n_itens": len(linhas), "_pago": pag,
            })

        # ---- reposição
        demanda_hoje = saidas[:, d] + perdida[:, d]
        ewma = 0.92 * ewma + 0.08 * demanda_hoje
        rop = ewma * (prazo_v * 0.7)
        precisa = (estoque + pipeline < rop) & cat.ativo[:, d] & (d < descont_v - 45)
        for v in np.where(precisa)[0]:
            if formato_rolo[v]:
                lote = float(max(2, np.ceil(ewma[v] * 20)))
            else:
                lote = float(max(50, np.ceil(ewma[v] * 20 / 50) * 50))
            atraso = 0.0
            if rng.random() > conf_v[v]:
                atraso = rng.uniform(8, 35)
            if forn_v[v] == 7 and data.month in (5, 6):  # fornecedor de chita sobrecarregado no São João
                atraso += rng.uniform(5, 20)
            chegada = d + int(prazo_v[v] * rng.uniform(0.8, 1.25) + atraso)
            pipeline[v] += lote
            chegadas.setdefault(chegada, []).append((v, lote))
        zerou[:, d] |= estoque < np.where(formato_rolo, 1, 0.5)

    # ------------------------------------------------------------------ DataFrames
    pedidos = pd.DataFrame(ped_rows)
    itens = pd.DataFrame(item_rows, columns=["item_pedido_id", "pedido_id", "_v", "quantidade", "preco_unitario",
                                             "preco_tabela", "custo_unitario", "total_item"])
    itens["variante_id"] = V["variante_id"].values[itens["_v"].values]

    clientes = pd.DataFrame(fab.clientes)
    clientes["_n_pedidos"] = c_ped[:n_cli]
    enderecos = pd.DataFrame(fab.enderecos)

    pagamentos, pedidos = _pagamentos_e_status(rng, pedidos)
    fretes = _fretes(rng, pedidos)
    devolucoes, pedidos, mov_dev = _devolucoes(rng, pedidos, itens)
    avaliacoes = _avaliacoes(rng, pedidos, itens, V, devolucoes, fretes)

    # movimentações
    mv = pd.DataFrame(movs, columns=["_v", "tipo", "quantidade", "ocorrido_em", "pedido_id", "fornecedor_id"])
    mv = pd.concat([mv, mov_dev], ignore_index=True)
    mv["variante_id"] = V["variante_id"].values[mv["_v"].values]
    mv = mv.sort_values("ocorrido_em", kind="stable").reset_index(drop=True)
    mv.insert(0, "movimentacao_id", np.arange(1, len(mv) + 1))
    mv["pedido_id"] = mv["pedido_id"].astype("Int64")
    mv["fornecedor_id"] = mv["fornecedor_id"].astype("Int64")
    mv["devolucao_id"] = mv["devolucao_id"].astype("Int64") if "devolucao_id" in mv else pd.NA

    # estoque diário (apenas dias em que a variante existe)
    vv, dd = np.where(cat.ativo | (est_ini > 0))
    est_final = est_ini + entradas - saidas
    ed = pd.DataFrame({
        "variante_id": V["variante_id"].values[vv], "data": datas[dd].date,
        "saldo_inicial": np.round(est_ini[vv, dd], 2), "entradas": np.round(entradas[vv, dd], 2),
        "saidas": np.round(saidas[vv, dd], 2), "saldo_final": np.round(est_final[vv, dd], 2),
        "em_ruptura": zerou[vv, dd].astype(int), "demanda_perdida": np.round(perdida[vv, dd], 2),
    })
    # ajustes e perdas do dia 1 entram no saldo (diferença absorvida no saldo_final do dia)
    estoque_atual = pd.DataFrame({
        "variante_id": V["variante_id"].values, "saldo_unidades": np.round(np.maximum(estoque, 0), 2),
        "ponto_reposicao": np.round(ewma * (prazo_v * 0.7), 2),
        "lote_reposicao": np.where(formato_rolo, np.maximum(2, np.ceil(ewma * 40)),
                                   np.maximum(50, np.ceil(ewma * 40 / 50) * 50)),
        "atualizado_em": CFG.fim + pd.Timedelta(hours=23, minutes=59),
    })
    perdas = pd.DataFrame({"data": datas, "pedidos_perdidos_ruptura": perdas_dia})
    return ResultadoPedidos(clientes, enderecos, cupom_df, pedidos, itens, pagamentos, fretes, devolucoes, mv,
                            avaliacoes, estoque_atual, ed, perdas)


# ---------------------------------------------------------------------------
def _escolhe_cupom(rng, data, novo, motor, canal, cliente, subtotal, bf_janelas):
    for a, b in bf_janelas:
        if a <= data <= b and rng.random() < 0.42:
            return {2023: "BLACK23", 2024: "BLACK24", 2025: "BLACK25"}[data.year]
    md = (data.month, data.day)
    if data >= pd.Timestamp("2024-03-13") and (3, 13) <= md <= (3, 16) and rng.random() < 0.3:
        return "CONSUMIDOR15"
    if data >= pd.Timestamp("2024-05-22") and (5, 22) <= md <= (5, 26) and rng.random() < 0.35:
        return "COSTUREIRA20"
    if data >= pd.Timestamp("2024-05-01") and data.month == 5 and rng.random() < 0.08:
        return "ARRAIA10"
    if canal == "whatsapp" and rng.random() < 0.22:
        return "WHATS5"
    if novo and canal == "site" and rng.random() < 0.28:
        return "BEMVINDA10"
    if motor == "meta_prospeccao" and rng.random() < 0.07:
        if data >= pd.Timestamp("2025-04-01"):
            return str(rng.choice(["AGULHADEOURO15", "LINHAEPONTO10", "TESOURAMAGICA15"]))
        if data >= pd.Timestamp("2024-08-01"):
            return str(rng.choice(["AGULHADEOURO15", "LINHAEPONTO10"]))
        if data >= pd.Timestamp("2024-03-01"):
            return "AGULHADEOURO15"
    if not novo and cliente["aceita_email_marketing"] and rng.random() < 0.05:
        return "VOLTEI10"
    if rng.random() < 0.03:
        return "CARRINHO5"
    if subtotal >= 1500 and data >= pd.Timestamp("2024-01-15") and rng.random() < 0.5:
        return "ATACADO8"
    if subtotal >= 150 and data <= pd.Timestamp("2024-12-31") and rng.random() < 0.03:
        return "FRETEGRATIS150"
    return None


def _sorteia_pagamento(rng, t: int, canal: str) -> dict:
    p = {0: [0.35, 0.63, 0.02], 1: [0.37, 0.60, 0.03], 2: [0.40, 0.55, 0.05], 3: [0.42, 0.40, 0.18]}[t]
    if canal == "whatsapp":
        p = [0.75, 0.20, 0.05]
    metodo = str(rng.choice(["pix", "cartao_credito", "boleto"], p=p))
    tent = []
    pago = True
    if metodo == "cartao_credito":
        if rng.random() < 0.085:
            tent.append("recusado")
            if rng.random() < 0.55:
                tent.append("aprovado")
            else:
                pago = False
        else:
            tent.append("aprovado")
    elif metodo == "pix":
        if rng.random() < 0.085:
            tent.append("expirado")
            pago = False
        else:
            tent.append("aprovado")
    else:
        if rng.random() < 0.27:
            tent.append("expirado")
            pago = False
        else:
            tent.append("aprovado")
    return {"metodo": metodo, "tentativas": tent, "pago": pago}


def _pagamentos_e_status(rng, pedidos: pd.DataFrame):
    fim = CFG.fim + pd.Timedelta(hours=23, minutes=59)
    pag_rows = []
    status, pago_em, cancelado_em = [], [], []
    pid_pag = 0
    bandeiras = ["Visa", "Mastercard", "Elo", "Hipercard", "American Express"]
    band_p = [0.42, 0.38, 0.12, 0.04, 0.04]
    for r in _it(pedidos):
        info = r.i_pago
        metodo = info["metodo"]
        ts = r.criado_em
        total = r.total
        if metodo == "cartao_credito":
            if total < 80:
                parc = 1
            else:
                pp = np.array([0.42, 0.07, 0.33, 0.03, 0.03, 0.05, 0.0, 0.0, 0.0, 0.04, 0.0, 0.03])
                if total > 600:
                    pp = np.array([0.22, 0.06, 0.30, 0.05, 0.06, 0.10, 0.02, 0.02, 0.02, 0.08, 0.02, 0.05])
                parc = int(rng.choice(np.arange(1, 13), p=pp / pp.sum()))
        else:
            parc = 1
        t_cur = ts + pd.Timedelta(seconds=int(rng.integers(20, 240)))
        p_em, c_em = None, None
        for k, st in enumerate(info["tentativas"]):
            pid_pag += 1
            if metodo == "boleto":
                atual = t_cur + pd.Timedelta(days=float(rng.uniform(0.5, 3)) if st == "aprovado" else 4)
            elif metodo == "pix":
                atual = t_cur + pd.Timedelta(minutes=float(rng.uniform(0.5, 25)) if st == "aprovado" else 30)
            else:
                atual = t_cur + pd.Timedelta(seconds=int(rng.integers(3, 30)))
            if atual > fim and st == "aprovado" and metodo != "cartao_credito":
                st_final, atual_v = "pendente", None
            else:
                st_final, atual_v = st, atual
            pag_rows.append({
                "pagamento_id": pid_pag, "pedido_id": r.pedido_id, "tentativa": k + 1, "metodo": metodo,
                "bandeira": (str(rng.choice(bandeiras, p=band_p)) if rng.random() > 0.06 else None)
                if metodo == "cartao_credito" else None,
                "parcelas": parc, "valor": total, "status": st_final,
                "gateway": "Pagar.me" if metodo != "boleto" or r.pedido_id % 3 else "Asaas",
                "transacao_gateway": f"tr_{rng.integers(10**15, 10**16 - 1):x}{pid_pag}",
                "criado_em": t_cur, "atualizado_em": atual_v,
            })
            if st_final == "aprovado":
                p_em = atual
            elif st_final in ("recusado",):
                t_cur = atual + pd.Timedelta(minutes=float(rng.uniform(1, 15)))
            elif st_final == "expirado":
                c_em = atual
            elif st_final == "pendente":
                pass
        if p_em is not None:
            status.append("pago")
        elif c_em is not None or (info["tentativas"][-1] == "recusado"):
            status.append("cancelado")
            c_em = c_em or t_cur
        else:
            status.append("aguardando_pagamento")
        pago_em.append(p_em)
        cancelado_em.append(c_em)
    pedidos = pedidos.copy()
    pedidos["status"] = status
    pedidos["pago_em"] = pago_em
    pedidos["cancelado_em"] = cancelado_em
    # estorno (chargeback/cancelamento após pagamento): 0,5% dos pagos com cartão
    pag = pd.DataFrame(pag_rows)
    aprov_cartao = pag[(pag.status == "aprovado") & (pag.metodo == "cartao_credito")].index
    estorn = rng.choice(aprov_cartao, size=int(len(aprov_cartao) * 0.005), replace=False)
    pag.loc[estorn, "status"] = "estornado"
    pag.loc[estorn, "atualizado_em"] = pag.loc[estorn, "atualizado_em"] + pd.to_timedelta(rng.uniform(1, 20, len(estorn)), unit="D")
    ped_estorn = pag.loc[estorn, "pedido_id"].values
    m = pedidos.pedido_id.isin(ped_estorn)
    pedidos.loc[m, "status"] = "cancelado"
    pedidos.loc[m, "cancelado_em"] = pag.loc[estorn].set_index("pedido_id").loc[pedidos.loc[m, "pedido_id"], "atualizado_em"].values
    return pag, pedidos


def _fretes(rng, pedidos):
    fim = CFG.fim + pd.Timedelta(hours=23, minutes=59)
    rows = []
    postado, entregue = [], []
    for r in _it(pedidos):
        p_em, e_em = None, None
        if r.status == "pago" and r.pago_em is not None and r.i_servico != "Retirada":
            p_em = _dia_util(r.pago_em + pd.Timedelta(days=float(rng.choice([0.6, 1, 1.5, 2, 3], p=[0.25, 0.35, 0.2, 0.15, 0.05]))))
            p_em = p_em.normalize() + pd.Timedelta(hours=float(rng.uniform(13, 18)))
            atraso = rng.choice([0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 4, 8])
            e_em = p_em + pd.Timedelta(days=float(r.i_prazo + atraso + rng.uniform(-1, 1)))
            e_em = e_em.normalize() + pd.Timedelta(hours=float(rng.uniform(9, 19)))
            if p_em > fim:
                p_em, e_em = None, None
            elif e_em > fim:
                e_em = None
        elif r.status == "pago" and r.i_servico == "Retirada":
            e_em = r.pago_em + pd.Timedelta(days=float(rng.uniform(1, 6)))
            e_em = e_em if e_em <= fim else None
        postado.append(p_em)
        entregue.append(e_em)
    pedidos["_postado"] = postado
    pedidos["_entregue"] = entregue
    st = pedidos["status"].values.copy()
    pagos = st == "pago"
    st[pagos & pedidos["_postado"].notna().values] = "enviado"
    st[pagos & pedidos["_entregue"].notna().values] = "entregue"
    pedidos["status"] = st
    # entrega sem baixa de rastreio (imperfeição): 2% dos entregues ficam sem entregue_em
    sem_baixa = (pedidos["status"] == "entregue") & (rng.random(len(pedidos)) < 0.02)
    fr = pd.DataFrame({
        "frete_id": np.arange(1, len(pedidos) + 1),
        "pedido_id": pedidos["pedido_id"].values,
        "transportadora": pedidos["_transp"].values,
        "servico": pedidos["_servico"].values,
        "peso_kg": pedidos["_peso"].values,
        "valor_cobrado": pedidos["frete"].values,
        "custo_real": pedidos["_custo_frete"].values,
        "frete_gratis": pedidos["_gratis"].values,
        "prazo_estimado_dias": pedidos["_prazo"].values,
        "postado_em": pedidos["_postado"].values,
        "entregue_em": pedidos["_entregue"].where(~sem_baixa, None).values,
        "codigo_rastreio": [
            (f"{'NX' if s != 'SEDEX' else 'OB'}{rng.integers(10**8, 10**9)}BR" if t == "Correios" else
             f"{rng.integers(10**13, 10**14)}"[:14]) if pd.notna(p) else None
            for s, t, p in zip(pedidos["_servico"], pedidos["_transp"], pedidos["_postado"])],
    })
    return fr


def _it(df):
    """itertuples que preserva colunas internas (prefixo _) como i_<nome>."""
    return df.rename(columns=lambda c: "i" + c if c.startswith("_") else c).itertuples(index=False)


def _dia_util(ts):
    while ts.dayofweek >= 5:
        ts = ts + pd.Timedelta(days=1)
    return ts


def _devolucoes(rng, pedidos, itens):
    fim = CFG.fim + pd.Timedelta(hours=23, minutes=59)
    ent = pedidos[(pedidos.status == "entregue") & pedidos["_entregue"].notna()]
    p_dev = np.where(ent["_tipo"].values == 0, 0.032, 0.022)
    sel = ent[rng.random(len(ent)) < p_dev]
    itens_por_pedido = itens.groupby("pedido_id")
    motivos = ["cor_diferente_da_foto", "defeito_no_tecido", "metragem_incorreta", "gramatura_diferente",
               "desistencia", "atraso_na_entrega"]
    mp = [0.33, 0.20, 0.12, 0.10, 0.17, 0.08]
    rows, movs = [], []
    devolvidos = []
    for k, r in enumerate(_it(sel), start=1):
        its = itens_por_pedido.get_group(r.pedido_id)
        it = its.iloc[int(rng.integers(0, len(its)))]
        sol = r.i_entregue + pd.Timedelta(days=float(rng.uniform(1, 9)))
        if sol > fim:
            continue
        st = str(rng.choice(["concluida", "recusada", "aprovada", "solicitada"], p=[0.84, 0.08, 0.05, 0.03]))
        concl = sol + pd.Timedelta(days=float(rng.uniform(5, 20))) if st in ("concluida", "recusada") else None
        if concl is not None and concl > fim:
            st, concl = "aprovada", None
        motivo = str(rng.choice(motivos, p=mp))
        did = len(rows) + 1
        valor = float(it.total_item) if st != "recusada" else 0.0
        rows.append({"devolucao_id": did, "pedido_id": r.pedido_id, "item_pedido_id": int(it.item_pedido_id),
                     "motivo": motivo, "quantidade": float(it.quantidade), "valor_reembolsado": round(valor, 2),
                     "status": st, "solicitada_em": sol, "concluida_em": concl})
        if st == "concluida":
            if motivo != "defeito_no_tecido":
                movs.append({"_v": int(it["_v"]), "tipo": "entrada_devolucao", "quantidade": float(it.quantidade),
                             "ocorrido_em": concl, "pedido_id": r.pedido_id, "fornecedor_id": None,
                             "devolucao_id": did})
            if len(its) == 1:
                devolvidos.append(r.pedido_id)
    dv = pd.DataFrame(rows)
    pedidos.loc[pedidos.pedido_id.isin(devolvidos), "status"] = "devolvido"
    mv = pd.DataFrame(movs, columns=["_v", "tipo", "quantidade", "ocorrido_em", "pedido_id", "fornecedor_id", "devolucao_id"])
    return dv, pedidos, mv


def _avaliacoes(rng, pedidos, itens, V, devolucoes, fretes):
    fim = CFG.fim + pd.Timedelta(hours=23, minutes=59)
    ent = pedidos[pedidos.status.isin(["entregue", "devolvido"]) & pedidos["_entregue"].notna()]
    sel = ent[rng.random(len(ent)) < 0.17]
    prim_item = itens.drop_duplicates("pedido_id").set_index("pedido_id")
    prod_v = V["produto_id"].values
    dev = set(devolucoes.pedido_id) if len(devolucoes) else set()
    rows = []
    for r in _it(sel):
        it = prim_item.loc[r.pedido_id]
        nota_p = np.array([0.02, 0.03, 0.07, 0.22, 0.66])
        atraso = (r.i_entregue - r.i_postado).days > r.i_prazo + 1 if r.i_postado is not None else False
        if r.pedido_id in dev:
            nota_p = np.array([0.35, 0.30, 0.20, 0.10, 0.05])
        elif atraso:
            nota_p = np.array([0.10, 0.12, 0.25, 0.28, 0.25])
        nota = int(rng.choice([1, 2, 3, 4, 5], p=nota_p))
        tit, com = COMENTARIOS[nota][int(rng.integers(0, len(COMENTARIOS[nota])))]
        if rng.random() < 0.35:
            com = None
        quando = r.i_entregue + pd.Timedelta(days=float(rng.exponential(6)) + 0.2)
        if quando > fim:
            continue
        rows.append({"avaliacao_id": len(rows) + 1, "pedido_id": r.pedido_id, "cliente_id": r.cliente_id,
                     "produto_id": int(prod_v[int(it["_v"])]), "nota": nota, "titulo": tit, "comentario": com,
                     "criada_em": quando})
    return pd.DataFrame(rows)
