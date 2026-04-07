# DCAT-AP IT Generator

> Idea originale di [Daniele Crespi](https://www.linkedin.com/in/danielecrespi/).

> **Nota:** prodotto ancora in fase di test. L'output potrebbe non essere completamente conforme a DCAT-AP IT.

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
uv tool install git+https://github.com/ondata/dcat-ap-it-generator
```

## Vuoi testarlo subito?

Nella cartella `examples/` trovi una configurazione già pronta per il portale open data del **Comune di Messina**.

```bash
# 1. Clona il repository
git clone https://github.com/ondata/dcat-ap-it-generator
cd dcat-ap-it-generator

# 2. Installa il tool
uv tool install .

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
```

## Configurazione

Copia un file da `examples/` e adattalo al tuo portale:

```yaml
portal:
  url: "https://dati.comune.esempio.it"
  query_template: ""          # opzionale: filtro CKAN fq (es. "organization:nome-org")

catalog:
  uri: "https://dati.comune.esempio.it/catalog"
  title: "Catalogo Open Data"
  publisher_name: "Comune di Esempio"
  publisher_identifier: "c_xxxxx"   # codice IPA — cerca su https://indicepa.gov.it
  language: "ITA"

output:
  path: "output/catalog.ttl"
```

## Uso in cron

```bash
# Ogni domenica alle 3:00
0 3 * * 0 dcat-ap-it generate --config /path/to/config.yml
```
