# Piano: DCAT-AP IT Generator

## Fasi

### Fase 1 — Scaffold

Setup struttura, dipendenze, namespace RDF, mapping licenze.

- [ ] `requirements.txt` con tutte le dipendenze
- [ ] `config.example.yml` completo e commentato
- [ ] `src/namespaces.py` — definizione prefix RDF (DCATAPIT, DCAT, DCT, ADMS, FOAF, VCARD, SKOS)
- [ ] `src/licenses.yml` — tabella `license_title` CKAN → URI EU Publications Office

**Verifica:** `python3 -c "from src.namespaces import DCATAPIT; print(DCATAPIT)"` non lancia errori.

---

### Fase 2 — CKAN Client

Fetch paginato dei dataset da API CKAN.

- [ ] `src/ckan_client.py`:
  - `fetch_all_datasets(url, query_template, rows_per_page)` → generator di dict
  - Paginazione con `start` offset fino a esaurimento risultati
  - `fetch_organization(url, org_name)` → dict organizzazione
  - Gestione errori HTTP (retry 1x, poi skip con log)

**Verifica:** `python3 -c "from src.ckan_client import fetch_all_datasets; print(next(fetch_all_datasets('https://dati.trentino.it')))"` restituisce un dict dataset.

---

### Fase 3 — Mapper

Costruzione grafo RDF da dati CKAN.

- [ ] `src/mapper.py`:
  - `build_catalog(config, datasets)` → `rdflib.Graph`
  - `map_dataset(dataset, graph)` → aggiunge triple Dataset al grafo
  - `map_distribution(resource, dataset_uri, graph)` → aggiunge triple Distribution
  - `map_agent(name, identifier)` → nodo Agent (publisher / rightsHolder)
  - `map_contact_point(author, maintainer)` → nodo vcard:Kind
  - `frequency_uri(ckan_value)` → URI EU Vocabularies o `None`
  - `language_uri(ckan_value)` → URI ISO 639-3 o `None`
  - `license_uri(ckan_title, licenses_map)` → URI EU o `None`

**Verifica:** dato il fixture `tests/fixtures/dataset_trentino.json`, il mapper produce un grafo con almeno `dct:title`, `dct:identifier`, `dcat:distribution`.

---

### Fase 4 — CLI

Entry point typer con i due comandi.

- [ ] `generate.py`:
  - Comando `generate` con `--config`, `--output`, `--verbose`, `--dry-run`, `--yes`, `--organizations`
  - Comando `configure` — wizard `questionary` che crea `config.yml`
  - Banner `pyfiglet` solo con `--verbose`
  - Progress bar `rich` durante fetch CKAN
  - Tabella riepilogativa a fine esecuzione
  - Output strutturato sull'ultima riga: `generated catalog.ttl  datasets=N distributions=M duration=Xs`
  - Exit code `1` su errore fatale, `0` su successo

**Verifica:** `python3 generate.py generate --config config.example.yml --dry-run` stampa il riepilogo senza scrivere file.

---

### Fase 5 — Test

Unit test sul mapper con fixture statiche.

- [ ] `tests/fixtures/dataset_trentino.json` — dataset reale da dati.trentino.it
- [ ] `tests/fixtures/dataset_minimal.json` — dataset con soli campi obbligatori
- [ ] `tests/test_mapper.py`:
  - Test: dataset completo → triple attese presenti
  - Test: dataset senza `frequency` → proprietà omessa (non crash)
  - Test: dataset senza `issued` → proprietà omessa
  - Test: distribution mappata correttamente
  - Test: Turtle prodotto è parsabile da `rdflib`

**Verifica:** `python3 -m pytest tests/ -v` — tutti i test passano.

---

## Dipendenze tra fasi

```
Fase 1 → Fase 2 → Fase 3 → Fase 4
                ↘          ↗
                  Fase 5
```

Fasi 2 e 3 sviluppabili in parallelo dopo Fase 1. Fase 5 sviluppabile insieme a Fase 3.

---

## Rischi

| Rischio | Mitigazione |
|---------|-------------|
| Portali CKAN con struttura extra fields non standard | Mapper usa `.get()` ovunque, mai `[]` |
| URI licenze EU non coprono tutti i `license_title` CKAN | `license_uri()` restituisce `None` → proprietà omessa, no crash |
| Portali lenti o con rate limit | Retry 1x + pausa 1s tra pagine |
| Dataset con `title` None | Skip con log warning, non crash |
