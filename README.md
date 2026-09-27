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

## Limites da evidência

Esta primeira etapa verifica **conformidade de estados dos mesmos pares**. O Splink pode avisar que `m/u` não foram treinados e que usa prior padrão. Essa execução **não estima independentemente `u`**, não valida o bootstrap IBGE, a calibração do motor, o prior, decisões de promoção nem segurança em produção. A investigação estatística independente está na [issue Jornada #506](https://github.com/lucianox777/Jornada/issues/506). Evitar alterações silenciosas do comparador C# V1.
