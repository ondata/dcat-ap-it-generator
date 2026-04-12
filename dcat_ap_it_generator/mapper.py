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


_DATASTORE_FORMATS = ["CSV", "TSV", "JSON", "XML"]


def map_datastore_distributions(
    resource: dict,
    dataset_uri: URIRef,
    graph: Graph,
    existing_formats: set[str],
) -> None:
    """Aggiunge distribuzioni per i formati datastore non già presenti come resource."""
    res_id = resource.get("id")
    dataset_id = resource.get("package_id")
    if not res_id or not dataset_id:
        return

    base = str(dataset_uri).rsplit("/dataset/", 1)[0]
    access_url = URIRef(f"{base}/dataset/{quote(dataset_id)}/resource/{quote(res_id)}")

    for fmt in _DATASTORE_FORMATS:
        if fmt in existing_formats:
            continue
        dist_uri = URIRef(f"{base}/resource/{quote(res_id)}/datastore/{fmt.lower()}")
        dump_url = URIRef(f"{base}/datastore/dump/{quote(res_id)}?format={fmt.lower()}&bom=true")

        graph.add((dist_uri, RDF.type, DCATAPIT.Distribution))
        graph.add((dist_uri, RDF.type, DCAT.Distribution))
        res_name = resource.get("name") or fmt
        graph.add((dist_uri, DCT.title, Literal(f"{res_name} ({fmt})")))
        graph.add((dist_uri, DCAT.downloadURL, dump_url))
        graph.add((dist_uri, DCAT.accessURL, access_url))
        graph.add((dist_uri, DCT["format"], EU_FILE_TYPE[fmt]))

        if resource.get("license_type"):
            graph.add((dist_uri, DCT.license, URIRef(resource["license_type"])))

        graph.add((dataset_uri, DCAT.distribution, dist_uri))


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


def map_dataset(dataset: dict, base_url: str, graph: Graph, _agent_cache: dict | None = None, datastore_distributions: bool = False) -> URIRef | None:
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
    resources = dataset.get("resources") or []
    existing_formats = {r.get("format", "").upper() for r in resources}
    for resource in resources:
        map_distribution(resource, ds_uri, graph)
        if datastore_distributions and resource.get("datastore_active"):
            map_datastore_distributions(resource, ds_uri, graph, existing_formats)

    return ds_uri


def _emit_catalog_node(
    graph: Graph,
    cat_uri: URIRef,
    cat_attrs: dict,
    agent_cache: dict,
    *,
    modified_date: Literal,
) -> None:
    """Emette su `cat_uri` tutti gli attributi comuni a un dcatapit:Catalog.

    Riusato sia per il catalogo singolo (`build_catalog`) sia per
    aggregator e sub-catalog in `build_catalog_multi`. Non lega dataset
    né dct:hasPart: quelli sono responsabilità del chiamante.

    `cat_attrs` accetta le stesse chiavi della sezione `catalog` del config:
    title, description, issued, language, homepage, publisher_name,
    publisher_identifier, spatial.
    """
    graph.add((cat_uri, RDF.type, DCATAPIT.Catalog))
    graph.add((cat_uri, RDF.type, DCAT.Catalog))

    title = cat_attrs.get("title")
    if title:
        graph.add((cat_uri, DCT.title, Literal(title)))

    description = cat_attrs.get("description")
    if description:
        graph.add((cat_uri, DCT.description, Literal(description)))

    issued = _literal_date(cat_attrs.get("issued"))
    if issued:
        graph.add((cat_uri, DCT.issued, issued))

    # dct:modified obbligatorio — passato dal chiamante per garantire
    # coerenza tra aggregator e sub-catalog nello stesso run.
    graph.add((cat_uri, DCT.modified, modified_date))

    # dcat:themeTaxonomy obbligatorio — vocabolario EU Data Themes
    graph.add((cat_uri, DCAT.themeTaxonomy,
               URIRef("http://publications.europa.eu/resource/authority/data-theme")))

    for lang in language_uris(cat_attrs.get("language")):
        graph.add((cat_uri, DCT.language, lang))

    homepage = cat_attrs.get("homepage")
    if homepage:
        hp_uri = URIRef(homepage)
        # Rule 17: foaf:homepage range = foaf:Document
        graph.add((hp_uri, RDF.type, FOAF.Document))
        graph.add((cat_uri, FOAF.homepage, hp_uri))

    pub_name = cat_attrs.get("publisher_name")
    pub_id = cat_attrs.get("publisher_identifier")
    if pub_name:
        publisher = _add_agent(graph, pub_name, pub_id, _cache=agent_cache)
        graph.add((cat_uri, DCT.publisher, publisher))

    spatial = cat_attrs.get("spatial")
    if spatial:
        location = BNode()
        graph.add((location, RDF.type, DCT.Location))
        graph.add((location, DCATAPIT.geographicalIdentifier, Literal(spatial)))
        graph.add((cat_uri, DCT.spatial, location))


