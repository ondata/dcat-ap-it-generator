# LOG

## 2026-04-12

- Feat: `portal.datastore_distributions: true` — aggiunge distribuzioni DCAT per CSV/TSV/JSON/XML da endpoint `/datastore/dump/` per ogni resource con `datastore_active=True`, saltando i formati già presenti come resource nel dataset; `dcat:accessURL` punta alla pagina resource CKAN; `dct:description` ereditata dalla resource o generata automaticamente
- Aggiunto `datastore_distributions: true` in `examples/config-messina.yml`
- Test: 63 test verdi (8 nuovi per la feature datastore)
- Bump v0.1.6

## 2026-04-10

- Feat: modalità multi-catalog (`--multi-catalog` o `portal.multi_catalog: true` in config) — genera 1 aggregator + 1 sub-catalog per organizzazione CKAN con `dct:hasPart` (PR #2, Dennis Angemi)
- Feat: `portal.multi_catalog: true` leggibile da config YAML (non solo flag CLI)
- Aggiunto `examples/config-messina.yml` con federazione abilitata
- Test: 76 test verdi

## 2026-04-09

- Fix: publisher/rightsHolder BNode deduplicati — stesso agente (name, identifier) riusa lo stesso nodo
- Fix: timezone preservato in `xsd:dateTime` — `dt.isoformat()` invece di `strftime` senza `%z`
- Fix: `validate` ora logga regole SPARQL saltate (nome + tipo eccezione) e mostra conteggio finale
- Fix: `chunk_size` ora fa streaming — accumula chunk dal generatore senza caricare tutti i dataset in memoria
- Fix: `check_portal` fallback su `package_search` quando `status_show` bloccato (403 Milano)
- Test: aggiunti `test_ckan_client.py` (HTTP mockato), `test_cli.py` (typer runner, validate), da 39 a 62 test
- Milano: 2586 dataset, 5926 distribuzioni, 156.211 triple — 0 errori, 0 warning

## 2026-04-08 (confronto con catalogo ufficiale Messina)

- Confronto sistematico `output/messina.ttl` vs `https://dati.comune.messina.it/catalog.ttl`
- Fix: lettura subtheme EuroVoc da `themes_aggregate` (non solo `theme`) — risolti 33 warning `dct:subject`
- Fix: parsing lingue multiple `{ENG,ITA}` — prima prendeva solo il primo valore
- Aggiunto: nodi `dcatapit:LicenseDocument` con nome, tipo e versione da `licenses.yml`
- Aggiunto: `dct:spatial` sul catalogo da config (`spatial:` in YAML)
- Aperta issue ComuneDiMessina/opendata#31: `dct:temporal` errato nell'ufficiale (fallback `metadata_created` + bug inversione DD/MM)
- Risultato validazione: 0 errori, 112 warning (erano 146) — tutti da dati mancanti in CKAN

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
