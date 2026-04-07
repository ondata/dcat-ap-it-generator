import logging
import os
from datetime import datetime
from urllib.parse import quote

import yaml
from rdflib import Graph, Literal, URIRef, BNode
from rdflib.namespace import RDF, XSD

from dcat_ap_it_generator.namespaces import (
    BINDINGS, DCAT, DCATAPIT, DCT, EU_DATA_THEME,
    EU_FILE_TYPE, EU_FREQUENCY, EU_LANGUAGE, FOAF, VCARD,
)

log = logging.getLogger(__name__)

_LICENSES: dict[str, str] = {}
_LICENSE_IDS: dict[str, str] = {}


def _load_licenses() -> tuple[dict[str, str], dict[str, str]]:
    global _LICENSES, _LICENSE_IDS
    if _LICENSES:
        return _LICENSES, _LICENSE_IDS
    path = os.path.join(os.path.dirname(__file__), "licenses.yml")
    with open(path) as f:
        data = yaml.safe_load(f)
    _LICENSES = data.get("licenses", {})
    _LICENSE_IDS = data.get("license_ids", {})
    return _LICENSES, _LICENSE_IDS


# Mapping valori frequenza CKAN → codici EU Vocabularies
_FREQUENCY_MAP = {
    "DAILY": "DAILY",
    "WEEKLY": "WEEKLY",
    "BIWEEKLY": "BIWEEKLY",
    "MONTHLY": "MONTHLY",
    "QUARTERLY": "QUARTERLY",
    "BIANNUAL": "BIANNUAL",
    "ANNUAL": "ANNUAL",
    "IRREG": "IRREG",
    "UNKNOWN": "UNKNOWN",
    "OTHER": "OTHER",
    "NEVER": "NEVER",
    "CONT": "CONT",
    "UPDATE_CONT": "UPDATE_CONT",
    "HOURLY": "HOURLY",
}


def _get_extra(dataset: dict, key: str) -> str | None:
    """Estrae il valore di un extra field dal dataset CKAN."""
    for item in dataset.get("extras") or []:
        if isinstance(item, dict) and item.get("key") == key:
            return item.get("value")
    return None


def theme_uris(dataset: dict) -> list[URIRef]:
    """Restituisce URI dcat:theme dal campo extra 'theme' (JSON array di codici EU)."""
    import json as _json
    raw = _get_extra(dataset, "theme")
    if not raw:
        return []
    try:
        codes = _json.loads(raw)
    except (ValueError, TypeError):
        return []
    uris = []
    for code in codes:
        if isinstance(code, str):
            # Già URI completa
            if code.startswith("http"):
                uris.append(URIRef(code))
            else:
                uris.append(EU_DATA_THEME[code.upper()])
    return uris


def frequency_uri(ckan_value: str | None) -> URIRef | None:
    if not ckan_value:
        return None
    code = _FREQUENCY_MAP.get(ckan_value.upper())
    if code:
        return EU_FREQUENCY[code]
    return None


def language_uri(ckan_value: str | None) -> URIRef | None:
    """Converte es. 'ITA', '{ITA,DEU}', 'it' in URI EU language per il primo valore."""
    if not ckan_value:
        return None
    # Strip braces e prendi solo il primo
    raw = ckan_value.strip("{}")
    first = raw.split(",")[0].strip().upper()
    if not first:
        return None
    # Normalizza codici a 2 lettere → 3 lettere comuni
    _ISO2_TO_3 = {"IT": "ITA", "EN": "ENG", "DE": "DEU", "FR": "FRA", "ES": "SPA"}
    if len(first) == 2:
        first = _ISO2_TO_3.get(first, first)
    return EU_LANGUAGE[first]


def license_uri(ckan_title: str | None) -> URIRef | None:
    if not ckan_title:
        return None
    licenses, _ = _load_licenses()
    uri = licenses.get(ckan_title)
    if uri:
        return URIRef(uri)
    return None


def license_id_uri(ckan_id: str | None) -> URIRef | None:
    if not ckan_id:
        return None
    _, license_ids = _load_licenses()
    uri = license_ids.get(ckan_id.lower())
    if uri:
        return URIRef(uri)
    return None


def format_uri(ckan_format: str | None) -> URIRef | None:
    if not ckan_format:
        return None
    return EU_FILE_TYPE[ckan_format.upper().replace(" ", "_")]


