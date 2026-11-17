"""Contatos registrados e examinados do Brasil (public.sinan_hans) pra parquet.

A silver não tem contatos registrados, que é o denominador do indicador; o
SINAN bruto tem. Sai já somado por município, ano de diagnóstico e o que a
coorte precisa (classificação, modo de entrada, tipo de alta).

    python -m scripts.extrair_contatos_br
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src import banco  # noqa: E402

DESTINO = RAIZ / "data" / "origem" / "sinan_br_contatos.parquet"

# contreg/contexam são texto; o que não for número vira nulo
SQL = r"""
    SELECT id_mn_resi AS cod_mun6,
           left(dt_diag, 4)::int AS ano_diagnostico,
           classopera, modoentr, tpalta_n,
           count(*) AS casos,
           sum(CASE WHEN contreg ~ '^\d+$' THEN contreg::int END) AS contatos_registrados,
           sum(CASE WHEN contexam ~ '^\d+$' THEN contexam::int END) AS contatos_examinados
    FROM public.sinan_hans
    WHERE dt_diag ~ '^\d{4}-'
    GROUP BY 1, 2, 3, 4, 5
"""


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--destino", type=Path, default=DESTINO)
    a = p.parse_args()

    if not banco.configurado():
        raise SystemExit("Credenciais ausentes: copie .env.exemplo pra .env e preencha.")

    df = banco.consultar(SQL)
    a.destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(a.destino, index=False, compression="zstd")
    print(f"{len(df)} linhas ({df['casos'].sum()} notificações) em {a.destino}")


if __name__ == "__main__":
    main()
