import logging
import os
from datetime import datetime
from urllib.parse import quote

import yaml
from rdflib import Graph, Literal, URIRef, BNode
from rdflib.namespace import RDF, XSD

from dcat_ap_it_generator.namespaces import (
    BINDINGS, DCAT, DCATAPIT, DCT, EU_ACCESS_RIGHT, EU_DATA_THEME,
    EU_FILE_TYPE, EU_FREQUENCY, EU_LANGUAGE, FOAF, OWL, VCARD,
)

log = logging.getLogger(__name__)

_LICENSES: dict[str, str] = {}
_LICENSE_IDS: dict[str, str] = {}
_LICENSE_DOCS: dict[str, dict] = {}


def _load_licenses() -> tuple[dict[str, str], dict[str, str]]:
    global _LICENSES, _LICENSE_IDS, _LICENSE_DOCS
    if _LICENSES:
        return _LICENSES, _LICENSE_IDS
    path = os.path.join(os.path.dirname(__file__), "licenses.yml")
    with open(path) as f:
        data = yaml.safe_load(f)
    _LICENSES = data.get("licenses", {})
    _LICENSE_IDS = data.get("license_ids", {})
    _LICENSE_DOCS = data.get("license_documents", {})
    return _LICENSES, _LICENSE_IDS