def _today_literal() -> Literal:
    from datetime import timezone
    return Literal(
        datetime.now(timezone.utc).strftime("%Y-%m-%d"), datatype=XSD.date
    )


def _new_graph() -> Graph:
    g = Graph()
    for prefix, ns in BINDINGS.items():
        g.bind(prefix, ns)
    return g


def build_catalog(config: dict, datasets: list[dict], base_url: str) -> Graph:
    g = _new_graph()

    cat_cfg = config.get("catalog", {})
    cat_uri = URIRef(cat_cfg.get("uri", base_url))
    datastore_dist = bool(config.get("portal", {}).get("datastore_distributions", False))

    agent_cache: dict[tuple, BNode] = {}
    _emit_catalog_node(g, cat_uri, cat_cfg, agent_cache, modified_date=_today_literal())

    for dataset in datasets:
        ds_uri = map_dataset(dataset, base_url, g, _agent_cache=agent_cache, datastore_distributions=datastore_dist)
        if ds_uri:
            g.add((cat_uri, DCAT.dataset, ds_uri))

    # LicenseDocument — emetti nodi per le licenze usate nel grafo
    _add_license_documents(g)

    return g


def _org_site(org: dict | None) -> str | None:
    """Estrae l'URL del sito istituzionale di un'organization CKAN.

    `ckanext-dcatapit` espone il campo come `site`; CKAN core e altri
    portali usano `url`. Si controllano entrambi nell'ordine.
    """
    if not org:
        return None
    for key in ("site", "url"):
        val = (org.get(key) or "").strip()
        if val.startswith(("http://", "https://")):
            return val
    return None


def _subcatalog_uri(org: dict | None, org_name: str, base_url: str) -> URIRef:
    """Calcola l'URI di un sotto-catalogo per organization.

    Preferisce il sito istituzionale dell'organization (`site` o `url`)
    quando presente e ben formato; altrimenti fallback su
    `{base_url}/catalog/{org_name}`. Normalizza rimuovendo slash finali
    per evitare le URI doppie viste in alcuni dump CKAN.
    """
    site = _org_site(org)
    if site:
        return URIRef(site.rstrip("/"))
    return URIRef(f"{base_url.rstrip('/')}/catalog/{quote(org_name)}")


def _subcatalog_attrs(
    org: dict | None,
    org_name: str,
    cat_cfg: dict,
) -> dict:
    """Costruisce gli attributi di un sotto-catalogo a partire dai
    metadati CKAN dell'organization, con fallback ai valori del config
    del catalogo principale (per garantire i campi obbligatori OWL).
    """
    title = None
    description = None
    if org:
        title = org.get("title") or org.get("display_name")
        description = org.get("description")

    return {
        "title": title or org_name,
        "description": description or cat_cfg.get("description"),
        # publisher: per default ereditiamo dal catalogo principale,
        # garantendo che dct:publisher sia sempre presente sul sub-catalog.
        # In futuro si potrebbe derivarlo da extras dell'org se disponibili.
        "publisher_name": cat_cfg.get("publisher_name"),
        "publisher_identifier": cat_cfg.get("publisher_identifier"),
        "language": cat_cfg.get("language"),
        "homepage": _org_site(org) or cat_cfg.get("homepage"),
        "spatial": cat_cfg.get("spatial"),
    }


