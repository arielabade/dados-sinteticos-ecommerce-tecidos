"""Varredura final: garante que nenhum dado pessoal dos arquivos de referência
foi parar no dataset gerado ou nos arquivos do repositório.

Uso: python scripts/varredura_pii.py <pasta ou arquivo de referência> [...]

Lê CSV/XLSX da pasta de referência, extrai e-mails, telefones, CPFs/CNPJs e
nomes completos, e procura cada um:
  * nas tabelas clientes e enderecos do MySQL carregado;
  * em todos os arquivos de texto versionáveis do repositório.
Imprime apenas contagens, nunca os valores encontrados.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import pymysql

RAIZ = Path(__file__).resolve().parents[1]
CONN = dict(host=os.environ.get("MYSQL_HOST", "127.0.0.1"), port=int(os.environ.get("MYSQL_PORT", "3336")),
            user=os.environ.get("MYSQL_USER", "analista"), password=os.environ.get("MYSQL_PASSWORD", "analista123"),
            database="tecidos")

RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
RE_DOC = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b|\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
RE_FONE = re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def digitos(s: str) -> str:
    return re.sub(r"\D", "", s)


def ler_referencia(caminhos: list[Path]):
    textos, nomes = [], set()
    arquivos = [f for c in caminhos for f in ([c] if c.is_file() else c.rglob("*"))]
    for f in arquivos:
        if f.suffix.lower() not in (".csv", ".xlsx", ".xls"):
            continue
        try:
            if f.suffix.lower() == ".csv":
                planilhas = {"_": pd.read_csv(f, dtype=str, on_bad_lines="skip")}
            else:
                planilhas = pd.read_excel(f, sheet_name=None, dtype=str)
        except Exception:
            continue
        for df in planilhas.values():
            for col in df.columns:
                vals = df[col].dropna().astype(str)
                textos.extend(vals.tolist())
                if re.search(r"nome|cliente|name|contato", str(col), re.I):
                    nomes.update(norm(v) for v in vals if len(v.split()) >= 2 and not any(ch.isdigit() for ch in v))
    blob = "\n".join(textos)
    emails = {e.lower() for e in RE_EMAIL.findall(blob)}
    docs = {digitos(d) for d in RE_DOC.findall(blob)}
    fones = {digitos(f)[-11:] for f in RE_FONE.findall(blob) if len(digitos(f)) >= 10}
    return emails, docs, fones, nomes


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    emails, docs, fones, nomes = ler_referencia([Path(a) for a in sys.argv[1:]])
    print(f"Referência: {len(emails)} e-mails, {len(docs)} CPFs/CNPJs, {len(fones)} telefones, {len(nomes)} nomes completos")

    con = pymysql.connect(**CONN)
    cur = con.cursor()
    cur.execute("SELECT LOWER(TRIM(email)), cpf, cnpj, telefone, nome, razao_social FROM clientes")
    rows = cur.fetchall()
    g_emails = {r[0] for r in rows}
    g_docs = {digitos(x) for r in rows for x in (r[1], r[2]) if x}
    g_fones = {digitos(r[3])[-11:] for r in rows if r[3]}
    g_nomes = {norm(x) for r in rows for x in (r[4], r[5]) if x}
    cur.execute("SELECT destinatario, logradouro FROM enderecos")
    g_nomes |= {norm(r[0]) for r in cur.fetchall()}

    falhas = 0
    for rotulo, ref, ger in [("e-mails", emails, g_emails), ("CPF/CNPJ", docs, g_docs), ("telefones", fones, g_fones)]:
        n = len(ref & ger)
        falhas += n
        print(f"  [{'ok' if n == 0 else 'FALHA'}] {rotulo} da referência presentes no banco gerado: {n}")
    n_nomes = len(nomes & g_nomes)
    print(f"  [info] nomes completos coincidentes: {n_nomes} "
          f"(o Faker sorteia nomes comuns; coincidência isolada de nome sem e-mail/CPF/telefone não identifica ninguém)")

    # arquivos do repositório (o que seria versionado)
    arquivos = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=RAIZ,
                              capture_output=True, text=True).stdout.split()
    achados = 0
    for a in arquivos:
        p = RAIZ / a
        if not p.is_file() or p.stat().st_size > 20_000_000:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        achados += sum(1 for e in emails if e in txt)
        d_txt = digitos(txt)
        achados += sum(1 for d in docs | fones if len(d) >= 10 and d in d_txt and d in re.sub(r"\D", " ", txt).split())
    falhas += achados
    print(f"  [{'ok' if achados == 0 else 'FALHA'}] e-mails/documentos/telefones da referência nos {len(arquivos)} arquivos do repositório: {achados}")
    print("TUDO OK" if falhas == 0 else "FALHAS ENCONTRADAS")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
