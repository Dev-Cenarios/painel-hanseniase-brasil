# Guia de desenvolvimento

Para quem vai mexer no código: comandos, arquitetura e as regras que já
custaram uma investigação. O que o painel mostra está no README.

Painel **Hanseníase no Brasil**, em Streamlit. Filho do `modelo`, neto do
**`cenarios-core`** (`../cenarios-core`), de onde vêm mapa, gráficos e
contenção de falha, instalado do wheel em `vendor/` em versão fixa. Nasceu
em 29/out/2026 e no mesmo dia ligou no SINAN (`silver.hanseniase`, nacional).
A régua é o Boletim Epidemiológico de Hanseníase do MS (jan/2026); o
levantamento e a conferência estão em `docs/levantamento.md`.

**A tela é a do hansedf/hansepe** (mesmas seções, cards, réguas e o pack com
os mesmos nomes de métrica). Navegação **Brasil → UF → município**: no Brasil
o mapa é por UF ou por município (5.571); clicar numa UF abre os municípios
dela; clicar num município mostra os números dele; clicar de novo volta um nível.

Documentação, código, commits e comentários em português. A receita da
família é `../sinan/docs/como-fazer.md`.

- Mudança que serve a outros painéis vai para o core, não para cá.

## Comandos

Ambiente: `../sinan/.venv` (Python 3.13), com o core instalado.

```bash
python -m scripts.extrair_sinan_br        # silver.hanseniase → data/origem (VPN)
python -m scripts.extrair_contatos_br     # contatos do public.sinan_hans → data/origem (VPN)
python -m scripts.extrair_populacao_br    # pop_ibge → data/origem (VPN)
python -m scripts.extrair_censo_2022      # Censo 2022 do SIDRA → data/origem (o MS usa em 2022)
python -m scripts.extrair_boletim_ms      # tabelas do boletim do MS → data/origem (baixa o PDF)
python -m scripts.conferir_boletim        # silver × boletim, Brasil e UF
streamlit run app.py
pytest
ruff check --select F app.py src tests scripts
docker compose up -d --build              # exige .env (copie de .env.exemplo)
```

## Arquitetura

`app.py` (composição) → `src/dados.py` (fachada, recorte por `area`) →
`src/fonte_sinan.py` (as contas) e `src/doencas/` (pack) →
`cenarios_core.mapa` / `.grafico_componente`.

- **`area`** é `None` (Brasil), `("UF", "MT")` (sigla) ou `("MUN", "510340")`
  (`cod_mun6`, texto de 6 dígitos). Ausência é `None`/`NaN`; município com
  população e sem caso é zero.
- **`src/fonte_sinan.py`** conta como o boletim do MS: caso novo por **ano do
  diagnóstico** e residência, sem "Erro diagnóstico"; coorte com PB de A−1 e
  MB de A−2, tirando **só** a transferência para outro estado ou país (tirar
  toda transferência, como o hansedf, põe a cura ~5 pp acima), e cura só com
  alta até 31/12 de A; grau 2 sobre os avaliados e só com GIF avaliado ≥ 75%.
  Contatos registrados vêm do `public.sinan_hans` (a silver não tem).
  População = `pop_ibge`, a mesma do MS, e em 2022 o total do Censo, como o MS.
  A coorte do último ano da série fica **em fechamento** (`ANO_EM_FECHAMENTO`).
  `indicadores()` calcula tudo de uma vez para Brasil, UFs e municípios
  (~9 s na primeira carga, depois cache). `tests/test_dados.py` confere a
  distância ao boletim.
- Dados em `data/origem/` (fora do git e da imagem; o compose monta `./data`).
  As malhas (`geo/municipios.parquet` do tbbrasil, `geo/ufs.parquet` do sinan)
  e a bandeira são versionadas.
- **`src/doencas/`**: registro com `CONTRATO`; o pack é só constantes e
  consultas. Cor é por métrica.
- **Casca = a do hansepe** (a família de TB e hanseníase se reconhece por
  ela). `src/theme/` é cópia do `src/theme/` do hansepe (tokens, cores,
  componentes); `src/estilo.py` é a ponte — `cabecalho`, `card`,
  `titulo_bloco`… desenhando com as peças de lá. Painéis por
  `st.container(border=True, key="cartao-…")`, cards em `key="faixa-kpis"`,
  ícone de cada card no pack (`ICONES_KPI`). Só modo claro.
- O clique no mapa e no ranking é lido **no topo do script**, antes de
  desenhar, com nonce em `session_state` (`_clicou` no `app.py`).

## Regras

- Não importe o `app.py` em teste: use o `AppTest` (`tests/test_aplicacao.py`).
  E confira ausência de **aviso**, não só de exceção — `resiliencia.painel`
  engole falha de bloco.
- Capture `Exception`, nunca `BaseException` (`st.rerun()` atravessa por ela).
- O que o painel desenha diferente do core entra por **parâmetro** do core,
  nunca por cópia do código dele. Faltou parâmetro: é versão nova do core.
