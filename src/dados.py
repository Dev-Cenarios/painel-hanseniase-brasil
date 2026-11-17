"""Tudo que o app.py pede de dado passa por aqui.

``area`` é o recorte: ``None`` é o Brasil, ``("UF", "MT")`` uma UF (sigla) e
``("MUN", "510340")`` um município (``cod_mun6``). As contas ficam no
fonte_sinan.py, do jeito do boletim do MS.

- sem dado é None/NaN, nunca zero
"""

from __future__ import annotations

from functools import lru_cache

import geopandas as gpd
import pandas as pd

from src import fonte_sinan as _fonte

GRAUS_SERIE = _fonte.GRAUS_SERIE
MALHA_UFS = _fonte.RAIZ / "geo" / "ufs.parquet"

# ranking de taxa por município só entre quem tem casos (senão o topo é município de mil habitantes)
MINIMO_CASOS_RANKING = 10

Canal = _fonte.Canal


def disponivel() -> bool:
    """Se os parquets estão lá (sem eles os testes de dado são pulados)."""
    return _fonte.disponivel()


def extraido_em() -> str:
    return _fonte.extraido_em()


def anos() -> list[int]:
    return _fonte.anos()


# ---------------------------------------------------------------------------
# Geografia
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def municipios() -> gpd.GeoDataFrame:
    """``cod_mun6``, ``nome_mun``, ``uf``, ``geometry`` (5.571)."""
    return gpd.read_parquet(_fonte.MALHA_MUN)


@lru_cache(maxsize=1)
def ufs() -> gpd.GeoDataFrame:
    """``uf`` (sigla), ``nome_uf``, ``geometry``."""
    return gpd.read_parquet(MALHA_UFS)


def municipios_da_uf(uf: str) -> gpd.GeoDataFrame:
    m = municipios()
    return m[m["uf"] == uf].reset_index(drop=True)


@lru_cache(maxsize=1)
def _nomes_mun() -> dict[str, str]:
    m = municipios()
    return dict(zip(m["cod_mun6"], m["nome_mun"], strict=True))


@lru_cache(maxsize=1)
def _uf_do_mun() -> dict[str, str]:
    m = municipios()
    return dict(zip(m["cod_mun6"], m["uf"], strict=True))


@lru_cache(maxsize=1)
def _nomes_uf() -> dict[str, str]:
    u = ufs()
    return dict(zip(u["uf"], u["nome_uf"], strict=True))


def uf_de(area) -> str | None:
    """A UF da área (a própria, ou a do município)."""
    if area is None:
        return None
    nivel, codigo = area
    return codigo if nivel == "UF" else _uf_do_mun().get(codigo)


def nome_area(area) -> str:
    if area is None:
        return "Brasil"
    nivel, codigo = area
    if nivel == "UF":
        return _nomes_uf().get(codigo, codigo)
    return f"{_nomes_mun().get(codigo, codigo)} ({_uf_do_mun().get(codigo, '')})"


def nome_uf(sigla: str) -> str:
    return _nomes_uf().get(sigla, sigla)


# ---------------------------------------------------------------------------
# Números
# ---------------------------------------------------------------------------

def kpis(ano: int, area=None) -> dict:
    """Cada métrica do pack no ano, com numerador e denominador das proporções."""
    return _fonte.kpis(ano, area)


def valores_mapa(metrica: str, ano: int, nivel: str = "UF", uf: str | None = None) -> pd.Series:
    """A métrica por UF (sigla) ou por município (``cod_mun6``), opcionalmente só de uma UF."""
    return _fonte.valores(metrica, ano, nivel, uf)


def ranking(metrica: str, ano: int, nivel: str = "UF", uf: str | None = None,
            top_n: int | None = None, taxa: bool = False) -> pd.DataFrame:
    """``chave``, ``nome``, ``valor``, do maior pro menor.

    Taxa por município só entre os com ``MINIMO_CASOS_RANKING`` casos ou mais.
    """
    serie = valores_mapa(metrica, ano, nivel, uf)
    if taxa and nivel == "MUN":
        casos = valores_mapa("casos", ano, nivel, uf)
        serie = serie[casos.reindex(serie.index) >= MINIMO_CASOS_RANKING]
    serie = serie.dropna().sort_values(ascending=False)
    nomes = _nomes_uf() if nivel == "UF" else _nomes_mun()
    tabela = pd.DataFrame({"chave": serie.index, "nome": [nomes.get(c, c) for c in serie.index],
                           "valor": serie.to_numpy()})
    return tabela.head(top_n) if top_n else tabela


def serie_anual(metrica: str, area=None) -> pd.DataFrame:
    """``ano``, ``valor``."""
    return _fonte.serie_anual(metrica, area)


def canal(ano: int, area=None, grau: str | None = None) -> Canal:
    return _fonte.canal(ano, area, grau)


def meses_fora_da_faixa(c: Canal) -> pd.DataFrame:
    return _fonte.meses_fora_da_faixa(c)


def epicurva(ano_min: int, ano_max: int, area=None) -> pd.DataFrame:
    return _fonte.epicurva(ano_min, ano_max, area)


def piramide(ano: int, area=None) -> pd.DataFrame:
    return _fonte.piramide(ano, area)


def composicao(variavel: str, ano: int, area=None) -> pd.DataFrame:
    return _fonte.composicao(variavel, ano, area)


def serie_composicao(variavel: str, area=None) -> pd.DataFrame:
    return _fonte.serie_composicao(variavel, area)


def total_de_casos(ano: int, area=None) -> int:
    return _fonte.total_de_casos(ano, area)


def serie_qualidade(area=None) -> pd.DataFrame:
    return _fonte.serie_qualidade(area)


def serie_classificacao(area=None) -> pd.DataFrame:
    return _fonte.serie_classificacao(area)


def serie_0_14(area=None) -> pd.DataFrame:
    return _fonte.serie_0_14(area)
