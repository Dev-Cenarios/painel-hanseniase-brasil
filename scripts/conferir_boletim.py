"""Confere a silver contra o boletim do MS, por Brasil e UF, 2015–2024.

Conta do jeito do boletim: caso novo por ano de diagnóstico, sem erro
diagnóstico; coortes com PB de A−1 e MB de A−2, tirando só quem foi
transferido pra outro estado ou país (tirar toda transferência põe a cura
~5 pp acima do MS), e cura só com alta até 31/12 do ano de avaliação.
Imprime silver, MS e a diferença.

    python -m scripts.conferir_boletim [--ano 2024]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = RAIZ / "data" / "origem"

from scripts.extrair_boletim_ms import UFS  # noqa: E402

SIGLA = {cod: sigla for sigla, cod in UFS.values()}
GIF_AVALIADO = ("Grau zero", "Grau I", "Grau II")
SAI_DA_COORTE = ("Transferência p/ outro estado", "Transferência p/ outro país")


def _uf(cod_mun6: pd.Series) -> pd.Series:
    return pd.to_numeric(cod_mun6.astype(str).str[:2], errors="coerce").map(SIGLA)


def _por_area(df: pd.DataFrame, colunas: dict) -> pd.DataFrame:
    """Soma por (uf, ano) e acrescenta o Brasil."""
    uf = df.groupby(["uf", "ano"]).agg(**colunas).reset_index()
    br = df.groupby("ano").agg(**colunas).reset_index().assign(uf="BR")
    return pd.concat([uf, br], ignore_index=True).rename(columns={"uf": "codigo"})


def _coorte(df: pd.DataFrame, mb: pd.Series, ano_diag: pd.Series) -> pd.DataFrame:
    """Uma linha por caso e ano de avaliação em que ele entra na coorte."""
    return df.assign(ano=ano_diag + mb.map({True: 2, False: 1}))


def silver() -> pd.DataFrame:
    s = pd.read_parquet(ORIGEM / "sinan_br_hans.parquet")
    s = s[(s["modo_entrada"] == "Caso novo") & (s["tipo_alta"] != "Erro diagnóstico")].copy()
    s["ano"] = pd.to_datetime(s["data_diagnostico"], errors="coerce").dt.year
    s["uf"] = _uf(s["municipio_residencia_id"])
    idade = s["idade_notificada"].fillna("")
    s["menor15"] = ~idade.str.contains("ano") | (pd.to_numeric(idade.str[:3], errors="coerce") < 15)
    s["mb"] = s["classificacao_operacional"].fillna("").str.startswith("MB")
    s["avaliado"] = s["avaliacao_incapacidade_diagnostico"].isin(GIF_AVALIADO)
    s["grau2"] = s["avaliacao_incapacidade_diagnostico"] == "Grau II"
    s["cura"] = s["tipo_alta"] == "Cura"
    s["abandono"] = s["tipo_alta"] == "Abandono"
    s["cura_avaliada"] = s["cura"] & s["avaliacao_incapacidade_atual"].isin(GIF_AVALIADO)

    diag = _por_area(s, {"casos_novos": ("mb", "size"), "casos_0_14": ("menor15", "sum"),
                         "mb": ("mb", "sum"), "avaliados": ("avaliado", "sum"), "grau2": ("grau2", "sum")})
    sem_transf = s[~s["tipo_alta"].isin(SAI_DA_COORTE)]
    coorte = _coorte(sem_transf, sem_transf["mb"], sem_transf["ano"])
    # cura só conta se saiu até 31/12 do ano de avaliação
    ano_alta = pd.to_datetime(coorte["data_alta"], errors="coerce").dt.year
    coorte["cura"] = coorte["cura"] & (ano_alta <= coorte["ano"])
    coorte["cura_avaliada"] = coorte["cura_avaliada"] & coorte["cura"]
    coorte = _por_area(coorte,
                       {"coorte": ("cura", "size"), "curas": ("cura", "sum"),
                        "abandonos": ("abandono", "sum"), "curas_avaliadas": ("cura_avaliada", "sum")})
    return diag.merge(coorte, on=["codigo", "ano"], how="outer")


def contatos() -> pd.DataFrame:
    c = pd.read_parquet(ORIGEM / "sinan_br_contatos.parquet")
    alta = c["tpalta_n"].astype(str)
    c = c[(c["modoentr"].astype(str) == "1") & (alta != "8") & ~alta.isin(["4", "5"])].copy()
    c["uf"] = _uf(c["cod_mun6"])
    mb = c["classopera"].astype(str) == "2"
    c = _coorte(c, mb, c["ano_diagnostico"])
    return _por_area(c, {"registrados": ("contatos_registrados", "sum"),
                         "examinados": ("contatos_examinados", "sum")})


def populacao() -> pd.DataFrame:
    p = pd.read_parquet(ORIGEM / "populacao_ibge_br.parquet")
    p["uf"] = _uf(p["cod_mun6"])
    p["pop_0_14"] = p["populacao"].where(p["faixa"] <= 2, 0)
    return _por_area(p, {"pop": ("populacao", "sum"), "pop_0_14": ("pop_0_14", "sum")})


def indicadores() -> pd.DataFrame:
    t = silver().merge(contatos(), on=["codigo", "ano"], how="left").merge(
        populacao(), on=["codigo", "ano"], how="left")
    return pd.DataFrame({
        "codigo": t["codigo"], "ano": t["ano"],
        "casos_novos": t["casos_novos"],
        "taxa_deteccao": t["casos_novos"] / t["pop"] * 1e5,
        "casos_0_14": t["casos_0_14"],
        "taxa_0_14": t["casos_0_14"] / t["pop_0_14"] * 1e5,
        "pct_mb": 100 * t["mb"] / t["casos_novos"],
        "pct_gif_avaliado_diag": 100 * t["avaliados"] / t["casos_novos"],
        "pct_grau2_diag": 100 * t["grau2"] / t["avaliados"],
        "pct_cura_coorte": 100 * t["curas"] / t["coorte"],
        "pct_gif_avaliado_cura": 100 * t["curas_avaliadas"] / t["curas"],
        "pct_contatos_examinados": 100 * t["examinados"] / t["registrados"],
    })


def comparar() -> pd.DataFrame:
    ms = pd.read_parquet(ORIGEM / "boletim_ms.parquet")
    ms = ms[ms["nivel"].isin(["BR", "UF"])]
    nossos = indicadores().melt(["codigo", "ano"], var_name="indicador", value_name="silver")
    t = ms.merge(nossos, on=["codigo", "ano", "indicador"])
    t = t.rename(columns={"valor": "ms"})
    t["dif"] = t["silver"] - t["ms"]
    return t[["codigo", "ano", "indicador", "silver", "ms", "dif"]]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ano", type=int, default=2024)
    a = p.parse_args()

    pd.set_option("display.width", 250)
    t = comparar()
    br = t[t["codigo"] == "BR"].pivot(index="ano", columns="indicador", values="dif")
    print("Brasil, silver − MS (pontos; casos em número):")
    print(br.round(2).to_string())
    print(f"\nUFs {a.ano}, silver − MS:")
    print(t[t["ano"] == a.ano].pivot(index="codigo", columns="indicador", values="dif").round(1).to_string())


if __name__ == "__main__":
    main()
