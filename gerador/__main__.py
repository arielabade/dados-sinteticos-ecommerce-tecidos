"""Gera todos os CSVs do dataset.

Uso:
    python -m gerador                 # escala 1.0 (~150 mil pedidos)
    ESCALA=0.05 python -m gerador     # amostra rápida para desenvolvimento
"""
from __future__ import annotations

import json
import shutil
import time

import numpy as np
import pandas as pd

from .atribuicao import gerar_atribuicao, metricas_reportadas
from .calendario import calendario
from .catalogo import gerar_catalogo
from .config import CFG
from .demanda import gerar_demanda
from .exportar import Escritor
from .midia import META_CAMPANHAS, GOOGLE_CAMPANHAS, gerar_midia
from .pedidos import simular_pedidos
from .tracking import gerar_tracking


def _int(df, *cols):
    for c in cols:
        df[c] = pd.array(pd.to_numeric(df[c], errors="coerce").round(), dtype="Int64")
    return df


def main():
    t0 = time.time()
    print(f"Gerando dataset (escala={CFG.escala}, seed={CFG.seed}) em {CFG.saida}")
    if CFG.saida.exists():
        shutil.rmtree(CFG.saida)
    CFG.verdade.mkdir(parents=True, exist_ok=True)
    esc = Escritor()

    cal = calendario()
    cat = gerar_catalogo()
    midia = gerar_midia()
    dem = gerar_demanda(cal, midia)
    print(f"[{time.time() - t0:5.0f}s] catálogo, mídia e demanda prontos")

    ped = simular_pedidos(cal, cat, dem)
    P = ped.pedidos
    P["numero_pedido"] = (10000 + P.pedido_id).astype(str)
    print(f"[{time.time() - t0:5.0f}s] {len(P)} pedidos, {len(ped.clientes)} clientes")

    rng = CFG.rng("imperfeicoes")

    # --- imperfeição: mesma pessoa com duas contas (e-mails diferentes, mesmo nome/CPF)
    C = ped.clientes
    pf = C[(C.tipo_pessoa == "PF") & C.cpf.notna()]
    n_dup = int(len(C) * 0.006)
    novos = pf[pf.cliente_id > len(C) * 0.4].sample(n_dup, random_state=int(rng.integers(0, 2**31)))
    antigos = pf[pf.cliente_id < len(C) * 0.4].sample(n_dup, random_state=int(rng.integers(0, 2**31)))
    for col in ["nome", "cpf", "data_nascimento", "genero"]:
        C.loc[novos.index, col] = antigos[col].values
    C.loc[novos.index, "telefone"] = np.where(rng.random(n_dup) < 0.6, antigos["telefone"].values,
                                              C.loc[novos.index, "telefone"].values)

    # --- imperfeição: pedidos de teste da equipe
    teste_id = len(C) + 1
    C.loc[len(C)] = {**{c: None for c in C.columns}, "cliente_id": teste_id, "tipo_cliente": "hobby",
                     "tipo_pessoa": "PF", "nome": "Equipe Tecelã (teste)", "email": "teste.checkout@tecelatecidos.example",
                     "cadastrado_em": pd.Timestamp("2023-09-20 10:00"), "origem_cadastro": "checkout",
                     "aceita_email_marketing": 0, "aceita_whatsapp": 0, "_uf": "SP", "_n_pedidos": 0}
    datas_teste = pd.to_datetime(["2023-10-03 15:12", "2024-02-28 18:40", "2024-03-01 09:05", "2024-03-01 09:31",
                                  "2024-06-16 10:02", "2024-11-21 16:45", "2025-03-03 11:20", "2025-07-14 14:10",
                                  "2025-07-17 10:55", "2025-11-25 17:30", "2026-02-02 09:48", "2026-02-02 10:15"])
    v_teste = int(cat.variantes.variante_id.iloc[0])
    pid0 = int(P.pedido_id.max())
    item0 = int(ped.itens.item_pedido_id.max())
    pag0 = int(ped.pagamentos.pagamento_id.max())
    fr0 = int(ped.fretes.frete_id.max())
    novos_p, novos_i, novos_pag, novos_fr = [], [], [], []
    for k, ts in enumerate(datas_teste, start=1):
        pid = pid0 + k
        pago = k % 3 == 0
        sub = float(cat.preco_tabela[0, min((ts - CFG.inicio).days, len(CFG.datas) - 1)])
        novos_p.append({"pedido_id": pid, "numero_pedido": str(10000 + pid), "cliente_id": teste_id,
                        "endereco_entrega_id": None, "cupom_id": None, "canal_venda": "site",
                        "status": "pago" if pago else "cancelado", "criado_em": ts,
                        "pago_em": ts + pd.Timedelta(minutes=2) if pago else None,
                        "cancelado_em": None if pago else ts + pd.Timedelta(minutes=30),
                        "subtotal": round(sub * 0.5, 2), "desconto": round(sub * 0.5 - 1, 2), "frete": 0.0, "total": 1.0,
                        "pedido_teste": 1, "_dia": (ts - CFG.inicio).days, "_motor": "teste", "_novo": False,
                        "_tipo": 0, "_uf": "SP", "_regiao": "SE", "_servico": "Retirada", "_transp": "Retirada na loja",
                        "_prazo": 0, "_peso": 0.1, "_custo_frete": 0.0, "_gratis": 1, "_n_itens": 1, "_pago": None})
        novos_i.append({"item_pedido_id": item0 + k, "pedido_id": pid, "_v": 0, "variante_id": v_teste, "quantidade": 0.5,
                        "preco_unitario": round(sub, 2), "preco_tabela": round(sub, 2),
                        "custo_unitario": round(float(cat.custo[0, 0]), 2), "total_item": round(sub * 0.5, 2)})
        novos_pag.append({"pagamento_id": pag0 + k, "pedido_id": pid, "tentativa": 1, "metodo": "pix", "bandeira": None,
                          "parcelas": 1, "valor": 1.0, "status": "aprovado" if pago else "expirado", "gateway": "Pagar.me",
                          "transacao_gateway": f"tr_teste_{k:04d}", "criado_em": ts + pd.Timedelta(seconds=40),
                          "atualizado_em": ts + pd.Timedelta(minutes=2 if pago else 30)})
        novos_fr.append({"frete_id": fr0 + k, "pedido_id": pid, "transportadora": "Retirada na loja", "servico": "Retirada",
                         "peso_kg": 0.1, "valor_cobrado": 0.0, "custo_real": 0.0, "frete_gratis": 1,
                         "prazo_estimado_dias": 0, "postado_em": None, "entregue_em": None, "codigo_rastreio": None})
    P["pedido_teste"] = 0
    P = pd.concat([P, pd.DataFrame(novos_p)], ignore_index=True)
    ped.pedidos = P
    ped.itens = pd.concat([ped.itens, pd.DataFrame(novos_i)], ignore_index=True)
    ped.pagamentos = pd.concat([ped.pagamentos, pd.DataFrame(novos_pag)], ignore_index=True)
    ped.fretes = pd.concat([ped.fretes, pd.DataFrame(novos_fr)], ignore_index=True)
    ped.clientes = C

    # --- tracking (grava sessões, eventos, cliques e envios mês a mês)
    print(f"[{time.time() - t0:5.0f}s] gerando tracking...")
    Pt = P[P.pedido_teste == 0]
    ped_trk = type(ped)(**{**ped.__dict__, "pedidos": Pt})
    trk = gerar_tracking(cat, midia, ped_trk, cal, esc)
    P["sessao_id"] = pd.array(P.pedido_id.map(trk.pedido_sessao), dtype="Int64")
    print(f"[{time.time() - t0:5.0f}s] tracking: {trk.resumo['sessoes']} sessões, {trk.resumo['eventos']} eventos")

    A = gerar_atribuicao(trk, Pt)
    meta_m, google_m, kw_m = metricas_reportadas(trk, Pt, midia)
    print(f"[{time.time() - t0:5.0f}s] atribuição e métricas de plataforma prontas")

    # --- imperfeição: gramatura não cadastrada
    V = cat.variantes.copy()
    V["gramatura_gm2"] = pd.array(V.gramatura_gm2, dtype="Int64")
    V.loc[rng.random(len(V)) < 0.04, "gramatura_gm2"] = pd.NA

    # ------------------------------------------------------------ gravação
    esc.gravar("categorias", cat.categorias)
    esc.gravar("fornecedores", cat.fornecedores)
    esc.gravar("produtos", cat.produtos)
    esc.gravar("variantes", V, ["variante_id", "produto_id", "sku", "cor", "estampa", "gramatura_gm2", "formato_venda",
                                "metros_por_unidade", "preco_atual", "custo_atual", "ativo", "criado_em"])
    esc.gravar("historico_precos", cat.historico)
    esc.gravar("estoque", ped.estoque)
    esc.gravar("estoque_diario", ped.estoque_diario)
    esc.gravar("clientes", C)
    esc.gravar("enderecos", ped.enderecos)
    esc.gravar("cupons", _int(ped.cupons, "limite_usos"))
    esc.gravar("meta_contas", midia.meta_contas)
    esc.gravar("meta_campanhas", midia.meta_campanhas)
    esc.gravar("meta_conjuntos", midia.meta_conjuntos)
    esc.gravar("meta_anuncios", midia.meta_anuncios)
    esc.gravar("meta_metricas_diarias", meta_m)
    esc.gravar("google_contas", midia.google_contas)
    esc.gravar("google_campanhas", midia.google_campanhas)
    esc.gravar("google_grupos_anuncio", midia.google_grupos)
    esc.gravar("google_palavras_chave", _int(midia.google_palavras, "indice_qualidade"))
    esc.gravar("google_metricas_diarias", google_m)
    esc.gravar("google_palavras_chave_metricas_diarias", kw_m)
    P = _int(P, "endereco_entrega_id", "cupom_id")
    esc.gravar("pedidos", P, ["pedido_id", "numero_pedido", "cliente_id", "endereco_entrega_id", "sessao_id", "cupom_id",
                              "canal_venda", "status", "criado_em", "pago_em", "cancelado_em", "subtotal", "desconto",
                              "frete", "total", "pedido_teste"])
    esc.gravar("itens_pedido", ped.itens, ["item_pedido_id", "pedido_id", "variante_id", "quantidade", "preco_unitario",
                                           "preco_tabela", "custo_unitario", "total_item"])
    esc.gravar("pagamentos", ped.pagamentos)
    esc.gravar("fretes", ped.fretes)
    esc.gravar("devolucoes", ped.devolucoes)
    esc.gravar("movimentacoes_estoque", ped.movimentacoes, ["movimentacao_id", "variante_id", "tipo", "quantidade",
                                                            "ocorrido_em", "pedido_id", "devolucao_id", "fornecedor_id"])
    esc.gravar("avaliacoes", ped.avaliacoes)
    esc.gravar("atribuicoes", A)

    # ------------------------------------------------------------ verdade (fora do MySQL)
    vd = CFG.verdade
    dem.diario.rename_axis("data").to_csv(vd / "demanda_diaria.csv")
    dem.params.to_csv(vd / "parametros_mmm.csv", index=False)
    pd.concat([midia.investimento_canal.add_prefix("inv_"), midia.investimento_efetivo.add_prefix("inv_efetivo_")],
              axis=1).rename_axis("data").to_csv(vd / "investimento_canal_diario.csv")
    ped.perdas_ruptura.to_csv(vd / "pedidos_perdidos_ruptura.csv", index=False)
    Pt[["pedido_id", "_motor", "_novo"]].rename(columns={"_motor": "motor_verdadeiro", "_novo": "cliente_novo"}) \
        .to_csv(vd / "pedidos_motor.csv", index=False)
    pd.DataFrame([{"plataforma": "meta", "campanha": c[0], "eficiencia": c[7]} for c in META_CAMPANHAS] +
                 [{"plataforma": "google", "campanha": c[0], "eficiencia": c[9]} for c in GOOGLE_CAMPANHAS]) \
        .to_csv(vd / "eficiencia_campanhas.csv", index=False)
    (vd / "resumo.json").write_text(json.dumps({"escala": CFG.escala, "seed": CFG.seed, "linhas": esc.linhas},
                                               indent=2, ensure_ascii=False))

    pagos = P[P.status.isin(["pago", "enviado", "entregue", "devolvido"]) & (P.pedido_teste == 0)]
    inv = midia.investimento_canal.values.sum()
    print("\nResumo")
    for t, n in sorted(esc.linhas.items(), key=lambda x: -x[1]):
        print(f"  {t:<42} {n:>12,}")
    print(f"  receita paga: R$ {pagos.total.sum():,.0f} | ticket médio: R$ {pagos.total.mean():,.2f}")
    print(f"  investimento: R$ {inv:,.0f} | MER: {pagos.total.sum() / inv:.2f}")
    print(f"  conversão (pedidos/sessões): {len(P) / trk.resumo['sessoes']:.2%}")
    print(f"Concluído em {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
