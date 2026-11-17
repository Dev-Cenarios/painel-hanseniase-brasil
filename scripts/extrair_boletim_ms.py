"""Lê as tabelas por UF do Boletim Epidemiológico de Hanseníase do MS (jan/2026) pra parquet.

É a régua do painel: Brasil, 5 regiões e 27 UFs, 2015–2024, nos indicadores
do apêndice. Sai em formato longo (uma linha por área × indicador × ano).

    python -m scripts.extrair_boletim_ms

Precisa do pypdf (está no ../sinan/.venv).
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "data" / "origem" / "boletins"
PDF = PASTA / "boletim-hanseniase-ms-jan-2026.pdf"
URL = ("https://www.gov.br/saude/pt-br/centrais-de-conteudo/publicacoes/boletins/epidemiologicos/"
       "especiais/2026/boletim-epidemiologico-de-hanseniase-numero-especial-jan-2026.pdf")
DESTINO = RAIZ / "data" / "origem" / "boletim_ms.parquet"
ANOS = tuple(range(2015, 2025))

# tabela do apêndice → (indicador do n, indicador do valor); None = a tabela não traz
TABELAS = {
    3: (None, "pct_contatos_deteccao"),
    8: ("casos_novos", "taxa_deteccao"),
    9: (None, "pct_gif_avaliado_diag"),
    10: (None, "pct_grau2_diag"),
    11: ("casos_mb", "pct_mb"),
    14: (None, "pct_cura_coorte"),
    15: (None, "pct_gif_avaliado_cura"),
    16: (None, "pct_contatos_examinados"),
    17: ("casos_0_14", "taxa_0_14"),
    18: (None, "pct_recidiva"),
}

UFS = {
    "RONDONIA": ("RO", 11), "ACRE": ("AC", 12), "AMAZONAS": ("AM", 13), "RORAIMA": ("RR", 14),
    "PARA": ("PA", 15), "AMAPA": ("AP", 16), "TOCANTINS": ("TO", 17), "MARANHAO": ("MA", 21),
    "PIAUI": ("PI", 22), "CEARA": ("CE", 23), "RIO GRANDE DO NORTE": ("RN", 24),
    "PARAIBA": ("PB", 25), "PERNAMBUCO": ("PE", 26), "ALAGOAS": ("AL", 27), "SERGIPE": ("SE", 28),
    "BAHIA": ("BA", 29), "MINAS GERAIS": ("MG", 31), "ESPIRITO SANTO": ("ES", 32),
    "RIO DE JANEIRO": ("RJ", 33), "SAO PAULO": ("SP", 35), "PARANA": ("PR", 41),
    "SANTA CATARINA": ("SC", 42), "RIO GRANDE DO SUL": ("RS", 43),
    "MATO GROSSO DO SUL": ("MS", 50), "MATO GROSSO": ("MT", 51), "GOIAS": ("GO", 52),
    "DISTRITO FEDERAL": ("DF", 53),
}
# código do IBGE da região (sigla bateria com SE de Sergipe)
REGIOES = {"REGIAO NORTE": "1", "REGIAO NORDESTE": "2", "REGIAO SUDESTE": "3",
           "REGIAO SUL": "4", "REGIAO CENTRO-OESTE": "5"}

_NUM = r"(?:-|\d{1,3}(?:\.\d{3})*(?:,\d+)?)"
_LINHA = re.compile(rf"^(?P<nome>\D+?)(?P<nums>(?:\s+{_NUM})+)\s*$")


def _chave(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento).strip().upper()


def _numero(token: str) -> float | None:
    return None if token == "-" else float(token.replace(".", "").replace(",", "."))


def _trecho(texto: str, numero: int) -> str:
    """Texto da tabela no apêndice (a lista de tabelas do começo repete o título)."""
    inicio = texto.rindex(f"TABELA {numero} ")
    fim = texto.find(f"TABELA {numero + 1} ", inicio)
    return texto[inicio:fim if fim > 0 else None]


def ler_tabela(texto: str, numero: int) -> pd.DataFrame:
    ind_n, ind_valor = TABELAS[numero]
    linhas = []
    for linha in _trecho(texto, numero).splitlines():
        achou = _LINHA.match(linha.strip())
        if not achou:
            continue
        chave = _chave(achou["nome"])
        if chave == "BRASIL":
            nivel, codigo = "BR", "BR"
        elif chave in REGIOES:
            nivel, codigo = "REGIAO", REGIOES[chave]
        elif chave in UFS:
            nivel, codigo = "UF", UFS[chave][0]
        else:
            continue
        nums = [_numero(t) for t in achou["nums"].split()]
        por_ano = 2 if ind_n else 1
        if len(nums) != por_ano * len(ANOS):
            raise SystemExit(f"Tabela {numero}, {achou['nome']}: {len(nums)} números — o PDF mudou?")
        for k, ano in enumerate(ANOS):
            base = {"tabela": numero, "nivel": nivel, "codigo": codigo,
                    "nome": achou["nome"].strip(), "ano": ano}
            if ind_n:
                linhas.append({**base, "indicador": ind_n, "valor": nums[2 * k]})
            linhas.append({**base, "indicador": ind_valor, "valor": nums[por_ano * k + por_ano - 1]})
    tabela = pd.DataFrame(linhas)
    areas = tabela.drop_duplicates("codigo")
    if len(areas) != 33:
        raise SystemExit(f"Tabela {numero}: achei {len(areas)} áreas, esperava 33 (BR + 5 + 27)")
    return tabela


def ler(caminho: Path) -> pd.DataFrame:
    import pypdf

    texto = "\n".join(pg.extract_text() or "" for pg in pypdf.PdfReader(caminho).pages)
    return pd.concat([ler_tabela(texto, n) for n in TABELAS], ignore_index=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--destino", type=Path, default=DESTINO)
    a = p.parse_args()

    PASTA.mkdir(parents=True, exist_ok=True)
    if not PDF.is_file():
        urllib.request.urlretrieve(URL, PDF)
    tabela = ler(PDF)
    tabela.to_parquet(a.destino, index=False)
    print(f"{len(tabela)} linhas, {tabela['indicador'].nunique()} indicadores em {a.destino}")


if __name__ == "__main__":
    sys.exit(main())
