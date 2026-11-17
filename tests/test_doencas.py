"""O registro de doenças e o pack (cópia do hansepe)."""

from __future__ import annotations

import pytest

from src import doencas

pack = doencas.carregar()


def test_o_pack_padrao_carrega_e_cumpre_o_contrato() -> None:
    for atributo in doencas.CONTRATO:
        assert hasattr(pack, atributo), atributo


def test_doenca_desconhecida_falha() -> None:
    with pytest.raises(ValueError):
        doencas.carregar("nao_existe")


def test_toda_metrica_do_mapa_tem_rotulo_curto() -> None:
    for metrica in pack.METRICAS_MAPA:
        assert pack.rotulo_curto(metrica) != metrica, metrica


@pytest.mark.parametrize(("metrica", "valor", "classe"), [
    ("incid", 1.99, "Baixo"),
    ("incid", 2.0, "Médio"),
    ("incid", 40, "Hiperendêmico"),
    ("cura_pct", 74.9, "Precário"),
    ("cura_pct", 90, "Bom"),
    ("abandono_pct", 9.9, "Bom"),
    ("abandono_pct", 25, "Precário"),
    ("prop_grau2_pct", 10, "Alto"),
])
def test_classe_do_ms(metrica: str, valor: float, classe: str) -> None:
    assert pack.classe_de(metrica, valor) == classe


def test_sem_valor_nao_tem_classe() -> None:
    assert pack.classe_de("incid", None) is None
