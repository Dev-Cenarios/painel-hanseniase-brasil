"""Os números do Brasil, das UFs e dos municípios: SINAN de hanseníase contado como o boletim do MS.

- caso novo = modo de entrada "Caso novo", sem "Erro diagnóstico", pelo ano do diagnóstico e residência
- coorte do MS: PB diagnosticados em A−1 e MB em A−2; sai só quem foi transferido pra outro
  estado ou país, e a cura só conta com alta até 31/12 de A (assim fecha com o boletim)
- grau 2 sobre os avaliados, e só com GIF avaliado em 75% ou mais
- população = pop_ibge (a mesma do boletim), e em 2022 o total do Censo, como o MS

``area`` é ``None`` (Brasil), ``("UF", "MT")`` ou ``("MUN", "510340")``.
Os nomes das métricas são os do hansepe.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = RAIZ / "data" / "origem"
SINAN = ORIGEM / "sinan_br_hans.parquet"
CONTATOS = ORIGEM / "sinan_br_contatos.parquet"
POP_IBGE = ORIGEM / "populacao_ibge_br.parquet"
CENSO_2022 = ORIGEM / "censo_2022.parquet"
MALHA_MUN = RAIZ / "geo" / "municipios.parquet"

# pop_ibge vai de 2010 a 2025; 2026 ainda tá aberto
ANOS = tuple(range(2010, 2026))

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro")

# abaixo disso a proporção é ruído e vira sem dado
MINIMO_PARA_PERCENTUAL = 5

# o MS só lê o grau 2 com GIF avaliado em pelo menos 75%
MINIMO_GIF_AVALIADO = 75

# coorte com mais que isso sem alta ainda não fechou
MAXIMO_SEM_ALTA = 0.25

# coorte do último ano da série ainda recebe alta lançada com atraso (2025 saía 8 pp abaixo)
ANO_EM_FECHAMENTO = ANOS[-1]

# quantos anos anteriores fazem a faixa do canal endêmico (o hansepe usa 5)
ANOS_REFERENCIA = 5

# tirar toda transferência põe a cura ~5 pp acima do MS
SAI_DA_COORTE = ("Transferência p/ outro estado", "Transferência p/ outro país")
SAI_DA_COORTE_COD = ("4", "5")

GRAUS_SERIE = ("Grau zero", "Grau I", "Grau II", "Não avaliado", "Não informado")
GIF_AVALIADO = ("Grau zero", "Grau I", "Grau II")

IGNORADO = "Ignorado/em branco"
_IGNORADOS = {"Ignorado", "Não informado", "Nao informado", None}

FAIXAS = (("0 a 4", 0, 4), ("5 a 9", 5, 9), ("10 a 14", 10, 14), ("15 a 19", 15, 19),
          ("20 a 29", 20, 29), ("30 a 39", 30, 39), ("40 a 49", 40, 49), ("50 a 59", 50, 59),
          ("60 a 69", 60, 69), ("70 a 79", 70, 79), ("80 e mais", 80, 200))

# variável da ficha (código do hansepe) → coluna da silver e a ordem das categorias
TOPICOS: dict[str, tuple[str, tuple[str, ...]]] = {
    "CLASSOPERA": ("classificacao_operacional", ("PB - Paucibacilar", "MB - Multibacilar")),
    "FORMACLINI": ("forma_clinica", ("I - Indeterminada", "T - Tuberculóide", "D - Dimorfa",
                                     "V - Virchowiana", "Não classificado")),
    "AVALIA_N": ("avaliacao_incapacidade_diagnostico", ("Grau zero", "Grau I", "Grau II", "Não avaliado")),
    "BACILOSCOP": ("baciloscopia", ("Positiva", "Negativa", "Não realizada")),
    "NERVOSAFET": ("nervos_afetados", ()),
    "EPIS_RACIO": ("episodio_reacional", ("Reação tipo 1", "Reação tipo 2", "Reação tipo 1 e 2")),
    "MODOENTR": ("modo_entrada", ("Caso novo", "Transferência do mesmo município (outra unidade)",
                                  "Transferência de outro município (mesma UF)",
                                  "Transferência de outro estado", "Transferência de outro país",
                                  "Recidiva", "Outros reingressos")),
    "MODODETECT": ("modo_deteccao", ("Encaminhamento", "Demanda espontânea", "Exame de coletividade",
                                     "Exame de contatos", "Outros modos")),
    "ESQ_INI_N": ("esquema_inicial", ("PQT/PB/6 doses", "PQT/MB/12 doses", "Outros Esquemas Substitutos")),
    "DOSE_RECEB": ("doses_recebidas", ()),
    "TPALTA_N": ("tipo_alta", ("Cura", "Transferência p/ mesmo município", "Transferência p/ outro município",
                               "Transferência p/ outro estado", "Transferência p/ outro país",
                               "Transferência não especificada", "Óbito", "Abandono")),
    "CS_RACA": ("raca_cor", ("Branca", "Preta", "Amarela", "Parda", "Indigena")),
    "CS_ESCOL_N": ("escolaridade", ("Analfabeto", "1a a 4a serie incompleta do EF", "4a serie completa do EF",
                                    "5a a 8a serie incompleta do EF", "Ensino fundamental completo",
                                    "Ensino medio incompleto", "Ensino medio completo",
                                    "Educacao superior incompleta", "Educacao superior completa",
                                    "Nao se aplica")),
    "CS_GESTANT": ("gestante", ("1o Trimestre", "2o Trimestre", "3o Trimestre", "Idade gestacional ignorada",
                                "Nao", "Nao se aplica")),
}

# como a categoria aparece (sem acento na fonte, ou com o código na frente)
_NOMES = {
    "PB - Paucibacilar": "Paucibacilar", "MB - Multibacilar": "Multibacilar",
    "I - Indeterminada": "Indeterminada", "T - Tuberculóide": "Tuberculoide", "D - Dimorfa": "Dimorfa",
    "V - Virchowiana": "Virchowiana", "Não classificado": "Não classificada",
    "Grau zero": "Grau 0", "Grau I": "Grau I", "Grau II": "Grau II",
    "Indigena": "Indígena", "Nao se aplica": "Não se aplica", "Nao": "Não",
    "Analfabeto": "Analfabeto", "1a a 4a serie incompleta do EF": "1ª a 4ª série incompleta",
    "4a serie completa do EF": "4ª série completa", "5a a 8a serie incompleta do EF": "5ª a 8ª série incompleta",
    "Ensino fundamental completo": "Fundamental completo", "Ensino medio incompleto": "Médio incompleto",
    "Ensino medio completo": "Médio completo", "Educacao superior incompleta": "Superior incompleto",
    "Educacao superior completa": "Superior completo",
    "Transferência do mesmo município (outra unidade)": "Transf. mesmo município",
    "Transferência de outro município (mesma UF)": "Transf. outro município",
    "Transferência de outro estado": "Transf. outro estado", "Transferência de outro país": "Transf. outro país",
}

# variáveis em que o valor é a quantidade
NUMERICAS = frozenset({"NERVOSAFET", "DOSE_RECEB"})

NIVEIS = ("BR", "UF", "MUN")


def disponivel() -> bool:
    return SINAN.is_file() and POP_IBGE.is_file() and CONTATOS.is_file()


def anos() -> list[int]:
    return list(ANOS)


def extraido_em() -> str:
    return datetime.date.fromtimestamp(SINAN.stat().st_mtime).strftime("%d/%m/%Y")


# ---------------------------------------------------------------------------
# Território
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _uf_do_prefixo() -> dict[str, str]:
    """Os dois primeiros dígitos do município → sigla da UF (lido da malha)."""
    malha = pd.read_parquet(MALHA_MUN, columns=["cod_mun6", "uf"])
    return dict(zip(malha["cod_mun6"].str[:2], malha["uf"], strict=False))


def _sigla(cod_mun6: pd.Series) -> pd.Series:
    return cod_mun6.str[:2].map(_uf_do_prefixo())


def _cod6(coluna: pd.Series) -> pd.Series:
    """Código IBGE (6 ou 7 dígitos, número ou texto) → texto de 6 dígitos."""
    return pd.to_numeric(coluna, errors="coerce").astype("Int64").astype(str).str[:6].where(coluna.notna())


def _da_area(df: pd.DataFrame, area) -> pd.DataFrame:
    if area is None:
        return df
    nivel, codigo = area
    return df[df["uf" if nivel == "UF" else "mun"] == codigo]


# ---------------------------------------------------------------------------
# Bases
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _notificacoes() -> pd.DataFrame:
    """Todas as notificações sem erro diagnóstico, com ano/mês do diagnóstico, idade e área."""
    df = pd.read_parquet(SINAN)
    df = df[df["tipo_alta"].fillna("") != "Erro diagnóstico"].copy()
    diag = pd.to_datetime(df["data_diagnostico"], errors="coerce")
    df["ano"] = diag.dt.year.astype("Int64")
    df["mes"] = diag.dt.month.astype("Int64")
    idade = df["idade_notificada"].fillna("")
    # "005 mes(es)" é bebê, não 5 anos
    df["idade"] = pd.to_numeric(idade.str[:3], errors="coerce").where(idade.str.contains("ano"), 0)
    df["idade"] = df["idade"].where(idade != "")
    df["novo"] = df["modo_entrada"] == "Caso novo"
    df["mb"] = df["classificacao_operacional"].str.startswith("MB", na=False)
    df["mun"] = _cod6(df["municipio_residencia_id"])
    df["uf"] = _sigla(df["mun"])
    return df


def _casos_novos(ano: int | None = None, area=None) -> pd.DataFrame:
    df = _notificacoes()
    df = _da_area(df[df["novo"]], area)
    return df if ano is None else df[df["ano"] == ano]


@lru_cache(maxsize=1)
def _pop_ibge() -> pd.DataFrame:
    pop = pd.read_parquet(POP_IBGE)
    pop["mun"] = pop["cod_mun6"].astype(str)
    pop["uf"] = _sigla(pop["mun"])
    return pop


def _somar(df: pd.DataFrame, colunas: list[str], ano: str = "ano") -> pd.DataFrame:
    """Soma por Brasil, UF e município: ``nivel``, ``codigo``, ``ano`` + colunas."""
    partes = [df.groupby(ano)[colunas].sum().reset_index().assign(nivel="BR", codigo="BR")]
    for nivel, chave in (("UF", "uf"), ("MUN", "mun")):
        g = df.dropna(subset=[chave]).groupby([chave, ano])[colunas].sum().reset_index()
        partes.append(g.rename(columns={chave: "codigo"}).assign(nivel=nivel))
    t = pd.concat(partes, ignore_index=True).rename(columns={ano: "ano"})
    t["ano"] = t["ano"].astype(int)
    return t.set_index(["nivel", "codigo", "ano"])


@lru_cache(maxsize=1)
def _contagens() -> pd.DataFrame:
    """Numeradores e denominadores de tudo, por nível × código × ano."""
    notif = _notificacoes()
    cn = notif[notif["novo"]].copy()
    gif = cn["avaliacao_incapacidade_diagnostico"].fillna("")
    cn = cn.assign(
        casos=1,
        menores=(cn["idade"] < 15).astype(int),
        classificados=cn["classificacao_operacional"].str[:2].isin(["PB", "MB"]).astype(int),
        multibacilares=cn["mb"].astype(int),
        avaliados=gif.isin(GIF_AVALIADO).astype(int),
        grau2=(gif == "Grau II").astype(int),
    )
    diag = _somar(cn.dropna(subset=["ano"]),
                  ["casos", "menores", "classificados", "multibacilares", "avaliados", "grau2"])

    coorte = cn[~cn["tipo_alta"].isin(SAI_DA_COORTE)].dropna(subset=["ano"]).copy()
    coorte["ano_aval"] = coorte["ano"] + np.where(coorte["mb"], 2, 1)
    alta = coorte["tipo_alta"].fillna("Não informado")
    ano_alta = pd.to_datetime(coorte["data_alta"], errors="coerce").dt.year
    coorte = coorte.assign(
        n_coorte=1,
        sem_alta=alta.isin(["Não informado", ""]).astype(int),
        curas=((alta == "Cura") & (ano_alta <= coorte["ano_aval"]).fillna(False)).astype(int),
        abandonos=(alta == "Abandono").astype(int),
    )
    coortes = _somar(coorte, ["n_coorte", "sem_alta", "curas", "abandonos"], ano="ano_aval")

    c = pd.read_parquet(CONTATOS)
    alta_c = c["tpalta_n"].astype(str)
    c = c[(c["modoentr"].astype(str) == "1") & (alta_c != "8") & ~alta_c.isin(SAI_DA_COORTE_COD)].copy()
    c["mun"] = _cod6(c["cod_mun6"])
    c["uf"] = _sigla(c["mun"])
    c["ano_aval"] = c["ano_diagnostico"] + np.where(c["classopera"].astype(str) == "2", 2, 1)
    c = c.rename(columns={"contatos_registrados": "registrados", "contatos_examinados": "examinados"})
    contatos = _somar(c, ["registrados", "examinados"], ano="ano_aval")

    notif = notif.dropna(subset=["ano"]).assign(
        notificados=1, recidivas=(notif["modo_entrada"] == "Recidiva").astype(int))
    recidivas = _somar(notif, ["notificados", "recidivas"])

    pop = _pop_ibge().assign(pop_0_14=lambda p: p["populacao"].where(p["faixa"] <= 2, 0))
    pop = _somar(pop.rename(columns={"populacao": "pop"}), ["pop", "pop_0_14"])
    if CENSO_2022.is_file():
        # o MS usa o Censo em 2022; 0–14 segue o pop_ibge
        censo = pd.read_parquet(CENSO_2022).rename(columns={"populacao": "pop"})
        censo = censo.assign(mun=censo["cod_mun6"], uf=_sigla(censo["cod_mun6"]), ano=2022)
        censo = _somar(censo, ["pop"])["pop"]
        pop.loc[censo.index.intersection(pop.index), "pop"] = censo

    # toda área com população entra, com zero onde não houve caso
    t = pop.join([diag, coortes, contatos, recidivas], how="left")
    contagens = [c for c in t.columns if c not in ("pop", "pop_0_14")]
    t[contagens] = t[contagens].fillna(0).astype(float)
    return t[t.index.get_level_values("ano").isin(ANOS)].sort_index()


def _div(parte: pd.Series, total: pd.Series, fator: float = 100, minimo: int = 0) -> pd.Series:
    ok = (total > 0) & (total >= minimo)
    return (parte / total.where(ok) * fator).astype(float)


@lru_cache(maxsize=1)
def indicadores() -> pd.DataFrame:
    """Todas as métricas do pack, por ``nivel`` × ``codigo`` × ``ano``, com os numeradores."""
    t = _contagens()
    m = MINIMO_PARA_PERCENTUAL
    gif_aval = _div(t["avaliados"], t["casos"], minimo=m)
    aberta = (t["n_coorte"] > 0) & (t["sem_alta"] / t["n_coorte"].where(t["n_coorte"] > 0) > MAXIMO_SEM_ALTA)
    aberta = aberta | (t.index.get_level_values("ano") == ANO_EM_FECHAMENTO)
    return pd.DataFrame({
        "casos": t["casos"],
        "pop": t["pop"],
        "incid": _div(t["casos"], t["pop"], 1e5),
        "casos_0_14": t["menores"],
        "pop_0_14": t["pop_0_14"],
        "taxa_det_0_14": _div(t["menores"], t["pop_0_14"], 1e5),
        "cura": t["curas"].mask(aberta),
        "prop_mb_pct": _div(t["multibacilares"], t["classificados"], minimo=m),
        "multibacilares": t["multibacilares"],
        "classificados": t["classificados"],
        "prop_grau2_pct": _div(t["grau2"], t["avaliados"], minimo=m).where(gif_aval >= MINIMO_GIF_AVALIADO),
        "grau2": t["grau2"],
        "avaliacao_base": t["avaliados"],
        "gif_avaliado_pct": gif_aval,
        "gif_avaliados": t["avaliados"],
        "gif_base": t["casos"],
        "cura_pct": _div(t["curas"], t["n_coorte"], minimo=m).mask(aberta),
        "cura_encerrada": t["curas"],
        "encerramentos": t["n_coorte"],
        "abandono_pct": _div(t["abandonos"], t["n_coorte"], minimo=m).mask(aberta),
        "abandonos": t["abandonos"],
        "saidas": t["n_coorte"],
        "contatos_pct": _div(t["examinados"], t["registrados"], minimo=m).mask(aberta),
        "contatos_examinados": t["examinados"],
        "contatos_registrados": t["registrados"],
        "recidiva_pct": _div(t["recidivas"], t["notificados"], minimo=m),
        "coorte_aberta": aberta,
        "cobertura_saidas": 1 - t["sem_alta"] / t["n_coorte"].where(t["n_coorte"] > 0),
    })


def _chave(area) -> tuple[str, str]:
    return ("BR", "BR") if area is None else area


def _limpo(valor):
    if isinstance(valor, (bool, np.bool_)):
        return bool(valor)
    return None if pd.isna(valor) else float(valor)


def kpis(ano: int, area=None) -> dict[str, float | bool | None]:
    """Todas as métricas do pack no ano, com numerador e denominador das proporções."""
    try:
        linha = indicadores().loc[(*_chave(area), ano)]
    except KeyError:
        return {}
    return {k: _limpo(v) for k, v in linha.items()}


def kpis_todos(area=None) -> pd.DataFrame:
    nivel, codigo = _chave(area)
    try:
        return indicadores().loc[(nivel, codigo)].reset_index()
    except KeyError:
        return pd.DataFrame(columns=["ano", *indicadores().columns])


def valores(metrica: str, ano: int, nivel: str, uf: str | None = None) -> pd.Series:
    """A métrica de cada UF (sigla) ou município (código de 6 dígitos) no ano."""
    t = indicadores().xs(nivel, level="nivel")
    t = t[t.index.get_level_values("ano") == ano].droplevel("ano")
    if uf and nivel == "MUN":
        t = t[_sigla(t.index.to_series()) == uf]
    return t[metrica].rename(metrica)


def serie_anual(metrica: str, area=None) -> pd.DataFrame:
    t = kpis_todos(area)
    return pd.DataFrame({"ano": t["ano"], "valor": t[metrica]})


def serie_qualidade(area=None) -> pd.DataFrame:
    """Os indicadores dos tópicos, por ano: ``contatos_pct``, ``gif_avaliado_pct``, ``grau2_pct``…"""
    t = kpis_todos(area)
    return pd.DataFrame({"ano": t["ano"], "contatos_pct": t["contatos_pct"],
                         "gif_avaliado_pct": t["gif_avaliado_pct"], "grau2_pct": t["prop_grau2_pct"],
                         "cura_pct": t["cura_pct"], "abandono_pct": t["abandono_pct"]})


def serie_classificacao(area=None) -> pd.DataFrame:
    """``ano``, ``pb``, ``mb``, ``prop_mb``."""
    t = kpis_todos(area)
    return pd.DataFrame({"ano": t["ano"], "pb": t["classificados"] - t["multibacilares"],
                         "mb": t["multibacilares"], "prop_mb": t["prop_mb_pct"]})


def serie_0_14(area=None) -> pd.DataFrame:
    """``ano``, ``casos``, ``taxa``."""
    t = kpis_todos(area)
    return pd.DataFrame({"ano": t["ano"], "casos": t["casos_0_14"], "taxa": t["taxa_det_0_14"]})


def populacao(ano: int, area=None, idade_max: int | None = None) -> float | None:
    k = kpis(ano, area)
    return k.get("pop_0_14" if idade_max == 14 else "pop")


# ---------------------------------------------------------------------------
# Mês: canal endêmico e epicurva
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Canal:
    """As camadas do canal endêmico, no formato do core (o mesmo do hansepe)."""

    faixa: pd.DataFrame
    referencia: pd.DataFrame
    atual: pd.DataFrame
    anos: tuple[int, ...]

    @property
    def vazio(self) -> bool:
        return self.atual.empty or self.faixa.empty


def _incidencia_mensal(ano: int, area, grau: str | None) -> pd.DataFrame:
    cn = _casos_novos(ano, area)
    if grau:
        cn = cn[cn["avaliacao_incapacidade_diagnostico"].fillna("Não informado") == grau]
    pop = populacao(ano, area)
    por_mes = cn["mes"].value_counts().reindex(range(1, 13), fill_value=0)
    return pd.DataFrame({"mes": por_mes.index, "mes_nome": [MESES[m - 1] for m in por_mes.index],
                         "valor": por_mes.to_numpy() / pop * 1e5 if pop else np.nan})


def canal(ano: int, area=None, grau: str | None = None) -> Canal:
    """O ano contra a faixa interquartil dos anos anteriores (a regra do hansepe)."""
    atual = _incidencia_mensal(ano, area, grau)
    anteriores = [_incidencia_mensal(a, area, grau).assign(ano=a)
                  for a in range(ano - ANOS_REFERENCIA, ano) if a in ANOS]
    meses = atual[["mes", "mes_nome"]]
    if not anteriores:
        return Canal(meses.assign(q1=np.nan, q3=np.nan),
                     pd.DataFrame(columns=["mes", "mes_nome", "ano", "valor"]), atual, ())
    historico = pd.concat(anteriores, ignore_index=True)
    quartis = historico.groupby("mes")["valor"].agg(
        q1=lambda s: float(np.quantile(s, 0.25)), q3=lambda s: float(np.quantile(s, 0.75)),
    ).reset_index()
    return Canal(meses.merge(quartis, on="mes", how="left"), historico[["mes", "mes_nome", "ano", "valor"]],
                 atual, tuple(sorted(historico["ano"].unique())))


def meses_fora_da_faixa(c: Canal) -> pd.DataFrame:
    if c.vazio:
        return pd.DataFrame(columns=["mes", "valor", "q1", "q3", "posicao"])
    j = c.atual.merge(c.faixa[["mes", "q1", "q3"]], on="mes")
    fora = j[(j["valor"] > j["q3"]) | (j["valor"] < j["q1"])].copy()
    fora["posicao"] = np.where(fora["valor"] > fora["q3"], "acima", "abaixo")
    return fora


def epicurva(ano_min: int, ano_max: int, area=None) -> pd.DataFrame:
    """Casos novos por mês em série contínua: ``ano_mes``, ``ano``, ``mes``, ``casos``."""
    cn = _casos_novos(area=area)
    cn = cn[(cn["ano"] >= ano_min) & (cn["ano"] <= ano_max)]
    idx = pd.MultiIndex.from_product([range(ano_min, ano_max + 1), range(1, 13)], names=["ano", "mes"])
    serie = cn.groupby(["ano", "mes"]).size().reindex(idx, fill_value=0).rename("casos").reset_index()
    serie["ano_mes"] = serie["ano"].astype(str) + "-" + serie["mes"].astype(str).str.zfill(2)
    return serie[["ano_mes", "ano", "mes", "casos"]]


# ---------------------------------------------------------------------------
# Perfil
# ---------------------------------------------------------------------------

def piramide(ano: int, area=None) -> pd.DataFrame:
    """``sexo``, ``faixa_ord``, ``faixa_etaria``, ``valor``, ``pop`` (a do core)."""
    cn = _casos_novos(ano, area)
    pop = _da_area(_pop_ibge(), area)
    pop = pop[pop["ano"] == ano]
    sexo = cn["sexo"].map({"Masculino": "M", "Feminino": "F"})
    registros = []
    for s in ("M", "F"):
        for ordem, (nome, de, ate) in enumerate(FAIXAS):
            casos = ((sexo == s) & cn["idade"].between(de, ate)).sum()
            # a população vem em faixas de 5 anos (faixa 16 = 80+)
            p = pop[(pop["sexo"] == s) & (pop["faixa"] * 5).between(de, ate)]["populacao"].sum()
            registros.append({"sexo": s, "faixa_ord": ordem, "faixa_etaria": nome,
                              "valor": float(casos), "pop": float(p)})
    return pd.DataFrame(registros)


def _categorias(variavel: str, linhas: pd.DataFrame) -> pd.Series:
    """A categoria de cada caso, já no nome da tela; ``None`` pra campo vazio."""
    coluna, _ = TOPICOS[variavel]
    valores_ = linhas[coluna]
    if variavel in NUMERICAS:
        return pd.to_numeric(valores_, errors="coerce").astype("Int64").astype(str).where(valores_.notna())
    return valores_.map(lambda v: None if v in _IGNORADOS or v != v else _NOMES.get(v, v))


def _ordem(variavel: str, presentes) -> list[str]:
    _, ordem = TOPICOS[variavel]
    if variavel in NUMERICAS:
        return sorted(presentes, key=lambda c: int(c))
    conhecidas = [_NOMES.get(c, c) for c in ordem]
    return [c for c in conhecidas if c in presentes] + sorted(c for c in presentes if c not in conhecidas)


def total_de_casos(ano: int, area=None) -> int:
    return len(_casos_novos(ano, area))


def composicao(variavel: str, ano: int, area=None) -> pd.DataFrame:
    """``categoria``, ``n``, ``pct``, ``total`` dos casos novos com o campo preenchido."""
    cat = _categorias(variavel, _casos_novos(ano, area)).dropna()
    n = cat.value_counts()
    n = n.reindex(_ordem(variavel, set(n.index)))
    total = float(n.sum())
    pct = (n / total * 100).to_numpy() if total >= MINIMO_PARA_PERCENTUAL else [None] * len(n)
    return pd.DataFrame({"categoria": n.index, "n": n.to_numpy().astype(float), "pct": pct, "total": total})


def serie_composicao(variavel: str, area=None) -> pd.DataFrame:
    """``ano``, ``categoria``, ``n``, ``pct`` (cada ano soma 100%)."""
    cn = _casos_novos(area=area)
    cn = cn[cn["ano"].isin(ANOS)]
    tabela = pd.DataFrame({"ano": cn["ano"].astype(int), "categoria": _categorias(variavel, cn)}).dropna()
    n = tabela.groupby(["ano", "categoria"]).size().rename("n").reset_index()
    n["pct"] = n["n"] / n.groupby("ano")["n"].transform("sum") * 100
    ordem = {c: i for i, c in enumerate(_ordem(variavel, set(n["categoria"])))}
    return n.sort_values(["ano", "categoria"], key=lambda s: s.map(ordem) if s.name == "categoria" else s)
