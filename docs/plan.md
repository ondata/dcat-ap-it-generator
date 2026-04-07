# Piano: DCAT-AP IT Generator

## Fasi

### Fase 1 — Scaffold ✓

Setup struttura, dipendenze, namespace RDF, mapping licenze.

- [x] `pyproject.toml` con tutte le dipendenze (gestito con `uv`)
- [x] `config.example.yml` completo e commentato (esempio reale: Comune di Messina)
- [x] `dcat_ap_it_generator/namespaces.py` — prefix RDF (DCATAPIT, DCAT, DCT, FOAF, VCARD, SKOS, EU vocabularies)
- [x] `dcat_ap_it_generator/licenses.yml` — tabella `license_title` CKAN → URI EU Publications Office

---

### Fase 2 — CKAN Client ✓

Fetch paginato dei dataset da API CKAN.

- [x] `dcat_ap_it_generator/ckan_client.py`:
  - `fetch_all_datasets(url, query_template, rows_per_page)` → generator di dict
  - `count_datasets(url, query_template)` → int (per progress bar)
  - `fetch_organization(url, org_name)` → dict organizzazione
  - Paginazione con `start` offset fino a esaurimento risultati
  - Gestione errori HTTP (retry 1x + pausa 1s, poi skip con log)

---

### Fase 3 — Mapper ✓

Costruzione grafo RDF da dati CKAN.

- [x] `dcat_ap_it_generator/mapper.py`:
  - `build_catalog(config, datasets, base_url)` → `rdflib.Graph`
  - `map_dataset(dataset, base_url, graph)` → aggiunge triple Dataset al grafo
  - `map_distribution(resource, dataset_uri, license_ref, graph)` → aggiunge triple Distribution
  - `_add_agent(graph, name, identifier)` → nodo Agent (publisher / rightsHolder)
  - `_add_contact_point(graph, author, maintainer)` → nodo vcard:Kind
  - `frequency_uri(ckan_value)` → URI EU Vocabularies o `None`
  - `language_uri(ckan_value)` → URI ISO 639-3 o `None` (gestisce `{ITA,DEU}`, prende il primo)
  - `license_uri(ckan_title)` → URI EU o `None`

---

### Fase 4 — CLI ✓

Entry point typer con i due comandi.

- [x] `dcat_ap_it_generator/cli.py`:
  - Comando `generate` con `--config`, `--output`, `--verbose`, `--dry-run`, `--yes`, `--organizations`
  - Comando `configure` — wizard `questionary` che crea `config.yml`
  - Banner `pyfiglet` solo con `--verbose`
  - Progress bar `rich` durante fetch CKAN
  - Pannello riepilogativo a fine esecuzione (solo con `--verbose`)
  - Output strutturato sull'ultima riga: `generated catalog.ttl  datasets=N distributions=M duration=Xs`
  - Exit code `1` su errore fatale, `0` su successo
  - Senza argomenti → mostra help
- [x] Installabile con `uv tool install .` → comando `dcat-ap-it`

---

### Fase 5 — Test ✓

Unit test sul mapper con fixture statiche.

- [x] `tests/fixtures/dataset_trentino.json` — dataset reale da dati.trentino.it
- [x] `tests/fixtures/dataset_minimal.json` — dataset con soli campi obbligatori
- [x] `tests/test_mapper.py` — 21 test, tutti verdi:
  - `frequency_uri`, `language_uri`, `license_uri` — casi normali, edge case, None
  - `map_dataset` con dataset completo → triple attese presenti
  - `map_dataset` con dataset minimale → nessun crash, proprietà opzionali omesse
  - `build_catalog` → Turtle parsabile, nodo Catalog presente, dataset linkati

---

## Dipendenze tra fasi

```
Fase 1 → Fase 2 → Fase 3 → Fase 4
                ↘          ↗
                  Fase 5
```

---

## Rischi affrontati

| Rischio | Soluzione adottata |
|---------|-------------------|
| Portali CKAN con extra fields non standard | Mapper usa `.get()` ovunque, mai `[]` |
| URI licenze EU non coprono tutti i `license_title` CKAN | `license_uri()` restituisce `None` → proprietà omessa |
| Portali lenti o con rate limit | Retry 1x + pausa 0.1s tra pagine |
| Dataset con `title` None | Skip con log warning |
| `DCT.format` conflicta con built-in Python | Uso `DCT["format"]` |
| `licenses.yml` non incluso nel wheel | Aggiunto `[tool.setuptools.package-data]` in `pyproject.toml` |
| `src` non riconosciuto come package installabile | Rinominato in `dcat_ap_it_generator` |
