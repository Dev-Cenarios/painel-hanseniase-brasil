# Levantamento — Hanseníase no Brasil

29/out/2026. Painel de vigilância, nascido do `modelo`.

## Decisões

- Navegação: **Brasil → UF → município**.
- Finalidade: vigilância (sem estudo acoplado).
- Tela: a do hansepe/hansedf (mesmo pack de hanseníase, cards, seções, régua de endemicidade do MS).
- Território: o do tbbrasil (malha de 5.571 municípios, ranking de boletim com UF e linha do Brasil), mais o nível UF no meio.
- Régua de conferência: Boletim Epidemiológico de Hanseníase do MS.
- Porta dev 8524, `/cenarios/hansebr`.

## Fonte: `silver.hanseniase` (cenarios_ai)

- Nacional: ~1,04 mi notificações, 27 UFs, ~2.900 municípios/ano.
- Anos completos de 2001 em diante; 2026 parcial.
- `municipio_residencia_id` (inteiro) → junta com a malha por código, não por nome.
- Dá pra seguir o MS em tudo: caso novo por ano de diagnóstico, coorte de cura PB (A−1) / MB (A−2), grau II entre casos novos, 0–14, abandono.
- Contatos **registrados** não estão na silver → `public.sinan_hans` (como no hansedf).
- `status_duplicidade` não serve pra limpar (657 mil "não informado", 176 marcadas).

Casos novos por ano de diagnóstico (silver):

| Ano | Casos novos |
|---|---|
| 2019 | 28.569 |
| 2020 | 18.338 |
| 2021 | 18.679 |
| 2022 | 20.050 |
| 2023 | 23.228 |
| 2024 | 22.663 |
| 2025 | 23.519 |

## Alternativa descartada: agregados do sinan

`sinan/data/parquet/dashboard` tem hanseníase 2010–2025 em BR/UF/MUN, mas:

- `incidence.casos_total` é **todas as entradas** (BR 2024 = 29.838); caso novo (`MODOENTR=1`) = 22.724.
- `sinan_landing` é marginal por variável: grau II, MB e 0–14 só saem sobre todas as entradas.
- Cura de 2025 ainda aberta (2.335).

Serve de conferência: casos novos batem com a silver (22.724 × 22.663 em 2024; um conta por notificação, outro por diagnóstico).

## Régua: Boletim Epidemiológico de Hanseníase do MS (nº especial, 28/jan/2026)

PDF em `data/origem/boletins/` (fora do git), lido por `scripts/extrair_boletim_ms.py` →
`data/origem/boletim_ms.parquet`: Brasil, 5 regiões e 27 UFs, 2015–2024, tabelas 3, 8–11 e 14–18
do apêndice (casos novos e taxa, 0–14, MB, GIF avaliado e grau 2 no diagnóstico, cura,
GIF avaliado na cura, contatos examinados, detecção por contatos, recidiva). Brasil 2024:
22.129 casos novos, 10,41/100 mil; 0–14 = 921 (2,19); grau 2 = 11,5%; cura = 78,0%;
contatos = 80,0%.

Como o MS conta: caso novo por **ano de diagnóstico** e residência, sem "erro diagnóstico";
cura/GIF na cura/contatos pela coorte (PB A−1, MB A−2); grau 2 sobre os avaliados.
População: estimativa IBGE/DataSUS; 2022 = Censo; **2023 usa a população de 2021**
(NT 41/2024 Cgiae). ES desde 2020 vem do e-SUS VS e entra somado ao Sinan.

Silver × boletim, com a mesma definição (caso novo, ano de diagnóstico, sem erro diagnóstico):