def build_catalog_multi(
    config: dict,
    datasets_by_org: dict[str, list[dict]],
    base_url: str,
    org_metadata: dict[str, dict] | None = None,
) -> Graph:
    """Costruisce un grafo multi-catalogo: 1 aggregator + N sub-catalog.

    Args:
        datasets_by_org: mapping org_name → lista di dataset CKAN.
            Le chiavi vuote ("") raggruppano i dataset senza organization.
        org_metadata: mapping org_name → dict da `organization_show`.
            Se mancante per un'org, si ricorre ai fallback.

    Garanzie:
        - ogni dataset compare una sola volta nel grafo
        - i BNode publisher/holder sono deduplicati globalmente
        - i sub-catalog hanno tutti dct:publisher (ereditato dal config
          se l'org non lo fornisce) per soddisfare i requisiti OWL
    """
    g = _new_graph()
    cat_cfg = config.get("catalog", {})
    aggregator_uri = URIRef(cat_cfg.get("uri", base_url))
    today = _today_literal()
    agent_cache: dict[tuple, BNode] = {}
    org_metadata = org_metadata or {}
    datastore_dist = bool(config.get("portal", {}).get("datastore_distributions", False))

    # Aggregator
    _emit_catalog_node(g, aggregator_uri, cat_cfg, agent_cache, modified_date=today)

    # Pre-calcolo URIs sub-catalog (deduplicato per URI per evitare collisioni
    # quando più org puntano alla stessa org.url)
    subcat_uris: dict[str, URIRef] = {}
    seen_uris: set[URIRef] = set()
    for org_name in datasets_by_org:
        org = org_metadata.get(org_name)
        uri = _subcatalog_uri(org, org_name, base_url)
        # In caso di collisione (improbabile ma possibile), forziamo il fallback
        if uri in seen_uris and uri != aggregator_uri:
            uri = URIRef(f"{base_url.rstrip('/')}/catalog/{quote(org_name)}")
        seen_uris.add(uri)
        subcat_uris[org_name] = uri

    # Emit sub-catalog nodes + dct:hasPart dall'aggregator
    for org_name, sub_uri in subcat_uris.items():
        if sub_uri == aggregator_uri:
            # Edge case: l'org coincide con l'aggregator (es. config.uri ==
            # org.url). Saltiamo l'emissione del nodo separato e linkiamo
            # i dataset direttamente all'aggregator.
            continue
        org = org_metadata.get(org_name)
        attrs = _subcatalog_attrs(org, org_name, cat_cfg)
        _emit_catalog_node(g, sub_uri, attrs, agent_cache, modified_date=today)
        g.add((aggregator_uri, DCT.hasPart, sub_uri))

    # Mappa dataset una sola volta e li lega al sub-catalog corretto.
    # L'aggregator linka anche TUTTI i dataset via dcat:dataset (DCAT-AP IT
    # Rule 4: ogni Catalog deve avere dcat:dataset). Nel caso edge in cui un
    # sub-catalog coincide con l'aggregator, il link è già presente.
    for org_name, datasets in datasets_by_org.items():
        target_uri = subcat_uris[org_name]
        for dataset in datasets:
            ds_uri = map_dataset(dataset, base_url, g, _agent_cache=agent_cache, datastore_distributions=datastore_dist)
            if not ds_uri:
                continue
            g.add((target_uri, DCAT.dataset, ds_uri))
            if target_uri != aggregator_uri:
                g.add((aggregator_uri, DCAT.dataset, ds_uri))

    # LicenseDocument — emetti una sola volta a fine costruzione
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
