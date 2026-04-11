[![PyPI version](https://img.shields.io/pypi/v/dcat-ap-it-generator)](https://pypi.org/project/dcat-ap-it-generator/)
[![GitHub](https://img.shields.io/badge/github-ondata%2Fdcat--ap--it--generator-blue?logo=github)](https://github.com/ondata/dcat-ap-it-generator)
[![deepwiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/ondata/dcat-ap-it-generator)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Newsletter](https://img.shields.io/badge/newsletter-ondata-FF6719?logo=substack)](https://ondata.substack.com/)

# DCAT-AP IT Generator

> Idea originale di [Daniele Crespi](https://www.linkedin.com/in/danielecrespi/).

Genera file RDF Turtle conformi a [DCAT-AP IT](https://www.dati.gov.it/sites/default/files/2020-02/DCAT-AP_IT.owl) interrogando qualsiasi portale CKAN via API.

## Il problema che risolve

L'approccio tradizionale per produrre metadati DCAT-AP IT da un portale CKAN richiede l'installazione e la manutenzione del plugin [`ckanext-dcatapit`](https://github.com/geosolutions-it/ckanext-dcatapit). Questo plugin:

- non è aggiornato attivamente da anni
- richiede accesso all'infrastruttura del portale
- dipende da una versione specifica di CKAN

**Questo tool funziona in modo completamente indipendente dal plugin e dall'infrastruttura del portale.** Basta che il portale esponga le API CKAN standard (disponibili su qualsiasi installazione CKAN).

## Come funziona

Lo script interroga le API pubbliche del portale CKAN, mappa i campi dei dataset verso le proprietà DCAT-AP IT e produce un file Turtle pronto per essere harvested.

```mermaid
flowchart LR
    A[Portale CKAN\nAPI pubbliche] -->|fetch + mapping| B[dcat-ap-it generate]
    B -->|RDF Turtle| C[catalog.ttl]
    C -->|harvesting| D[Catalogo\nnazionale / regionale]
```

Il file prodotto è pronto per essere harvested da qualsiasi catalogo che supporti DCAT-AP IT — che sia nazionale (es. dati.gov.it) o regionale.

Contiene:
- `dcatapit:Catalog` con i metadati del catalogo
- `dcatapit:Dataset` per ogni dataset pubblicato
- `dcatapit:Distribution` per ogni risorsa

## Installazione

```bash
# da PyPI
uv tool install dcat-ap-it-generator

# oppure con pip
pip install dcat-ap-it-generator
```

Il pacchetto include **122 regole SPARQL** allineate all'OWL DCAT-AP IT, usate dal comando `validate`. Non è necessario scaricarle separatamente. Le regole combinano quelle originali di [`daf-semantic-validator`](https://github.com/italia/daf-semantic-validator) con correzioni e integrazioni derivate dall'OWL ufficiale — vedi [`docs/rules.md`](docs/rules.md) per i dettagli.

## Vuoi testarlo subito?

Nella cartella `examples/` trovi una configurazione già pronta per il portale open data del **Comune di Messina**.

```bash
# 1. Installa il tool
uv tool install dcat-ap-it-generator

# 2. Clona il repository (per i file di esempio)
git clone https://github.com/ondata/dcat-ap-it-generator
cd dcat-ap-it-generator

# 3. Anteprima senza scrivere file
dcat-ap-it generate --config examples/config-messina.yml --dry-run

# 4. Genera il file Turtle
dcat-ap-it generate --config examples/config-messina.yml
# → output/messina.ttl
```

## Uso

```bash
# Genera il file Turtle
dcat-ap-it generate --config config.yml

# Anteprima senza scrivere file
dcat-ap-it generate --config config.yml --dry-run

# Genera un file per organizzazione
dcat-ap-it generate --config config.yml --organizations org1,org2

# Wizard interattivo per creare una nuova configurazione
dcat-ap-it configure

# Valida un file TTL contro le 122 regole DCAT-AP IT
dcat-ap-it validate output/catalog.ttl

# Solo errori (esclude warning)
dcat-ap-it validate output/catalog.ttl --errors-only
```

## Configurazione

Copia un file da `examples/` e adattalo al tuo portale:

```yaml
portal:
  url: "https://dati.comune.esempio.it"   # URL base portale CKAN
  api_key: ""                              # opzionale, per portali privati
  rows_per_page: 100                       # dataset per richiesta paginata (default: 100)
  max_datasets: 0                          # limite totale dataset; 0 = nessun limite (default: 0)
  chunk_size: 0                            # se > 0, genera N file TTL separati (es. 500 → catalog_001.ttl, _002.ttl…)
  query_template: ""                       # opzionale: filtro CKAN fq (es. "organization:nome-org")

catalog:
  uri: "https://dati.comune.esempio.it/catalog"
  title: "Catalogo Open Data"
  description: ""                          # opzionale
  issued: ""                               # opzionale, formato ISO 8601
  publisher_name: "Comune di Esempio"
  publisher_identifier: "c_xxxxx"         # codice IPA — cerca su https://indicepa.gov.it
  language: "ITA"                          # codice ISO 639-3
  homepage: ""                             # opzionale
  spatial: ""                              # opzionale, URI GeoNames (es. https://www.geonames.org/2524170)

output:
  path: "output/catalog.ttl"
```

## Uso in cron

```bash
# Ogni domenica alle 3:00
0 3 * * 0 dcat-ap-it generate --config /path/to/config.yml
```
