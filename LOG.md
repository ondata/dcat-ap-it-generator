# LOG

## 2026-04-07

- Inizializzato progetto con `uv init`
- Scritte spec (`docs/spec.md`) e piano (`docs/plan.md`)
- Implementate tutte e 5 le fasi:
  - **Fase 1:** scaffold — `src/namespaces.py`, `src/licenses.yml`, `config.example.yml`
  - **Fase 2:** `src/ckan_client.py` — fetch paginato CKAN con retry
  - **Fase 3:** `src/mapper.py` — mapping CKAN → DCAT-AP IT RDF (rdflib)
  - **Fase 4:** `generate.py` — CLI typer con comandi `generate` e `configure`
  - **Fase 5:** `tests/test_mapper.py` — 21 test, tutti verdi
- Verifica dry-run su `dati.trentino.it`: 1329 dataset, 6070 distribuzioni
