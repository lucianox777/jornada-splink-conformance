# Jornada × Splink — conferência externa

Runner **externo**, offline e exclusivamente sintético para confrontar estados do comparador C# da Jornada com **Splink 4.0.17 / DuckDB 1.2.2**. Este repositório é independente: **não** entra no build, deploy nem pipeline da [Jornada](https://github.com/lucianox777/Jornada). Não usar dados de cidadãos, conexões SQL ou credenciais.

## Ambiente e execução (Windows PowerShell)

A partir deste repositório:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe .\runner.py "C:\caminho\Jornada\Solution\evidence\ibge-splink" .\results
```

O runner exige, por padrão, os hashes exatos dos dois replays IBGE de 27/09/2026. Somente para **novos** insumos sintéticos, regenerados intencionalmente, usar `--allow-new-input-hashes`; preserve o hash real emitido no relatório e não confunda a nova execução com a evidência anterior.

| Arquivo de entrada | SHA-256 exigido |
| --- | --- |
| `ibge-u-todos.json` | `a5cea4f00027427190c726f92329724e6f92fc3bcd64c67f4d9f758ca4d2af64` |
| `ibge-u-feminino.json` | `da89b9a7a6594f52065e64284732f032adb3033c347ba969684161cd028f378c` |

A execução gera, para cada recorte, `.splink-result.json`, `.splink-result.summary.json` e `.splink-result.divergences.json`. O contrato de saída é `JORNADA_SPLINK_IBGE_U_REPLAY_RESULT_V1`: o programa verifica versão, referência sintética, índices consecutivos, cobertura um-para-um dos pares, estados e SHA da origem. Os 20.000 pares de referência da rodada documentada apresentaram **20 divergências TODOS** e **33 FEMININO**. São medições históricas da [evidência documentada na Jornada](https://github.com/lucianox777/Jornada/blob/master/Solution/docs/IBGE_Splink_External_Replay_20260927.md), não critérios universais para novos replays.

## Conferência pelo C# (pasta Solution da Jornada)

```powershell
dotnet run --project .\src\Jornada.Linkage.Evaluation -c Release -- --check-splink-ibge-replay .\evidence\ibge-splink\ibge-u-todos.json "C:\caminho\jornada-splink-conformance\results\ibge-u-todos.splink-result.json" "C:\caminho\jornada-splink-conformance\results\todos.diagnostic.json"
dotnet run --project .\src\Jornada.Linkage.Evaluation -c Release -- --check-splink-ibge-replay .\evidence\ibge-splink\ibge-u-feminino.json "C:\caminho\jornada-splink-conformance\results\ibge-u-feminino.splink-result.json" "C:\caminho\jornada-splink-conformance\results\feminino.diagnostic.json"
```

Os JSONs grandes de entrada e resultados **não são versionados aqui**. Preserve-os com seus hashes no acervo de evidências; `results/` está no `.gitignore`. A CI executa apenas testes sintéticos pequenos, com o Splink real fixado nas dependências.


## Estimador independente de `u` — protótipo sintético (#2)

O módulo `independent_u.py` gera novos pares por `random.Random` e amostragem ponderada das **marginais públicas fornecidas explicitamente**; não reutiliza o sorteio C# nem o replay dos mesmos pares. Classifica com Splink real e registra, por estado e seed, suporte, frequência, intervalo Wilson de 95%, SHA-256 e probabilidade analítica de colisão exata. Seeds pré-declaradas: `20261001`, `20261002`, `20261003`. A hipótese de independência prenome × sobrenome é **artificial**, não uma distribuição conjunta publicada pelo IBGE.

Formato exigido para `public-marginals.json` (o exemplo é **inteiramente fictício**, não contém frequências reais do IBGE):

```json
{
  "schema_version": "JORNADA_IBGE_PUBLIC_MARGINALS_V1",
  "reference_code": "CENSO2022_NOMES_BRASIL_V1",
  "reference_content_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "first_name_sex": "TODOS",
  "surname_sex": "TODOS",
  "first_names": [{"name": "ANA", "occurrences": 3}, {"name": "MARIA", "occurrences": 1}],
  "surnames": [{"name": "SILVA", "occurrences": 2}, {"name": "SANTOS", "occurrences": 2}]
}
```

```powershell
.\.venv\Scripts\python.exe .\independent_u.py .\public-marginals.json .\results\independent --pairs 10000
```

O documento de marginais **reais** ainda precisa ser exportado e verificado contra a referência IBGE da Jornada, preservando o hash e os recortes. Os testes da CI usam somente a pequena tabela fictícia acima. Os replays internos gerados por este protótipo têm `c_sharp_state=LOW` como **placeholder do contrato**, não são resultados do C# e não devem ser usados para medir discordância entre classificadores. Nesse modo, o runner **não gera relatórios de divergência nem suporte C#**, pois os estados C# no replay são apenas placeholders; a saída válida é exclusivamente a distribuição de estados do Splink e sua incerteza amostral. Não importar `u` no banco nem afirmar calibração independente antes de comparar com o C# usando marginais reais e tolerâncias pré-fixadas.

## Limites da evidência

Esta primeira etapa verifica **conformidade de estados dos mesmos pares**. O Splink pode avisar que `m/u` não foram treinados e que usa prior padrão. Essa execução **não estima independentemente `u`**, não valida o bootstrap IBGE, a calibração do motor, o prior, decisões de promoção nem segurança em produção. A investigação estatística independente está na [issue Jornada #506](https://github.com/lucianox777/Jornada/issues/506). Evitar alterações silenciosas do comparador C# V1.
