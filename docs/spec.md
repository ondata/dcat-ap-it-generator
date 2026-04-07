# Spec: DCAT-AP IT Generator

## Objective

Script Python che interroga un portale CKAN via API, legge i metadata dei dataset pubblicati e genera un file RDF in formato Turtle conforme al profilo italiano DCAT-AP IT (https://www.dati.gov.it/sites/default/files/2020-02/DCAT-AP_IT.owl).

**Utenti target:** PA italiane che devono produrre cataloghi di metadati conformi.

**Successo:** dato un portale CKAN configurato, lo script produce un file `.ttl` valido che contiene un `dcatapit:Catalog` con tutti i `dcatapit:Dataset` e le relative `dcatapit:Distribution`.

---

## Tech Stack

- Python 3.10+
- `requests` — chiamate HTTP alle API CKAN
- `rdflib` — costruzione e serializzazione del grafo RDF
- `PyYAML` — lettura configurazione
- `typer[all]` — CLI con argomenti/opzioni tipizzati
- `rich` — output colorato, tabelle, progress bar
- `questionary` — prompt interattivi (setup guidato)
- `pyfiglet` — banner ASCII all'avvio
- Nessun framework web, nessun ORM

---

## Commands

```
# Esecuzione normale
python3 generate.py --config config.yml

# Esecuzione con banner e feedback dettagliato
python3 generate.py --config config.yml --verbose

# Setup guidato interattivo (crea config.yml via prompt)
python3 generate.py configure

# Test
python3 -m pytest tests/

# Lint
ruff check .

# Dipendenze
pip3 install -r requirements.txt
```

---

## Project Structure

```
dcat-ap-it-generator/
├── generate.py          # Entry point CLI (typer app)
├── config.yml           # Configurazione (non committato, vedi config.example.yml)
├── config.example.yml   # Template configurazione
├── requirements.txt
├── src/
│   ├── ckan_client.py   # Fetch dati da CKAN API
│   ├── mapper.py        # Mapping CKAN → DCAT-AP IT RDF
│   └── namespaces.py    # Prefix RDF (DCATAPIT, DCAT, DCT, ADMS, ecc.)
├── tests/
│   ├── test_mapper.py
│   └── fixtures/        # JSON di esempio da API CKAN
├── docs/
│   └── spec.md
└── tmp/                 # File temporanei (non committati)
```

---

## Configuration (config.example.yml)

```yaml
portal:
  url: "https://dati.trentino.it"  # URL base portale CKAN
  api_key: ""                       # Opzionale, solo per portali privati
  rows_per_page: 100                # Dataset per richiesta paginata

catalog:
  uri: "https://dati.trentino.it/catalog"
  title: "Catalogo Open Data - PAT"
  description: "Catalogo dataset della Provincia Autonoma di Trento"
  issued: "2021-01-01"
  publisher_name: "Provincia Autonoma di Trento"
  publisher_identifier: "IPA_CODE"  # Codice IPA dell'ente
  language: "it"
  homepage: "https://dati.trentino.it"

output:
  path: "output/catalog.ttl"
```

---

## Mapping CKAN → DCAT-AP IT

### Livello Catalog (`dcatapit:Catalog`)

| Campo config YAML       | Proprietà RDF             |
|-------------------------|---------------------------|
| `catalog.uri`           | `@id` del Catalog         |
| `catalog.title`         | `dct:title`               |
| `catalog.description`   | `dct:description`         |
| `catalog.issued`        | `dct:issued`              |
| `catalog.publisher_*`   | `dct:publisher` (Agent)   |
| `catalog.language`      | `dct:language`            |
| `catalog.homepage`      | `foaf:homepage`           |
| `portal.url`            | `dcat:themeTaxonomy`      |

### Livello Dataset (`dcatapit:Dataset`)

| Campo CKAN              | Proprietà RDF                        | Note                          |
|-------------------------|--------------------------------------|-------------------------------|
| `id`                    | `dct:identifier`                     |                               |
| `title`                 | `dct:title`                          |                               |
| `notes`                 | `dct:description`                    |                               |
| `tags[].name`           | `dcat:keyword`                       |                               |
| `license_title`         | `dct:license`                        | URI da vocabolario EU         |
| `issued`                | `dct:issued`                         | extra field                   |
| `modified`              | `dct:modified`                       | extra field                   |
| `frequency`             | `dct:accrualPeriodicity`             | URI da EU Vocab frequencies   |
| `language`              | `dct:language`                       | `{ITA,DEU}` → URI ISO 639     |
| `publisher_name`        | `dct:publisher > foaf:name`          | extra field                   |
| `holder_name`           | `dct:rightsHolder > foaf:name`       | extra field                   |
| `organization.title`    | `dct:publisher` (fallback)           | se publisher_name assente     |
| `geographical_name`     | `dct:spatial`                        | extra field                   |
| `temporal_start/end`    | `dct:temporal`                       | extra field                   |
| `themes_aggregate`      | `dcat:theme`                         | URI da EU Data Themes         |
| `maintainer`/`author`   | `dcat:contactPoint`                  | vcard:Kind                    |
| `url`                   | `dcat:landingPage`                   |                               |

### Livello Distribution (`dcatapit:Distribution`)

| Campo CKAN resource     | Proprietà RDF               |
|-------------------------|-----------------------------|
| `id`                    | `dct:identifier`            |
| `name`                  | `dct:title`                 |
| `url`                   | `dcat:downloadURL`          |
| `format`                | `dct:format`                |
| `size`                  | `dcat:byteSize`             |
| `created`               | `dct:issued`                |
| `last_modified`         | `dct:modified`              |
| `license` (ereditata)   | `dct:license`               |

---

## Vocabolari controllati

Alcuni valori CKAN richiedono mapping a URI di vocabolari EU:

- **Frequenze**: `http://publications.europa.eu/resource/authority/frequency/`
  - `DAILY`, `WEEKLY`, `MONTHLY`, `ANNUAL`, `IRREG`, ecc.
- **Lingue**: `http://publications.europa.eu/resource/authority/language/`
  - `ITA`, `ENG`, `DEU`, ecc.
- **Formati**: `http://publications.europa.eu/resource/authority/file-type/`
  - `CSV`, `JSON`, `PDF`, ecc.
- **Temi EU DATA**: `http://publications.europa.eu/resource/authority/data-theme/`

---

## Testing Strategy

- Framework: `pytest`
- I test usano fixture JSON statici (nessuna chiamata live al CKAN)
- Unit test su `mapper.py`: dato un dict CKAN, verifica le triple RDF prodotte
- Un test di integrazione opzionale può fare 1 richiesta reale e verificare che il Turtle sia valido

---

## CLI Design

### Comandi

```
generate.py generate [OPTIONS]   # Comando principale (default)
generate.py configure            # Setup guidato interattivo
```

### Comando `generate`

```python
@app.command()
def generate(
    config: Path = typer.Option("config.yml", "--config", "-c", help="File YAML config"),
    output: Path = typer.Option(None, "--output", "-o", help="Override output path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Output dettagliato"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Solo fetch, non scrive file"),
):
```

**Comportamento:**
- Con `--verbose`: mostra banner ASCII + progress bar dataset per dataset
- Senza `--verbose`: output minimale (solo errori + riga finale con count)
- Con `--dry-run`: mostra tabella riepilogativa senza scrivere il file
- Sempre: progress bar per la paginazione CKAN (operazione lenta)

**Output esempio (verbose):**
```
  ____   ____    _  _____        _    ____
 |  _ \ / ___|  / \|_   _|      / \  |  _ \
 | | | | |     / _ \ | |       / _ \ | |_) |
 | |_| | |___ / ___ \| |      / ___ \|  __/
 |____/ \____/_/   \_\_|     /_/   \_\_|

Portale: https://dati.trentino.it
Fetching datasets... ████████████████████ 100% (1329/1329)

┌──────────────────────────────────────────────┐
│ Catalog generato                             │
│ Dataset:      1329                           │
│ Distribution: 2847                           │
│ Output:       output/catalog.ttl (1.2 MB)   │
└──────────────────────────────────────────────┘
✓ Fatto!
```

### Comando `configure`

Wizard interattivo che crea `config.yml` tramite `questionary`:

```
? URL portale CKAN: https://dati.trentino.it
? URI del catalogo: https://dati.trentino.it/catalog
? Titolo catalogo: Catalogo Open Data PAT
? Nome publisher: Provincia Autonoma di Trento
? Codice IPA publisher: pat
? Lingua default [it]: it
? Path output [output/catalog.ttl]: 
✓ config.yml creato
```

### Principi UX (umani)

- **Verbosità progressiva:** banner e tabelle solo con `--verbose` o `configure`
- **Scriptabile:** tutto configurabile via flag, nessun prompt in modalità non-interattiva
- **Fail gracefully:** errori su singolo dataset loggati ma non bloccano il resto; riepilogo errori a fine esecuzione
- **Progress sempre attivo:** la paginazione CKAN può richiedere minuti, la progress bar è sempre visibile

### Principi UX (agenti)

La CLI deve essere utilizzabile da agenti LLM senza intervento umano. Linee guida:

**Non-interattiva per default.** Ogni input è passabile via flag. Il wizard `configure` è solo per umani; in modalità non-interattiva tutto arriva da `--config`.

**`--help` con esempi concreti.** Ogni sottocomando espone esempi copia-incolla:

```
$ generate.py generate --help
Options:
  --config  Path file YAML config  [default: config.yml]
  --output  Override path output .ttl
  --verbose Output dettagliato
  --dry-run Solo fetch, non scrive file
  --yes     Salta conferme interattive

Examples:
  generate.py generate --config config.yml
  generate.py generate --config config.yml --output /tmp/catalog.ttl
  generate.py generate --config config.yml --dry-run
```

**Output strutturato su successo.** L'ultima riga di stdout in caso di successo è sempre parsabile:

```
generated catalog.ttl  datasets=1329 distributions=2847 duration=12s
```

In caso di errore, stderr riceve un messaggio con l'invocazione corretta:

```
Error: config file not found: config.yml
  generate.py generate --config <path-to-config>
  generate.py configure  # to create a new config interactively
```

**Fail fast.** Flag mancanti o config invalida → errore immediato con exit code != 0, mai hang su prompt.

**Idempotente.** Rieseguire lo stesso comando sovrascrive l'output senza effetti collaterali.

**`--dry-run` sempre disponibile.** Mostra cosa verrebbe generato (dataset count, output path) senza scrivere file.

**`--yes` per bypassare conferme.** Nessuna domanda interattiva se `--yes` è presente.

**Struttura comandi prevedibile.** Pattern `generate.py <verbo> [OPTIONS]`:
- `generate.py generate` — genera il Turtle
- `generate.py configure` — setup interattivo
- `generate.py validate --config config.yml` — valida la config senza generare (futuro)

---

## Boundaries

- **Always:** validare la config YAML all'avvio, loggare errori sui dataset non mappabili senza interrompere
- **Ask first:** aggiungere nuove dipendenze, modificare il mapping per casi edge non coperti dalla spec
- **Never:** richiedere autenticazione CKAN per default, modificare dati sul portale, committare file di output

---

## Success Criteria

1. Dato `config.example.yml` puntato su `dati.trentino.it`, lo script produce `catalog.ttl` senza errori
2. Il file prodotto è Turtle valido (parsabile da `rdflib`)
3. Contiene almeno un `dcatapit:Catalog`, N `dcatapit:Dataset` e le relative `dcatapit:Distribution`
4. Ogni dataset ha almeno: `dct:title`, `dct:description`, `dct:identifier`, `dct:publisher`
5. Lo script gira in cron senza input interattivo

---

## Decisions

| # | Domanda | Decisione |
|---|---------|-----------|
| 1 | Multilingua su `title`/`notes` | Solo il primo valore, nessun tag `@lang` |
| 2 | Paginazione | Tutti i dataset del portale; config opzionale `query_template` per filtrare (es. `organization:pat`) |
| 3 | Mapping licenze → URI EU | File YAML esterno `src/licenses.yml` |
| 4 | Campi non obbligatori assenti | Proprietà omessa, nessun fallback |
| 5 | Output | Un file `.ttl` unico; con `--organizations org1,org2` genera un file per organizzazione |

### Dettaglio: query_template in config

```yaml
portal:
  url: "https://dati.trentino.it"
  query_template: "organization:pat"  # opzionale, filtro CKAN fq
```

### Dettaglio: output per organizzazione

```bash
# File unico (default)
generate.py generate --config config.yml
# → output/catalog.ttl

# File per organizzazione
generate.py generate --config config.yml --organizations pat,comune-trento
# → output/pat.ttl
# → output/comune-trento.ttl
```
