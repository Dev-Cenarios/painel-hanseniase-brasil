"""O app inteiro rodando no AppTest, nos três níveis (Brasil, UF, município).

Confere também que não tem aviso: o resiliencia.painel esconde erro de bloco
atrás de um aviso, e o app "sobe" mesmo com gráfico quebrado.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src import doencas

APP = str(Path(__file__).resolve().parents[1] / "app.py")
LIMITE = 300

pytestmark = pytest.mark.dado

pack = doencas.carregar()


def _rodar(**estado) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=LIMITE)
    for chave, valor in estado.items():
        at.session_state[chave] = valor
    return at.run()


def _conferir(at: AppTest) -> None:
    assert not at.exception, [e.value for e in at.exception]
    assert not at.warning, [w.value for w in at.warning]


def _cards(at: AppTest) -> list[str]:
    return [m.value for m in at.markdown if 'class="kpi-card' in m.value]


def _mapas(at: AppTest) -> list[str]:
    return [c.proto.json_args for c in at.get("component_instance") if '"spec"' in c.proto.json_args]


def test_sobe_com_as_secoes_do_hansepe() -> None:
    at = _rodar()
    _conferir(at)
    # 5 da faixa, 2 proporções e 4 de qualidade
    assert len(_cards(at)) == 11
    texto = " ".join(m.value for m in at.markdown)
    for secao in ("Indicadores de qualidade do programa", "Tópicos de interesse",
                  "Classificação operacional por ano", "Casos de 0 a 14 anos por ano"):
        assert secao in texto, secao
    assert len(_mapas(at)) == 1


def test_mapa_do_brasil_por_municipio() -> None:
    at = _rodar(recorte="MUN")
    _conferir(at)
    assert len(_mapas(at)) == 1


@pytest.mark.parametrize("metrica", pack.METRICAS_MAPA)
def test_toda_metrica_do_mapa_desenha(metrica: str) -> None:
    _conferir(_rodar(metrica=metrica))


@pytest.mark.parametrize("area", [("UF", "MT"), ("MUN", "510340")])
def test_uf_e_municipio_mudam_os_cards(area) -> None:
    brasil, recorte = _rodar(), _rodar(area=area)
    _conferir(recorte)
    assert _cards(brasil)[:5] != _cards(recorte)[:5]
    texto = " ".join(m.value for m in recorte.markdown)
    assert "Mato Grosso" in texto
    if area[0] == "MUN":
        assert "Cuiabá" in texto


def test_ano_antigo_nao_quebra() -> None:
    _conferir(_rodar(ano=2010))


def test_ultimo_ano_avisa_coorte_em_fechamento() -> None:
    at = _rodar(metrica="cura_pct")
    _conferir(at)
    assert any("em fechamento" in c.value for c in at.caption)