def _literal_date(value: str | None) -> Literal | None:
    if not value:
        return None
    # Prova vari formati
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(value, fmt)
            return Literal(dt.strftime("%Y-%m-%d"), datatype=XSD.date)
        except ValueError:
            continue
    log.debug("Data non parsabile: %s", value)
    return None


def _dataset_uri(base_url: str, dataset_id: str) -> URIRef:
    return URIRef(f"{base_url.rstrip('/')}/dataset/{quote(dataset_id)}")


def _distribution_uri(base_url: str, resource_id: str) -> URIRef:
    return URIRef(f"{base_url.rstrip('/')}/resource/{quote(resource_id)}")


def map_distribution(resource: dict, dataset_uri: URIRef, license_ref: URIRef | None, graph: Graph) -> URIRef | None:
    res_id = resource.get("id")
    if not res_id:
        return None

    base = str(dataset_uri).rsplit("/dataset/", 1)[0]
    dist_uri = _distribution_uri(base, res_id)

    graph.add((dist_uri, RDF.type, DCATAPIT.Distribution))
    graph.add((dist_uri, RDF.type, DCAT.Distribution))

    name = resource.get("name")
    if name:
        graph.add((dist_uri, DCT.title, Literal(name)))

    url = resource.get("url")
    if url:
        graph.add((dist_uri, DCAT.downloadURL, URIRef(url)))
        graph.add((dist_uri, DCAT.accessURL, URIRef(url)))

    fmt = format_uri(resource.get("format"))
    if fmt:
        graph.add((dist_uri, DCT["format"], fmt))

    size = resource.get("size")
    if size:
        try:
            graph.add((dist_uri, DCAT.byteSize, Literal(int(size), datatype=XSD.decimal)))
        except (ValueError, TypeError):
            pass

    issued = _literal_date(resource.get("created"))
    if issued:
        graph.add((dist_uri, DCT.issued, issued))

    modified = _literal_date(resource.get("last_modified"))
    if modified:
        graph.add((dist_uri, DCT.modified, modified))

    if license_ref:
        graph.add((dist_uri, DCT.license, license_ref))

    # Collega dataset → distribution
    graph.add((dataset_uri, DCAT.distribution, dist_uri))

    return dist_uri


def _add_agent(graph: Graph, name: str, identifier: str | None = None) -> BNode:
    agent = BNode()
    graph.add((agent, RDF.type, DCATAPIT.Agent))
    graph.add((agent, RDF.type, FOAF.Agent))
    graph.add((agent, FOAF.name, Literal(name)))
    if identifier:
        graph.add((agent, DCT.identifier, Literal(identifier)))
    return agent


def _add_contact_point(graph: Graph, author: str | None, maintainer: str | None) -> BNode | None:
    name = maintainer or author
    if not name:
        return None
    cp = BNode()
    graph.add((cp, RDF.type, VCARD.Kind))
    graph.add((cp, VCARD.fn, Literal(name)))
    return cp


