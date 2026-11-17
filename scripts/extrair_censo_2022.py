"""População residente do Censo 2022 por município (SIDRA, tabela 4709) pra parquet.

O boletim do MS usa o Censo em 2022 no lugar da estimativa; só o total entra
(0–14 e pirâmide seguem o pop_ibge).

    python -m scripts.extrair_censo_2022
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "data" / "origem" / "censo_2022.parquet"
URL = "https://apisidra.ibge.gov.br/values/t/4709/n6/all/v/93/p/2022"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--destino", type=Path, default=DESTINO)
    a = p.parse_args()

    with urllib.request.urlopen(URL, timeout=120) as r:
        linhas = json.load(r)[1:]  # a primeira é o cabeçalho
    df = pd.DataFrame({"cod_mun6": [x["D1C"][:6] for x in linhas],
                       "populacao": [int(x["V"]) for x in linhas]})
    if len(df) < 5570 or df["cod_mun6"].duplicated().any():
        raise SystemExit(f"{len(df)} municípios — a tabela do SIDRA mudou?")
    a.destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(a.destino, index=False)
    print(f"{len(df)} municípios, {df['populacao'].sum()} habitantes em {a.destino}")


if __name__ == "__main__":
    main()
