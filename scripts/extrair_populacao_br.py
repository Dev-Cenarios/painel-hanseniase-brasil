"""População por município, ano, sexo e faixa de 5 anos (public.pop_ibge) pra parquet.

Faixa 0 = 0–4 … 16 = 80+ (o pop_ibge já para em 80). 0–14 = faixas 0 a 2.
UF e Brasil saem da soma.

    python -m scripts.extrair_populacao_br
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src import banco  # noqa: E402

DESTINO = RAIZ / "data" / "origem" / "populacao_ibge_br.parquet"

SQL = """
    SELECT left(cod_mun, 6) AS cod_mun6,
           ano::int AS ano,
           CASE sexo WHEN '1' THEN 'M' WHEN '2' THEN 'F' END AS sexo,
           least(idade::int / 5, 16) AS faixa,
           sum(populacao)::bigint AS populacao
    FROM public.pop_ibge
    GROUP BY 1, 2, 3, 4
"""


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--destino", type=Path, default=DESTINO)
    a = p.parse_args()

    if not banco.configurado():
        raise SystemExit("Credenciais ausentes: copie .env.exemplo pra .env e preencha.")

    df = banco.consultar(SQL)
    if df["sexo"].isna().any():
        raise SystemExit("sexo fora de 1/2 no pop_ibge — rever o CASE")
    df["faixa"] = df["faixa"].astype("int8")
    a.destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(a.destino, index=False, compression="zstd")
    print(f"{len(df)} linhas em {a.destino}")
    print(df.groupby("ano")["populacao"].sum().to_string())


if __name__ == "__main__":
    main()
