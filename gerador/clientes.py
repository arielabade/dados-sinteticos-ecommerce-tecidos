"""Identidades 100% sintéticas para clientes e endereços.

* Nomes e logradouros vêm do Faker pt_BR com seed fixa.
* CPFs e CNPJs têm o formato oficial, mas o último dígito verificador é
  propositalmente inválido (ver doc_ficticio): não há como coincidir com um
  documento real.
* E-mails usam só domínios reservados pela RFC 2606/6761 (example.com,
  example.net, example.org, *.example, *.test), que não podem pertencer a
  ninguém.
* Telefones têm DDD coerente com a UF, mas número aleatório.
Nenhum dado de pessoa real é usado.
"""
from __future__ import annotations

import unicodedata

import numpy as np
import pandas as pd
from faker import Faker

from .config import CFG

# UF: (peso, [(cidade, peso)], faixa de CEP (5 dígitos), DDDs)
UFS = {
    "SP": (29.0, [("São Paulo", 45), ("Campinas", 6), ("Guarulhos", 4), ("Santo André", 3), ("Sorocaba", 3),
                  ("Ribeirão Preto", 3), ("São José dos Campos", 3), ("Americana", 2), ("Santos", 2), ("Jundiaí", 2),
                  ("Osasco", 3), ("Bauru", 2), ("Piracicaba", 2)], (1000, 19999), ["11", "19", "15", "16", "12", "13", "14"]),
    "RJ": (11.5, [("Rio de Janeiro", 60), ("Niterói", 8), ("Duque de Caxias", 6), ("Nova Iguaçu", 6), ("Petrópolis", 4),
                  ("Campos dos Goytacazes", 4), ("Volta Redonda", 3)], (20000, 28999), ["21", "22", "24"]),
    "MG": (10.0, [("Belo Horizonte", 35), ("Juiz de Fora", 8), ("Uberlândia", 8), ("Contagem", 6), ("Divinópolis", 4),
                  ("Montes Claros", 4), ("Ipatinga", 3)], (30000, 39999), ["31", "32", "34", "37", "38", "33"]),
    "PR": (6.5, [("Curitiba", 40), ("Londrina", 12), ("Maringá", 12), ("Cascavel", 6), ("Ponta Grossa", 6)], (80000, 87999), ["41", "43", "44", "45", "42"]),
    "SC": (5.0, [("Florianópolis", 20), ("Joinville", 18), ("Blumenau", 18), ("Brusque", 8), ("Chapecó", 8), ("Itajaí", 8)], (88000, 89999), ["47", "48", "49"]),
    "RS": (5.5, [("Porto Alegre", 40), ("Caxias do Sul", 15), ("Pelotas", 8), ("Canoas", 8), ("Santa Maria", 6)], (90000, 99999), ["51", "54", "53", "55"]),
    "BA": (5.0, [("Salvador", 50), ("Feira de Santana", 12), ("Vitória da Conquista", 8), ("Ilhéus", 4)], (40000, 48999), ["71", "75", "77", "73"]),
    "PE": (3.8, [("Recife", 45), ("Caruaru", 15), ("Olinda", 8), ("Jaboatão dos Guararapes", 10), ("Petrolina", 6)], (50000, 56999), ["81", "87"]),
    "DF": (3.0, [("Brasília", 100)], (70000, 72799), ["61"]),
    "GO": (3.0, [("Goiânia", 55), ("Anápolis", 12), ("Aparecida de Goiânia", 12), ("Jaraguá", 4)], (72800, 76799), ["62", "64"]),
    "CE": (3.0, [("Fortaleza", 65), ("Juazeiro do Norte", 10), ("Sobral", 6)], (60000, 63999), ["85", "88"]),
    "ES": (2.0, [("Vitória", 30), ("Vila Velha", 25), ("Serra", 15), ("Cariacica", 10)], (29000, 29999), ["27", "28"]),
    "PA": (1.6, [("Belém", 60), ("Ananindeua", 15), ("Santarém", 8)], (66000, 68899), ["91", "93", "94"]),
    "MT": (1.4, [("Cuiabá", 50), ("Várzea Grande", 15), ("Rondonópolis", 10)], (78000, 78899), ["65", "66"]),
    "MS": (1.3, [("Campo Grande", 60), ("Dourados", 15)], (79000, 79999), ["67"]),
    "PB": (1.2, [("João Pessoa", 55), ("Campina Grande", 25)], (58000, 58999), ["83"]),
    "RN": (1.1, [("Natal", 60), ("Mossoró", 15)], (59000, 59999), ["84"]),
    "AM": (1.0, [("Manaus", 100)], (69000, 69299), ["92"]),
    "MA": (1.0, [("São Luís", 60), ("Imperatriz", 15)], (65000, 65999), ["98", "99"]),
    "AL": (0.9, [("Maceió", 70), ("Arapiraca", 15)], (57000, 57999), ["82"]),
    "PI": (0.8, [("Teresina", 75)], (64000, 64999), ["86", "89"]),
    "SE": (0.7, [("Aracaju", 80)], (49000, 49999), ["79"]),
    "RO": (0.5, [("Porto Velho", 60), ("Ji-Paraná", 20)], (76800, 76999), ["69"]),
    "TO": (0.5, [("Palmas", 60), ("Araguaína", 20)], (77000, 77999), ["63"]),
    "AC": (0.25, [("Rio Branco", 100)], (69900, 69999), ["68"]),
    "AP": (0.25, [("Macapá", 100)], (68900, 68999), ["96"]),
    "RR": (0.2, [("Boa Vista", 100)], (69300, 69399), ["95"]),
}
UF_LISTA = list(UFS)
UF_PESO = np.array([UFS[u][0] for u in UF_LISTA]) / sum(UFS[u][0] for u in UF_LISTA)
REGIAO = {**{u: "SE" for u in ["SP", "RJ", "MG", "ES"]}, **{u: "S" for u in ["PR", "SC", "RS"]},
          **{u: "CO" for u in ["DF", "GO", "MT", "MS"]},
          **{u: "NE" for u in ["BA", "PE", "CE", "PB", "RN", "MA", "AL", "PI", "SE"]},
          **{u: "N" for u in ["PA", "AM", "RO", "TO", "AC", "AP", "RR"]}}

