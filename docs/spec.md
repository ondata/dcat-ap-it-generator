# Spec: DCAT-AP IT Generator

Tool Python che interroga un portale CKAN via API, legge i metadati dei dataset e genera un file RDF in formato Turtle conforme al profilo italiano DCAT-AP IT (https://www.dati.gov.it/sites/default/files/2020-02/DCAT-AP_IT.owl).

**Utenti target:** PA italiane che devono produrre cataloghi di metadati conformi.

**Successo:** data una config puntata su un portale CKAN, il tool produce un `.ttl` che contiene un `dcatapit:Catalog` con tutti i `dcatapit:Dataset` e le relative `dcatapit:Distribution`, pronto per essere harvested.

---

## Architettura

Pipeline: **CLI → ckan client → mapper → grafo RDF → file Turtle**

```
Portale CKAN API  →  dcat-ap-it generate  →  catalog.ttl  →  harvesting nazionale/regionale
```

## Tech Stack

- Python **≥ 3.13** (usa `int | None`, `match`)
- `requests` — chiamate HTTP alle API CKAN
- `rdflib` — costruzione e serializzazione del grafo RDF
- `PyYAML` — lettura configurazione
- `typer[all]` — CLI con opzioni tipizzate
- `rich` — output colorato e progress bar
- `questionary` — prompt interattivi (comando `configure`)
- `pyfiglet` — banner ASCII con `--verbose`
- Gestione dipendenze/package: **uv** (`pyproject.toml`, `uv.lock`); `uv tool install .` → comando `dcat-ap-it`

Riferimento OWL archiviato in `docs/specs/DCAT-AP_IT.owl`.

---

## Comandi

```
uv run dcat-ap-it generate --config config.yml           # Genera il file Turtle
uv run dcat-ap-it generate --config config.yml --dry-run # Anteprima senza scrivere
uv run dcat-ap-it configure                               # Wizard interattivo (solo umani)
uv run dcat-ap-it validate output/catalog.ttl             # Valida contro le 122 regole SPARQL
uv run dcat-ap-it validate output/catalog.ttl --errors-only
```

### `generate` — opzioni

| Opzione | Default | Effetto |
|---|---|---|
| `--config` / `-c` | `config.yml` | File YAML config |
| `--output` / `-o` | dal config | Override path output |
| `--verbose` / `-v` | off | Banner ASCII + pannello riepilogativo |
| `--dry-run` | off | Solo fetch, non scrive file |
| `--yes` / `-y` | off | Salta conferme interattive |
| `--organizations` | — | Filtra per org (comma-separated), un file per org |
| `--multi-catalog` | off | 1 aggregator + 1 sub-catalog per organization (`dct:hasPart`) |

### `validate` — opzioni

| Opzione | Default | Effetto |
|---|---|---|
| `input` (arg posizionale) | — | File TTL da validare |
| `--rules-dir` | built-in | Directory regole SPARQL |
| `--errors-only` / `-e` | off | Mostra solo errori, non warning |

---

## Struttura del progetto

```
dcat-ap-it-generator/
├── pyproject.toml           # Dipendenze, entry point, config test/ruff
├── uv.lock                  # Lock delle dipendenze
├── dcat_ap_it_generator/
│   ├── cli.py               # App typer: generate, configure, validate
│   ├── ckan_client.py       # Fetch paginato API CKAN + retry
│   ├── mapper.py            # Mapping CKAN → DCAT-AP IT RDF (rdflib)
│   ├── namespaces.py        # Namespace RDF + BINDINGS
│   ├── licenses.yml         # Titoli licenze CKAN → URI EU Office
│   └── rules/               # 122 regole SPARQL (.rq; *.suspended saltate)
├── tests/                   # pytest (99 test), fixture statiche in tests/fixtures/
├── examples/                # Config reali: messina, milano, umbria, matera, olbia
├── docs/                    # spec.md, plan.md, rules.md, release.md, specs/
└── output/                  # TTL generati (gitignorato)
```

---

## Configurazione

```yaml
portal:
  url: "https://dati.comune.esempio.it"   # URL base portale CKAN
  api_key: ""                             # Opzionale, portali privati
  rows_per_page: 100                      # Dataset per richiesta paginata
  max_datasets: 0                         # 0 = nessun limite
  chunk_size: 0                           # se > 0, genera N file TTL separati (_001, _002…)
  query_template: ""                      # Filtro CKAN fq (es. "organization:nome-org")
  multi_catalog: false                    # Genera aggregator + sub-catalog per org
  datastore_distributions: false          # Distribuzioni CSV/TSV/JSON/XML da endpoint /datastore/dump/

catalog:
  uri: "https://dati.comune.esempio.it/catalog"
  title: "Catalogo Open Data"
  description: ""                         # Opzionale
  issued: ""                              # Opzionale, ISO 8601
  publisher_name: "Comune di Esempio"
  publisher_identifier: "c_xxxxx"        # Codice IPA — https://indicepa.gov.it
  language: "ITA"                         # Codice ISO 639-3
  homepage: ""                            # Opzionale
  spatial: ""                             # Opzionale, URI GeoNames (es. https://www.geonames.org/2524170)

output:
  path: "output/catalog.ttl"
```

`multi_catalog` e `datastore_distributions` sono leggibili anche come flag CLI (`--multi-catalog`) o dalla config YAML.

---

## Mapping CKAN → DCAT-AP IT

### Livello Catalog (`dcatapit:Catalog`)

| Fonte | Proprietà | Note |
|---|---|---|
| `catalog.uri` | soggetto del Catalog | |
| `catalog.title` | `dct:title` | |
| `catalog.description` | `dct:description` | |
| `catalog.issued` | `dct:issued` | |
| `catalog.publisher_*` | `dct:publisher` | `dcatapit:Organization` |
| `catalog.language` | `dct:language` | |
| `catalog.homepage` | `foaf:homepage` | |
| `catalog.spatial` | `dct:spatial` | |
| — | `dcat:themeTaxonomy` | sempre presente |
| (multi-catalog) | `dct:hasPart` | sub-catalog per organizzazione |

### Livello Dataset (`dcatapit:Dataset`)

| Campo CKAN | Proprietà RDF | Note |
|---|---|---|
| `id` | `dct:identifier` | |
| `title` | `dct:title` | |
| `notes` | `dct:description` | |
| `tags[].name` | `dcat:keyword` | |
| `license_title` | `dct:license` | URI da `licenses.yml` |
| `issued` | `dct:issued` | extra field |
| `modified` | `dct:modified` | fallback: data corrente |
| `frequency` | `dct:accrualPeriodicity` | URI EU vocabulary |
| `language` | `dct:language` | anche `{ITA,DEU}` → URI ISO 639 |
| `publisher_name` | `dct:publisher` | `dcatapit:Organization` |
| `holder_name` | `dct:rightsHolder` | fallback: publisher |
| — | `dct:accessRights` | default PUBLIC |
| `geographical_name` | `dct:spatial` | extra field |
| `temporal_start/end` | `dct:temporal` | `PeriodOfTime` con start/end |
| `themes_aggregate` | `dcat:theme` | URI EU Data Themes |
| `maintainer`/`author` | `dcat:contactPoint` | `dcatapit:Organization` solo con email valida |
| `url` | `dcat:landingPage` | fallback: pagina dataset |

### Livello Distribution (`dcatapit:Distribution`)

| Campo CKAN resource | Proprietà RDF | Note |
|---|---|---|
| `id` | `dct:identifier` | |
| `name` | `dct:title` | |
| `description` | `dct:description` | |
| `url` | `dcat:downloadURL` + `dcat:accessURL` | `accessURL` obbligatoria: fallback pagina resource |
| `format` | `dct:format` | URI EU file-type |
| `size` | `dcat:byteSize` | |
| `created` | `dct:issued` | |
| `last_modified` | `dct:modified` | |
| `license` | `dct:license` | |
| (datastore) | distribuzioni CSV/TSV/JSON/XML | da `/datastore/dump/` per `datastore_active=True` |

### Nodi aggiuntivi

- `dcatapit:Organization` per publisher/rightsHolder/contactPoint, con `foaf:name` taggato `@it` e dedup per (name, identifier)
- `dcatapit:LicenseDocument` per ogni licenza usata nel grafo (nome, tipo, versione)

---

## Vocabolari controllati

Valori CKAN → URI EU negli `EU_*` di `namespaces.py`:

- **Frequenze**: `…/authority/frequency/` — DAILY, WEEKLY, MONTHLY, ANNUAL, IRREG, ecc.
- **Lingue**: `…/authority/language/` — ITA, ENG, DEU, ecc.
- **Formati**: `…/authority/file-type/` — CSV, JSON, PDF, ecc.
- **Temi**: `…/authority/data-theme/`
- **Access right**: `…/authority/access-right/`

---

## Fallback OWL-required

Diverse regole OWL DCAT-AP IT impongono proprietà che i portali CKAN spesso non forniscono. Il mapper le garantisce in modo silenzioso:

| Proprietà | Fallback |
|---|---|
| `dct:accessRights` | `PUBLIC` su ogni Dataset |
| `dct:accrualPeriodicity` | `UNKNOWN` se assente |
| `dct:modified` | data corrente se assente |
| `dct:rightsHolder` | publisher se assente |
| `dcat:landingPage` | pagina del dataset (mai scartata) |
| `dcat:accessURL` | pagina CKAN della resource |
| `dcat:contactPoint` | emesso solo con email valida (`vcard:hasEmail` obbligatoria) |
| URI non valide | normalizzazione percent-encoding, altrimenti scarto con warning (`_safe_uri`) |

## Robustezza

- **URI non validi** (`_safe_uri`): valida col predicato usato dal serializzatore rdflib, tenta percent-encoding dei caratteri illegali, in ultima istanza scarta il valore con warning per dataset/risorsa
- **Scrittura atomica del TTL** (`_serialize_atomic`): serializza su file temporaneo univoco (`mkstemp`) e `os.replace()` a esito positivo; su errore il file preesistente resta intatto
- Dataset con `title` `None` → skip con warning; i portali lenti hanno retry 1x + pausa tra pagine
- Nomi namespace usati via `DCT["format"]` per evitare conflitti con built-in

---

## Testing Strategy

- `pytest` (99 test verdi): `uv run pytest`
- Fixture statiche in `tests/fixtures/` (risposte reali CKAN), nessuna rete nei test
- `ruff` come lint: `uv run ruff check .` (config in `pyproject.toml`)
- Verifica end-to-end sui portali reali (Trentino, Messina, Milano, Umbria) documentata in `LOG.md`

---

## UX dei comandi (umani e agenti)

- **Non-interattiva per default**: ogni input passabile via flag; `configure` solo per umani
- **`--help` con esempi copia-incolla** su ogni sotto-comando
- **Output strutturato su successo**: l'ultima riga di stdout è sempre parsable — `generated catalog.ttl datasets=N distributions=M duration=Xs`
- **Fail fast**: flag/config errata → errore immediato, exit code ≠ 0
- **Idempotente**: rieseguire sovrascrive l'output senza effetti collaterali
- **`--dry-run` sempre disponibile**: mostra cosa verrebbe generato senza scrivere
- **`--yes`** bypassa le conferme; niente prompt in modalità non-interattiva
- Errori su singolo dataset loggati ma non bloccano il resto

---

## Boundaries

- **Always:** validare la config YAML all'avvio, loggare gli errori sui dataset non mappabili senza interrompere, scrittura atomica
- **Ask first:** aggiungere dipendenze, modificare mapping per casi edge non coperti
- **Never:** richiedere autenticazione CKAN per default, modificare dati sul portale, committare file di output

---

## Success Criteria

1. Data una config puntata su un portale CKAN, genera `.ttl` senza errori fatali
2. Il file prodotto è Turtle valido (parsabile da `rdflib`)
3. Contiene un `dcatapit:Catalog`, N `dcatapit:Dataset` e le relative `dcatapit:Distribution`
4. Ogni dataset ha almeno `dct:title`, `dct:description`, `dct:identifier`, `dct:publisher`
5. Gira in cron senza input interattivo (`--yes`/`--dry-run` disponibili)

---

## Decisions

| # | Domanda | Decisione |
|---|---------|-----------|
| 1 | Multilingua su `title`/`notes` | Solo il primo valore, nessun tag `@lang` |
| 2 | Paginazione | Tutti i dataset del portale; `query_template` per filtrare |
| 3 | Mapping licenze → URI EU | File YAML esterno `licenses.yml` |
| 4 | Campi obbligatori OWL assenti | Fallback deciso per proprietà (vedi tabella sopra), non scarto uniforme |
| 5 | URI non valide | Normalizzare poi scartare; `mailto:` esclusi dalla normalizzazione |
| 6 | Output | File `.ttl` unico; `--organizations` per org; `chunk_size` e `multi_catalog` in config |
| 7 | Distribuzioni datastore | Aggiunte per `datastore_active=True` saltando formati già presenti |
| 8 | Scrittura | Atomica, per non pubblicare mai un TTL troncato |

---

## Riferimenti

- OWL DCAT-AP IT: `docs/specs/DCAT-AP_IT.owl` (archivio locale)
- Regole SPARQL: `dcat_ap_it_generator/rules/` — dettagli in `docs/rules.md`
- Validatore ufficiale AgID: https://www.dati.gov.it/sviluppatori/validatore
