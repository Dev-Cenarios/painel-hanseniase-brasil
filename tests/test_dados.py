"""O que o dados.py devolve e a distância até o boletim do MS (jan/2026)."""

from __future__ import annotations

import pytest

from src import dados, doencas

pytestmark = pytest.mark.dado

pack = doencas.carregar()

# Boletim Epidemiológico de Hanseníase, nº especial jan/2026, Brasil (Tabelas 8–10, 14, 16, 17)
BOLETIM = {
    "casos": {2015: 28761, 2019: 27864, 2022: 19635, 2023: 22773, 2024: 22129},
    "incid": {2015: 14.07, 2019: 13.23, 2022: 9.67, 2023: 10.68, 2024: 10.41},
    "taxa_det_0_14": {2015: 4.46, 2019: 3.44, 2023: 2.18, 2024: 2.19},
    "prop_grau2_pct": {2015: 7.5, 2019: 9.9, 2022: 11.5, 2024: 11.5},
    "cura_pct": {2015: 83.5, 2019: 79.4, 2022: 74.6, 2024: 78.0},
    "contatos_pct": {2015: 78.2, 2019: 82.4, 2022: 76.8, 2024: 80.0},
}

# a silver é extração mais nova que a do MS (31/mai/2025); casos em %, o resto em pontos
TOLERANCIA = {"casos": 1.5, "incid": 0.35, "taxa_det_0_14": 0.25, "prop_grau2_pct": 0.5,
              "cura_pct": 2.6, "contatos_pct": 1.6}


def test_anos() -> None:
    assert dados.anos() == list(range(2010, 2026))


def test_kpis_tem_tudo_que_a_tela_pede() -> None:
    pedidas = set(pack.LAYOUT_KPI) | set(pack.INDICADORES_QUALIDADE)
    for fracao in pack.FRACAO_KPI.values():
        pedidas |= set(fracao)
    for area in (None, ("UF", "MT"), ("MUN", "510340")):
        assert pedidas <= set(dados.kpis(2024, area)), area


@pytest.mark.parametrize("metrica", list(BOLETIM))
def test_brasil_perto_do_boletim(metrica: str) -> None:
    for ano, esperado in BOLETIM[metrica].items():
        valor = dados.kpis(ano)[metrica]
        dif = abs(valor / esperado - 1) * 100 if metrica == "casos" else abs(valor - esperado)
        assert dif <= TOLERANCIA[metrica], (ano, valor, esperado)


def test_ufs_perto_do_boletim() -> None:
    """Tabela 8, 2024: as maiores UFs."""
    for uf, casos, taxa in (("MT", 4674, 121.83), ("MA", 1987, 28.34), ("PE", 1711, 17.94),
                            ("SP", 1368, 2.98), ("TO", 911, 57.76)):
        k = dados.kpis(2024, ("UF", uf))
        assert abs(k["casos"] / casos - 1) <= 0.03, (uf, k["casos"])
        assert abs(k["incid"] - taxa) <= 2.0, (uf, k["incid"])


def test_ufs_e_municipios_somam_o_brasil() -> None:
    brasil = dados.kpis(2024)["casos"]
    assert dados.valores_mapa("casos", 2024, "UF").sum() == pytest.approx(brasil, abs=60)
    assert dados.valores_mapa("casos", 2024, "MUN").sum() == pytest.approx(brasil, abs=60)
    mt = dados.valores_mapa("casos", 2024, "MUN", "MT")
    assert mt.sum() == dados.kpis(2024, ("UF", "MT"))["casos"]


def test_mapa_cobre_as_27_ufs_e_os_municipios_da_malha() -> None:
    assert set(dados.valores_mapa("incid", 2024, "UF").index) == set(dados.ufs()["uf"])
    municipios = set(dados.municipios()["cod_mun6"])
    assert len(municipios - set(dados.valores_mapa("incid", 2024, "MUN").index)) <= 1


def test_municipio_sem_caso_e_zero_nao_vazio() -> None:
    casos = dados.valores_mapa("casos", 2024, "MUN")
    assert (casos == 0).sum() > 2000 and casos.notna().all()


def test_grau2_some_com_pouco_gif_avaliado() -> None:
    k = dados.kpis
    for area in (None, ("UF", "RN")):
        for ano in dados.anos():
            v = k(ano, area)
            if v["gif_avaliado_pct"] is not None and v["gif_avaliado_pct"] < 75:
                assert v["prop_grau2_pct"] is None, (area, ano)


def test_ranking_de_taxa_por_municipio_tira_os_pequenos() -> None:
    tabela = dados.ranking("incid", 2024, "MUN", "MT", taxa=True)
    casos = dados.valores_mapa("casos", 2024, "MUN", "MT")
    assert (casos.reindex(tabela["chave"]) >= dados.MINIMO_CASOS_RANKING).all()


def test_nomes() -> None:
    assert dados.nome_area(None) == "Brasil"
    assert dados.nome_area(("UF", "MT")) == "Mato Grosso"
    assert dados.nome_area(("MUN", "510340")) == "Cuiabá (MT)"
    assert dados.uf_de(("MUN", "510340")) == "MT"


@pytest.mark.parametrize("area", [None, ("UF", "MT"), ("MUN", "510340")])
def test_formas_dos_graficos(area) -> None:
    ano = 2024
    assert list(dados.serie_anual("incid", area).columns) == ["ano", "valor"]
    canal = dados.canal(ano, area)
    assert not canal.vazio and len(canal.anos) == 5
    epi = dados.epicurva(2015, ano, area)
    assert len(epi) == 120 and epi["casos"].sum() > 0
    for variavel in pack.VARIAVEIS_DESTAQUE:
        tabela = dados.composicao(variavel, ano, area)
        assert {"categoria", "n", "pct", "total"} <= set(tabela.columns) and not tabela.empty
        assert {"ano", "categoria", "n", "pct"} <= set(dados.serie_composicao(variavel, area).columns)
    pir = dados.piramide(ano, area)
    assert set(pir["sexo"]) == {"M", "F"} and (pir["pop"] > 0).all()
    assert {"contatos_pct", "gif_avaliado_pct", "grau2_pct", "cura_pct", "abandono_pct"} <= set(
        dados.serie_qualidade(area).columns)


def test_coorte_do_ultimo_ano_fica_em_fechamento() -> None:
    ultimo = dados.anos()[-1]
    for area in (None, ("UF", "MT")):
        k = dados.kpis(ultimo, area)
        assert k["coorte_aberta"] and k["cura"] is None and k["cura_pct"] is None, area
    assert dados.kpis(ultimo - 1)["cura_pct"] is not None
