# Regole di validazione SPARQL

## Origine

Le regole base provengono dal repository [`italia/daf-semantic-validator`](https://github.com/italia/daf-semantic-validator), un progetto del Team Digitale italiano che raccoglie query SPARQL per validare grafi RDF conformi a DCAT-AP IT.

Il file OWL ufficiale dello standard è archiviato in `docs/specs/DCAT-AP_IT.owl` ed è stato usato come riferimento per identificare proprietà obbligatorie e vincoli di cardinalità non coperti dal validator originale.

---

## Struttura della cartella `rules/`

I file sono query SPARQL (`.rq`) in formato `SELECT`. Ogni query individua le violazioni di una singola regola: se restituisce risultati, il grafo non è conforme.

Esistono tre categorie di file, distinguibili dal suffisso:

### `rule-N.rq` — regole originali (105 file)

Regole prelevate direttamente da `daf-semantic-validator` senza modifiche.

### `rule-N.new.rq` — regole corrette (13 file)

Versioni sostitutive di regole originali che contenevano errori o logica incompleta. Il suffisso `.new` indica che la regola originale è stata sostituita da questa versione corretta.

Le modifiche ricorrono in due pattern:

**1. Gestione dei blank node nei messaggi di errore**

La versione originale usava `str(?s)` per costruire il messaggio, che produce un errore SPARQL quando il soggetto è un blank node (risorsa anonima RDF). La versione corretta usa `IF(isBlank(?s),"@blank_node",str(?s))`.

Le righe commentate nei file mostrano la versione originale. Esempio in `rule-2.new.rq`:

```sparql
-- versione originale (da daf-semantic-validator):
-- BIND (concat("The agent  ",str(?s)," does not have a dct:identifier property.") AS ?Message).

-- versione corretta:
BIND (concat("The agent  ",IF(isBlank(?s),"@blank_node",str(?s))," does not have a dct:identifier property.") AS ?Message).
```

Questo pattern si ripete in 11 delle 13 regole modificate (`rule-2`, `rule-3`, `rule-21`, `rule-31`, `rule-44`, `rule-52`, `rule-53`, `rule-66`, `rule-83`, `rule-86`).

**2. Correzione del tipo RDF atteso**

`rule-43.new.rq` corregge il controllo su `dcat:contactPoint`: la versione originale verificava che il valore fosse di tipo `vcard:Kind` (classe generica), mentre lo standard DCAT-AP IT richiede specificamente `dcatapit:Organization`. La regola corretta usa:

```sparql
FILTER(!EXISTS {?o a dcatapit:Organization}).
```

`rule-163.new.rq` corregge la logica per verificare l'esistenza di almeno una `dcatapit:Distribution` nel grafo: la versione originale produceva risultati errati in presenza di grafi vuoti.

### `rule-N.added.rq` — regole aggiunte (36 file)

Regole nuove, non presenti nel validator originale, aggiunte per coprire vincoli definiti nell'OWL DCAT-AP IT ma assenti in `daf-semantic-validator`. Coprono proprietà obbligatorie e vincoli di cardinalità su classi come `Dataset`, `Distribution`, `Organization`, `PeriodOfTime`, `LicenseDocument`.

**Esempio 1 — proprietà obbligatoria mancante nel validator originale**

`rule-178.added.rq`: l'OWL definisce `dct:identifier` come proprietà obbligatoria per `dcatapit:Dataset`, ma il validator originale non la verificava. La regola aggiunta segnala ogni dataset privo di identificatore:

```sparql
# Rule_ID:178
# @title [Dataset] dct:identifier is a required property for Dataset

?s a dcatapit:Dataset.
FILTER(!EXISTS {?s dct:identifier ?identifier}).
```

**Esempio 2 — vincolo sul tipo del valore**

`rule-190.added.rq`: `dct:identifier` su `dcatapit:Agent` deve essere un letterale RDF, non un URI. La regola verifica il tipo del valore:

```sparql
# Rule_ID:190
# @title [Agent] dct:identifier should be a literal

?s a dcatapit:Agent.
?s dct:identifier ?o.
FILTER(!isLiteral(?o)).
```

**Esempio 3 — proprietà obbligatoria su classe secondaria**

`rule-196.added.rq`: `dcatapit:startDate` è obbligatoria per `dct:PeriodOfTime` (la classe usata per la copertura temporale dei dataset), ma completamente assente nel validator originale:

```sparql
# Rule_ID:196
# @title [Period of time] dcatapit:startDate is a required property for dct:PeriodOfTime

?s a dct:PeriodOfTime.
FILTER(!EXISTS {?s dcatapit:startDate ?sd}).
```

**Esempio 4 — vincolo di cardinalità massima**

`rule-213.added.rq`: `vcard:hasURL` su `dcatapit:Organization` ha cardinalità massima 1. La regola usa `GROUP BY` e `HAVING` per rilevare i casi con più valori:

```sparql
# Rule_ID:213
# @title [Organization] vcard:hasURL has maximum cardinality of 1 for Organization

?s a dcatapit:Organization.
?s vcard:hasURL ?id.
GROUP BY ?s
HAVING (COUNT(?id) > 1)
```

---

## Come vengono usate

Il comando `dcat-ap-it validate` carica tutti i file `.rq` presenti nella cartella `rules/` (inclusi `.new.rq` e `.added.rq`) ed esegue ogni query sul grafo Turtle prodotto dal comando `generate`.

```python
rule_files = sorted(f for f in rules_path.glob("*.rq"))
```

L'ordinamento numerico garantisce un output riproducibile. Non esiste distinzione di trattamento tra i tre tipi di file a runtime: vengono tutti eseguiti allo stesso modo.

---

## Riepilogo

| Tipo | Conteggio | Provenienza |
|------|-----------|-------------|
| `rule-N.rq` | 105 | `daf-semantic-validator` (originale) |
| `rule-N.new.rq` | 13 | Correzioni di regole originali |
| `rule-N.added.rq` | 36 | Regole nuove da OWL DCAT-AP IT |
| **Totale** | **154** | |