# Mapping valori frequenza CKAN → codici EU Vocabularies
_FREQUENCY_MAP = {
    "DAILY": "DAILY",
    "WEEKLY": "WEEKLY",
    "BIWEEKLY": "BIWEEKLY",
    "MONTHLY": "MONTHLY",
    "BIMONTHLY": "BIMONTHLY",
    "QUARTERLY": "QUARTERLY",
    "BIANNUAL": "BIANNUAL",
    "ANNUAL_2": "BIANNUAL",   # alias CKAN → EU BIANNUAL (2 volte l'anno)
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
    """Restituisce URI dcat:theme dal campo extra 'theme' o dal campo top-level 'theme'."""
    import json as _json
    raw = _get_extra(dataset, "theme")
    if not raw:
        raw = dataset.get("theme")
    if not raw:
        return []
    try:
        codes = _json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return []
    uris = []
    for code in codes:
        if isinstance(code, str):
            # Formato semplice: ["GOVE", "TRAN"]
            if code.startswith("http"):
                uris.append(URIRef(code))
            else:
                uris.append(EU_DATA_THEME[code.upper()])
        elif isinstance(code, dict) and "theme" in code:
            # Formato aggregato: [{"theme": "GOVE", "subthemes": [...]}]
            theme_code = code["theme"]
            if isinstance(theme_code, str):
                if theme_code.startswith("http"):
                    uris.append(URIRef(theme_code))
                else:
                    uris.append(EU_DATA_THEME[theme_code.upper()])
    return uris


def frequency_uri(ckan_value: str | None) -> URIRef | None:
    if not ckan_value:
        return None
    code = _FREQUENCY_MAP.get(ckan_value.upper())
    if code:
        return EU_FREQUENCY[code]
    return None


def language_uris(ckan_value: str | None) -> list[URIRef]:
    """Converte es. 'ITA', '{ITA,DEU}', 'it' in lista di URI EU language."""
    if not ckan_value:
        return []
    _ISO2_TO_3 = {"IT": "ITA", "EN": "ENG", "DE": "DEU", "FR": "FRA", "ES": "SPA"}
    raw = ckan_value.strip("{}")
    result = []
    for code in raw.split(","):
        code = code.strip().upper()
        if not code:
            continue
        if len(code) == 2:
            code = _ISO2_TO_3.get(code, code)
        result.append(EU_LANGUAGE[code])
    return result


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


def _clean_str(value: str | None) -> str | None:
    """Rimuove \r e normalizza whitespace per Literal RDF."""
    if not value:
        return value
    return value.replace("\r", "")


def _literal_date(value: str | None) -> Literal | None:
    if not value:
        return None
    if "T" in value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return Literal(dt.isoformat(), datatype=XSD.dateTime)
        except ValueError:
            value = value.split("T")[0]
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


def map_distribution(resource: dict, dataset_uri: URIRef, graph: Graph) -> URIRef | None:
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

    description = _clean_str(resource.get("description"))
    if description:
        graph.add((dist_uri, DCT.description, Literal(description)))

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

    if resource.get("license_type"):
        graph.add((dist_uri, DCT.license, URIRef(resource["license_type"])))

    # Collega dataset → distribution
    graph.add((dataset_uri, DCAT.distribution, dist_uri))

    return dist_uri


def _add_agent(
    graph: Graph,
    name: str,
    identifier: str | None = None,
    _cache: dict | None = None,
) -> BNode:
    cache_key = (name, identifier)
    if _cache is not None and cache_key in _cache:
        return _cache[cache_key]
    agent = BNode()
    graph.add((agent, RDF.type, DCATAPIT.Agent))
    graph.add((agent, RDF.type, FOAF.Agent))
    graph.add((agent, FOAF.name, Literal(name, lang="it")))
    if identifier:
        graph.add((agent, DCT.identifier, Literal(identifier)))
    else:
        log.warning("Agent senza dct:identifier (obbligatorio OWL): %s", name)
    if _cache is not None:
        _cache[cache_key] = agent
    return agent


def _add_contact_point(graph: Graph, dataset: dict, base_url: str) -> URIRef | None:
    """Emette dcatapit:Organization solo se c'è un'email (vcard:hasEmail obbligatoria per OWL)."""
    email = dataset.get("maintainer_email") or dataset.get("author_email")
    if not email:
        return None
    org = dataset.get("organization")
    if not isinstance(org, dict):
        return None
    org_id = org.get("id")
    if not org_id:
        return None
    org_uri = URIRef(f"{base_url.rstrip('/')}/organization/{org_id}/{quote(email, safe='')}")
    # Se già dichiarata, non riaggiungiamo (vcard:hasEmail max cardinality = 1)
    if (org_uri, RDF.type, DCATAPIT.Organization) in graph:
        return org_uri
    graph.add((org_uri, RDF.type, DCATAPIT.Organization))
    graph.add((org_uri, RDF.type, VCARD.Organization))
    graph.add((org_uri, RDF.type, VCARD.Kind))
    name = org.get("title") or org.get("name")
    if name:
        graph.add((org_uri, VCARD.fn, Literal(name)))
    graph.add((org_uri, VCARD.hasEmail, URIRef(f"mailto:{email}")))
    graph.add((org_uri, VCARD.hasURL, URIRef(base_url.rstrip("/"))))
    return org_uri


def _subject_uris(dataset: dict) -> list[URIRef]:
    """Estrae dct:subject dai subthemes EuroVoc (themes_aggregate → theme extras)."""
    import json as _json
    # themes_aggregate ha sempre la struttura con subthemes; theme spesso no
    raw = _get_extra(dataset, "themes_aggregate")
    if not raw:
        raw = _get_extra(dataset, "theme")
    if not raw:
        raw = dataset.get("theme")
    if not raw:
        return []
    try:
        codes = _json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return []
    uris = []
    for item in codes:
        if isinstance(item, dict):
            for sub in item.get("subthemes") or []:
                if isinstance(sub, str) and sub.startswith("http"):
                    uris.append(URIRef(sub))
    return uris


def _parse_temporal_coverage(raw: str | None) -> tuple[Literal | None, Literal | None]:
    """Parsa temporal_coverage JSON array → (t_start, t_end) come Literal o None."""
    import json as _json
    if not raw:
        return None, None
    try:
        items = _json.loads(raw)
    except (ValueError, TypeError):
        return None, None
    if not items or not isinstance(items, list):
        return None, None
    first = items[0]
    if not isinstance(first, dict):
        return None, None
    return (
        _literal_date(first.get("temporal_start")),
        _literal_date(first.get("temporal_end")),
    )


def map_dataset(dataset: dict, base_url: str, graph: Graph, _agent_cache: dict | None = None) -> URIRef | None:
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

    # dct:accessRights obbligatorio OWL — default PUBLIC
    graph.add((ds_uri, DCT.accessRights, EU_ACCESS_RIGHT["PUBLIC"]))

    notes = _clean_str(dataset.get("notes"))
    if notes:
        graph.add((ds_uri, DCT.description, Literal(notes)))

    # Keywords
    for tag in dataset.get("tags") or []:
        name = tag.get("name") if isinstance(tag, dict) else tag
        if name:
            graph.add((ds_uri, DCAT.keyword, Literal(name)))

    # Landing page — obbligatoria, tipizzata foaf:Document (OWL Rule 63)
    url = dataset.get("url") or f"{base_url.rstrip('/')}/dataset/{ds_id}"
    landing = URIRef(url)
    graph.add((landing, RDF.type, FOAF.Document))
    graph.add((ds_uri, DCAT.landingPage, landing))

    # Date — top-level → extras → metadata_created (issued) / metadata_modified (modified)
    issued = _literal_date(
        dataset.get("issued") or _get_extra(dataset, "issued") or dataset.get("metadata_created")
    )
    if issued:
        graph.add((ds_uri, DCT.issued, issued))

    modified_raw = (dataset.get("modified")
                    or _get_extra(dataset, "modified")
                    or dataset.get("metadata_modified"))
    modified = _literal_date(modified_raw)
    if not modified:
        from datetime import timezone
        modified = Literal(datetime.now(timezone.utc).strftime("%Y-%m-%d"), datatype=XSD.date)
    graph.add((ds_uri, DCT.modified, modified))

    # Frequency — top-level → extras, fallback UNKNOWN (obbligatorio OWL)
    freq = frequency_uri(dataset.get("frequency") or _get_extra(dataset, "frequency"))
    if not freq:
        freq = EU_FREQUENCY["UNKNOWN"]
    graph.add((ds_uri, DCT.accrualPeriodicity, freq))

    # Language — top-level → extras
    for lang in language_uris(dataset.get("language") or _get_extra(dataset, "language")):
        graph.add((ds_uri, DCT.language, lang))

    # Themes (dcat:theme — EU Data Themes) + dct:subject dai sottotemi EuroVoc
    for theme in theme_uris(dataset):
        graph.add((ds_uri, DCAT.theme, theme))
    for subj in _subject_uris(dataset):
        graph.add((ds_uri, DCT.subject, subj))

    # Publisher — top-level → extras → organization.title
    pub_name = (dataset.get("publisher_name")
                or _get_extra(dataset, "publisher_name"))
    if not pub_name and isinstance(dataset.get("organization"), dict):
        pub_name = dataset["organization"].get("title")
    pub_id = dataset.get("publisher_identifier") or _get_extra(dataset, "publisher_identifier")
    if pub_name:
        publisher = _add_agent(graph, pub_name, pub_id, _cache=_agent_cache)
        graph.add((ds_uri, DCT.publisher, publisher))

    # Rights holder — top-level → extras, fallback publisher (obbligatorio OWL)
    holder_name = dataset.get("holder_name") or _get_extra(dataset, "holder_name")
    holder_id = dataset.get("holder_identifier") or _get_extra(dataset, "holder_identifier")
    if not holder_name:
        holder_name = pub_name
        holder_id = pub_id
    if holder_name:
        holder = _add_agent(graph, holder_name, holder_id, _cache=_agent_cache)
        graph.add((ds_uri, DCT.rightsHolder, holder))

    # Contact point — dcatapit:Organization (obbligatorio OWL Rule 43)
    cp = _add_contact_point(graph, dataset, base_url)
    if cp:
        graph.add((ds_uri, DCAT.contactPoint, cp))

    # Spatial — top-level → extras (geographical_geonames_url)
    geo_url = dataset.get("geographical_geonames_url") or _get_extra(dataset, "geographical_geonames_url")
    if geo_url:
        location = BNode()
        graph.add((location, RDF.type, DCT.Location))
        graph.add((location, DCATAPIT.geographicalIdentifier, Literal(geo_url)))
        graph.add((ds_uri, DCT.spatial, location))

    # Temporal coverage — top-level fields, poi JSON array in extras (temporal_coverage)
    t_start = _literal_date(dataset.get("temporal_start"))
    t_end = _literal_date(dataset.get("temporal_end"))
    if not t_start and not t_end:
        t_start, t_end = _parse_temporal_coverage(_get_extra(dataset, "temporal_coverage"))
    # dcatapit:startDate obbligatorio su PeriodOfTime (Rule 196) — emettiamo solo se presente
    if t_start:
        period = BNode()
        graph.add((period, RDF.type, DCT.PeriodOfTime))
        graph.add((period, DCAT.startDate, t_start))
        graph.add((period, DCATAPIT.startDate, t_start))
        if t_end:
            graph.add((period, DCAT.endDate, t_end))
            graph.add((period, DCATAPIT.endDate, t_end))
        graph.add((ds_uri, DCT.temporal, period))

    # License sul dataset
    lic = license_id_uri(dataset.get("license_id")) or license_uri(dataset.get("license_title"))
    if lic:
        graph.add((ds_uri, DCT.license, lic))

    # Distributions
    for resource in dataset.get("resources") or []:
        map_distribution(resource, ds_uri, graph)

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

    # dct:modified obbligatorio — data di generazione
    from datetime import timezone
    g.add((cat_uri, DCT.modified, Literal(
        datetime.now(timezone.utc).strftime("%Y-%m-%d"), datatype=XSD.date
    )))

    # dcat:themeTaxonomy obbligatorio — vocabolario EU Data Themes
    g.add((cat_uri, DCAT.themeTaxonomy,
           URIRef("http://publications.europa.eu/resource/authority/data-theme")))

    for lang in language_uris(cat_cfg.get("language")):
        g.add((cat_uri, DCT.language, lang))

    homepage = cat_cfg.get("homepage")
    if homepage:
        g.add((cat_uri, FOAF.homepage, URIRef(homepage)))

    agent_cache: dict[tuple, BNode] = {}

    pub_name = cat_cfg.get("publisher_name")
    pub_id = cat_cfg.get("publisher_identifier")
    if pub_name:
        publisher = _add_agent(g, pub_name, pub_id, _cache=agent_cache)
        g.add((cat_uri, DCT.publisher, publisher))

    # Spatial — dal config
    spatial = cat_cfg.get("spatial")
    if spatial:
        location = BNode()
        g.add((location, RDF.type, DCT.Location))
        g.add((location, DCATAPIT.geographicalIdentifier, Literal(spatial)))
        g.add((cat_uri, DCT.spatial, location))

    for dataset in datasets:
        ds_uri = map_dataset(dataset, base_url, g, _agent_cache=agent_cache)
        if ds_uri:
            g.add((cat_uri, DCAT.dataset, ds_uri))

    # LicenseDocument — emetti nodi per le licenze usate nel grafo
    _add_license_documents(g)

    return g


def _add_license_documents(graph: Graph) -> None:
    """Aggiunge nodi dcatapit:LicenseDocument per ogni licenza usata nel grafo."""
    _load_licenses()
    license_uris = set(graph.objects(predicate=DCT.license))
    for lic_uri in license_uris:
        uri_str = str(lic_uri)
        doc = _LICENSE_DOCS.get(uri_str)
        if not doc:
            continue
        graph.add((lic_uri, RDF.type, DCATAPIT.LicenseDocument))
        graph.add((lic_uri, RDF.type, DCT.LicenseDocument))
        if doc.get("name_it"):
            graph.add((lic_uri, FOAF.name, Literal(doc["name_it"], lang="it")))
        if doc.get("name_en"):
            graph.add((lic_uri, FOAF.name, Literal(doc["name_en"], lang="en")))
        if doc.get("type"):
            graph.add((lic_uri, DCT.type, URIRef(doc["type"])))
        if doc.get("version"):
            graph.add((lic_uri, OWL.versionInfo, Literal(doc["version"])))