| | 2015 | 2019 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|
| Casos novos silver | 29.069 | 28.060 | 19.654 | 22.757 | 22.219 |
| Casos novos MS | 28.761 | 27.864 | 19.635 | 22.773 | 22.129 |
| % MB silver / MS | 69,1 / 68,9 | 78,5 / 78,4 | 81,7 / 81,2 | 82,8 / 82,4 | 82,8 / 82,2 |
| % grau 2 silver / MS | 7,5 / 7,5 | 9,8 / 9,9 | 11,4 / 11,5 | 11,2 / 11,2 | 11,1 / 11,5 |
| % GIF avaliado silver / MS | 88,7 / 87,1 | 87,7 / 85,6 | 87,6 / 85,1 | 88,2 / 85,3 | 92,8 / 88,1 |

- Casos novos: Brasil 2024 +0,4%; UFs entre −5,5% (RO) e +4,6% (DF). A silver é extração
  mais nova que a do MS (31/mai/2025), então 2015–2019 sobram ~1%.
- 0–14 e MB fecham dentro de ±3% nas UFs grandes.
- **GIF avaliado no diagnóstico sai 2–5 pp acima** (RN +20): na silver não há GIF em branco,
  só "Não avaliado"; o MS deve contar o branco fora dos avaliados. Investigar antes de usar
  como indicador; grau 2 (sobre avaliados) sai até 0,4 pp abaixo pelo mesmo motivo.
### Taxas e coortes (`python -m scripts.conferir_boletim`)

Extração nacional em `data/origem/`: `sinan_br_hans.parquet` (silver inteira, ~1 mi linhas),
`sinan_br_contatos.parquet` (`public.sinan_hans` somado por município × ano × classificação ×
entrada × alta) e `populacao_ibge_br.parquet` (`pop_ibge`, município × ano × sexo × faixa de 5 anos,
2010–2025).

Brasil, silver − MS:

| Ano | Taxa detecção | Taxa 0–14 | Cura (pp) | GIF na cura (pp) | Contatos (pp) |
|---|---|---|---|---|---|
| 2015 | +0,29 | +0,22 | +0,3 | +0,6 | +1,4 |
| 2019 | +0,27 | +0,08 | −0,7 | +0,6 | +0,3 |
| 2022 | −0,35 | +0,05 | +0,2 | +0,4 | 0,0 |
| 2023 | +0,07 | +0,03 | −2,5 | −0,2 | −1,5 |
| 2024 | +0,04 | −0,03 | −1,5 | −0,1 | −0,5 |

- **População**: o `pop_ibge` é a mesma do MS (2024: 212.583.750 → 10,41 nos dois). Só 2022
  destoa, porque o MS usou o Censo (203 mi); para fechar 2022, trocar pela população do Censo.
- **Coorte**: o que fecha com o MS é tirar **só a transferência para outro estado ou país**
  (tirar toda transferência, como no hansedf, põe a cura ~5 pp acima) e contar a cura só com
  **alta até 31/12 do ano de avaliação**. Contatos com a mesma regra.
- Nas UFs, cura fica entre −7 (RS) e +1 pp; DF, GO e RS ficam 5–7 pp abaixo. Contatos ficam
  dentro de ±3 pp, exceto PB (−7) e RS (−5). Taxa de detecção ±0,7, exceto MT (+1,8) e RO (−1,1).

## Ajustes de 9/nov/2026

- **População de 2022**: o total agora é o do Censo (SIDRA 4709, 203.080.756), como o MS.
  Brasil 2022: 9,68 contra 9,67 no boletim (antes 9,32). 0–14 e pirâmide seguem o `pop_ibge`.
- **GIF avaliado no diagnóstico**: não é campo em branco. Nem a silver nem o
  `public.sinan_hans` têm GIF vazio em 2024 (só 0, 1, 2 e 3 = não avaliado). A diferença
  cresce nos anos recentes (+1,3 pp em 2016, +2,9 em 2023, +4,7 em 2024), o que bate
  com GIF completado depois do congelamento da base do MS (31/mai/2025). Fica como está:
  a conta é a do MS, a base é que é mais nova.
- **Coorte do último ano** (2025) marcada como em fechamento: cura saía 68%, 8 pp abaixo de 2024.