DOMINIOS = ["example.com", "example.net", "example.org", "correio.example", "email.test", "caixa.example"]
DOMINIOS_P = [0.30, 0.22, 0.14, 0.14, 0.10, 0.10]

TIPO_PJ = {"hobby": 0.0, "costureira": 0.06, "atelie": 0.45, "confeccao": 0.88}
TIPO_MULHER = {"hobby": 0.88, "costureira": 0.92, "atelie": 0.80, "confeccao": 0.62}

SUFIXOS_EMPRESA = {"atelie": ["Ateliê", "Atelier", "Costura Criativa", "Moda Autoral", "Ateliê de Costura"],
                   "confeccao": ["Confecções", "Moda", "Confecção", "Uniformes", "Malharia"],
                   "costureira": ["Costuras", "Ajustes e Reformas"]}


def doc_ficticio(doc: str) -> str:
    """CPF/CNPJ no formato oficial, mas com o último dígito verificador
    propositalmente errado: documentos reais sempre têm DV válido, então
    nenhum valor gerado pode coincidir com um CPF/CNPJ de verdade."""
    return doc[:-1] + str((int(doc[-1]) + 1) % 10)


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


class FabricaClientes:
    """Cria clientes sob demanda durante a simulação diária."""

    def __init__(self):
        self.rng = CFG.rng("clientes")
        self.fk = Faker("pt_BR")
        self.fk.seed_instance(CFG.seed + 1)
        self.clientes: list[dict] = []
        self.enderecos: list[dict] = []
        self._emails: set[str] = set()

    def _email(self, primeiro: str, ultimo: str, pj_nome: str | None) -> str:
        rng = self.rng
        for _ in range(20):
            if pj_nome:
                base = "".join(ch for ch in _ascii(pj_nome) if ch.isalnum())[:22]
                local = rng.choice(["contato", "vendas", "compras", base, "atendimento"]) if rng.random() < 0.6 else base
                dom = f"{base[:14]}.example" if rng.random() < 0.5 else str(rng.choice(DOMINIOS, p=DOMINIOS_P))
            else:
                p, u = _ascii(primeiro).replace(" ", ""), _ascii(ultimo).replace(" ", "")
                padrao = rng.integers(0, 6)
                local = [f"{p}.{u}", f"{p}{u}", f"{p}_{u}", f"{p}{rng.integers(1, 99)}",
                         f"{p}.{u}{rng.integers(70, 2005)}", f"{p[0]}{u}"][padrao]
                dom = str(rng.choice(DOMINIOS, p=DOMINIOS_P))
            email = f"{local}@{dom}"
            if email not in self._emails:
                self._emails.add(email)
                return email
            pj_nome = None if rng.random() < 0.5 else pj_nome
        email = f"cliente{len(self._emails)}@{rng.choice(DOMINIOS)}"
        self._emails.add(email)
        return email

    def _telefone(self, uf: str) -> str | None:
        rng = self.rng
        if rng.random() < 0.17:
            return None
        ddd = str(rng.choice(UFS[uf][3]))
        n = f"9{rng.integers(1000, 9999)}{rng.integers(1000, 9999)}"
        fmt = rng.choice(4, p=[0.55, 0.2, 0.15, 0.1])
        return [f"({ddd}) {n[:5]}-{n[5:]}", f"{ddd}{n}", f"+55 {ddd} {n[:5]}-{n[5:]}", f"({ddd}){n}"][fmt]

    def endereco(self, cliente_id: int, uf: str, nome: str, criado_em, principal: int, tipo="entrega",
                 cidade: str | None = None) -> dict:
        rng, fk = self.rng, self.fk
        cidades = UFS[uf][1]
        if cidade is None:
            p = np.array([c[1] for c in cidades], float)
            cidade = cidades[int(rng.choice(len(cidades), p=p / p.sum()))][0]
        lo, hi = UFS[uf][2]
        cep5 = int(rng.integers(lo, hi + 1))
        cep = f"{cep5:05d}-{rng.integers(0, 999):03d}"
        if rng.random() < 0.12:
            cep = cep.replace("-", "")
        cidade_txt = cidade
        if rng.random() < 0.04:  # grafia sem acento (imperfeição)
            cidade_txt = unicodedata.normalize("NFKD", cidade).encode("ascii", "ignore").decode()
        elif rng.random() < 0.02:
            cidade_txt = cidade.upper()
        e = {
            "endereco_id": len(self.enderecos) + 1,
            "cliente_id": cliente_id, "tipo": tipo, "destinatario": nome,
            "cep": cep, "logradouro": fk.street_name(), "numero": str(rng.integers(1, 3500)),
            "complemento": None if rng.random() < 0.55 else str(rng.choice(
                [f"Apto {rng.integers(11, 1504)}", f"Casa {rng.integers(1, 9)}", f"Bloco {rng.choice(list('ABCD'))}",
                 "Fundos", f"Sala {rng.integers(1, 40)}", "Galpão 2", "Loja 1"])),
            "bairro": fk.bairro(), "cidade": cidade_txt, "uf": uf,
            "principal": principal, "criado_em": criado_em,
        }
        self.enderecos.append(e)
        return e

    def novo(self, tipo: str, cadastrado_em: pd.Timestamp, origem: str) -> dict:
        rng, fk = self.rng, self.fk
        cid = len(self.clientes) + 1
        mulher = rng.random() < TIPO_MULHER[tipo]
        primeiro = fk.first_name_female() if mulher else fk.first_name_male()
        ultimo = fk.last_name()
        nome = f"{primeiro} {ultimo}" + (f" {fk.last_name()}" if rng.random() < 0.35 else "")
        pj = rng.random() < TIPO_PJ[tipo]
        razao = None
        if pj:
            suf = str(rng.choice(SUFIXOS_EMPRESA.get(tipo, ["Costuras"])))
            fantasia = f"{suf} {primeiro}" if rng.random() < 0.5 else f"{ultimo} {suf}"
            razao = f"{fantasia} {rng.choice(['Ltda', 'ME', 'EIRELI', 'MEI'])}"
        uf = str(rng.choice(UF_LISTA, p=UF_PESO))
        nasc = None
        if rng.random() > 0.45:
            idade = int(np.clip(rng.normal(44 if tipo != "hobby" else 41, 12), 18, 82))
            nasc = (cadastrado_em - pd.Timedelta(days=idade * 365 + int(rng.integers(0, 365)))).date()
        email = self._email(primeiro, ultimo, razao)
        if rng.random() < 0.015:  # e-mail digitado com maiúsculas/espaço (imperfeição)
            email = (" " + email.capitalize()) if rng.random() < 0.3 else email.upper()
        c = {
            "cliente_id": cid, "tipo_cliente": tipo, "tipo_pessoa": "PJ" if pj else "PF",
            "nome": nome, "razao_social": razao, "email": email,
            "telefone": self._telefone(uf),
            "cpf": None if pj or rng.random() < 0.08 else doc_ficticio(fk.cpf()),
            "cnpj": doc_ficticio(fk.cnpj()) if pj else None,
            "data_nascimento": nasc,
            "genero": None if rng.random() < 0.6 else ("F" if mulher else ("M" if rng.random() < 0.97 else "O")),
            "cadastrado_em": cadastrado_em, "origem_cadastro": origem,
            "aceita_email_marketing": int(rng.random() < 0.58),
            "aceita_whatsapp": int(rng.random() < 0.41),
            "_uf": uf,
        }
        self.clientes.append(c)
        end = self.endereco(cid, uf, nome if not pj else razao, cadastrado_em, 1)
        c["_endereco_id"] = end["endereco_id"]
        c["_cidade"] = end["cidade"]
        # 9% têm um segundo endereço (cobrança ou outra entrega)
        if rng.random() < 0.09:
            self.endereco(cid, uf, nome, cadastrado_em, 0, tipo=str(rng.choice(["cobranca", "entrega"])))
        return c
