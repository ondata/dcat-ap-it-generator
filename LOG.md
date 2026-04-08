# LOG

## 2026-04-08

- Aggiunti `BIMONTHLY` e `ANNUAL_2` (alias → BIANNUAL) in `_FREQUENCY_MAP`
- Fix indagine fallback: nessun dataset Messina usa fallback per `modified` o `rightsHolder`
- `dct:description` su Distribution ora letta da `resource.description`
- OWL archiviato in `docs/specs/DCAT-AP_IT.owl`

## 2026-04-08 (aggiornamento)

- Analisi sistematica conformità OWL DCAT-AP IT (`docs/specs/DCAT-AP_IT.owl` salvato localmente)
- Fix obbligatori da OWL + validatore AGID (772 errori su Messina):
  - `dct:accessRights` → default PUBLIC su ogni Dataset
  - `dcat:landingPage` tipizzata come `foaf:Document` (Rule 63)
  - `dct:accrualPeriodicity` → fallback `UNKNOWN` se assente (Rule 180)
  - `dcatapit:startDate`/`dcatapit:endDate` in `PeriodOfTime` (Rule 196)
  - `dcat:contactPoint` → `dcatapit:Organization` con URI (Rule 43)
  - `dct:rightsHolder` → fallback publisher se assente
  - `dct:modified` → fallback data corrente se assente
  - `dct:spatial` → `dcatapit:geographicalIdentifier` (Literal) invece di `dct:identifier`
  - `foaf:name` agenti → tag lingua `@it`
  - Date con parte temporale → `xsd:dateTime` invece di `xsd:date`

## 2026-04-07

- Fix compliance DCAT-AP IT obbligatori: `dct:modified` su Dataset (fallback extras → metadata_modified), su Catalog (data UTC corrente), `dcat:themeTaxonomy` su Catalog
- Fix fallback extras per `issued` e `frequency` su Dataset
- Aggiunto `examples/config-milano.yml` (Comune di Milano, 2586 dataset)
- Release 0.1.0 su GitHub (ondata/dcat-ap-it-generator)
- Output Messina e Milano full compliant con requisiti obbligatori DCAT-AP IT

## 2026-04-07 (inizio)

- Inizializzato progetto con `uv init`
- Scritte spec (`docs/spec.md`) e piano (`docs/plan.md`)
- Implementate tutte e 5 le fasi:
  - **Fase 1:** scaffold — `src/namespaces.py`, `src/licenses.yml`, `config.example.yml`
  - **Fase 2:** `src/ckan_client.py` — fetch paginato CKAN con retry
  - **Fase 3:** `src/mapper.py` — mapping CKAN → DCAT-AP IT RDF (rdflib)
  - **Fase 4:** `generate.py` — CLI typer con comandi `generate` e `configure`
  - **Fase 5:** `tests/test_mapper.py` — 21 test, tutti verdi
- Verifica dry-run su `dati.trentino.it`: 1329 dataset, 6070 distribuzioni