def map_dataset(dataset: dict, base_url: str, graph: Graph) -> URIRef | None:
    ds_id = dataset.get("id")
    title = dataset.get("title")
    if not ds_id or not title:
        log.warning("Dataset senza id o title — skip: %s", ds_id)
        return None

    ds_uri = _dataset_uri(base_url, ds_id)

    graph.add((ds_uri, RDF.type, DCATAPIT.Dataset))
    graph.add((ds_uri, RDF.type, DCAT.Dataset))

    graph.add((ds_uri, DCT.identifier, Literal(ds_id)))
    graph.add((ds_uri, DCT.title, Literal(title)))

    notes = dataset.get("notes")
    if notes:
        graph.add((ds_uri, DCT.description, Literal(notes)))

    # Keywords
    for tag in dataset.get("tags") or []:
        name = tag.get("name") if isinstance(tag, dict) else tag
        if name:
            graph.add((ds_uri, DCAT.keyword, Literal(name)))

    # Landing page
    url = dataset.get("url") or f"{base_url.rstrip('/')}/dataset/{ds_id}"
    graph.add((ds_uri, DCAT.landingPage, URIRef(url)))

    # Date
    issued = _literal_date(dataset.get("issued"))
    if issued:
        graph.add((ds_uri, DCT.issued, issued))

    modified = _literal_date(dataset.get("modified"))
    if modified:
        graph.add((ds_uri, DCT.modified, modified))

    # Frequency
    freq = frequency_uri(dataset.get("frequency"))
    if freq:
        graph.add((ds_uri, DCT.accrualPeriodicity, freq))

    # Language — primo valore
    lang = language_uri(dataset.get("language"))
    if lang:
        graph.add((ds_uri, DCT.language, lang))

    # Themes (dcat:theme — EU Data Themes)
    for theme in theme_uris(dataset):
        graph.add((ds_uri, DCAT.theme, theme))

    # License — priorità: license_id → license_ids.yml, poi license_title → licenses.yml
    # Va sulle distribuzioni (DCAT-AP IT), non sul dataset
    lic = license_id_uri(dataset.get("license_id")) or license_uri(dataset.get("license_title"))

    # Publisher
    pub_name = dataset.get("publisher_name")
    if not pub_name and isinstance(dataset.get("organization"), dict):
        pub_name = dataset["organization"].get("title")
    if pub_name:
        publisher = _add_agent(graph, pub_name, dataset.get("publisher_identifier"))
        graph.add((ds_uri, DCT.publisher, publisher))

    # Rights holder
    holder_name = dataset.get("holder_name")
    if holder_name:
        holder = _add_agent(graph, holder_name, dataset.get("holder_identifier"))
        graph.add((ds_uri, DCT.rightsHolder, holder))

    # Contact point
    cp = _add_contact_point(graph, dataset.get("author"), dataset.get("maintainer"))
    if cp:
        graph.add((ds_uri, DCAT.contactPoint, cp))

    # Spatial (geographical_name)
    geo_name = dataset.get("geographical_name")
    if geo_name:
        location = BNode()
        graph.add((location, RDF.type, DCT.Location))
        graph.add((location, FOAF.name, Literal(geo_name)))
        geo_url = dataset.get("geographical_geonames_url")
        if geo_url:
            graph.add((location, DCT.identifier, URIRef(geo_url)))
        graph.add((ds_uri, DCT.spatial, location))

    # Temporal coverage
    t_start = _literal_date(dataset.get("temporal_start"))
    t_end = _literal_date(dataset.get("temporal_end"))
    if t_start or t_end:
        period = BNode()
        graph.add((period, RDF.type, DCT.PeriodOfTime))
        if t_start:
            graph.add((period, DCAT.startDate, t_start))
        if t_end:
            graph.add((period, DCAT.endDate, t_end))
        graph.add((ds_uri, DCT.temporal, period))

    # Distributions
    for resource in dataset.get("resources") or []:
        map_distribution(resource, ds_uri, lic, graph)

    return ds_uri


def build_catalog(config: dict, datasets: list[dict], base_url: str) -> Graph:
    g = Graph()

    # Namespace bindings per output leggibile
    for prefix, ns in BINDINGS.items():
        g.bind(prefix, ns)

    cat_cfg = config.get("catalog", {})
    cat_uri = URIRef(cat_cfg.get("uri", base_url))

    g.add((cat_uri, RDF.type, DCATAPIT.Catalog))
    g.add((cat_uri, RDF.type, DCAT.Catalog))

    title = cat_cfg.get("title")
    if title:
        g.add((cat_uri, DCT.title, Literal(title)))

    description = cat_cfg.get("description")
    if description:
        g.add((cat_uri, DCT.description, Literal(description)))

    issued = _literal_date(cat_cfg.get("issued"))
    if issued:
        g.add((cat_uri, DCT.issued, issued))

    lang = language_uri(cat_cfg.get("language"))
    if lang:
        g.add((cat_uri, DCT.language, lang))

    homepage = cat_cfg.get("homepage")
    if homepage:
        g.add((cat_uri, FOAF.homepage, URIRef(homepage)))

    pub_name = cat_cfg.get("publisher_name")
    pub_id = cat_cfg.get("publisher_identifier")
    if pub_name:
        publisher = _add_agent(g, pub_name, pub_id)
        g.add((cat_uri, DCT.publisher, publisher))

    for dataset in datasets:
        ds_uri = map_dataset(dataset, base_url, g)
        if ds_uri:
            g.add((cat_uri, DCAT.dataset, ds_uri))

    return g
