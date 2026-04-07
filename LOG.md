# LOG

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
