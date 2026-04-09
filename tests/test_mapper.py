import json
from pathlib import Path
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from dcat_ap_it_generator.mapper import build_catalog, map_dataset, frequency_uri, language_uris, license_uri
from dcat_ap_it_generator.namespaces import DCAT, DCATAPIT, DCT, EU_FREQUENCY, EU_LANGUAGE, FOAF, OWL

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = "https://dati.trentino.it"

CONFIG = {
    "portal": {"url": BASE_URL},
    "catalog": {
        "uri": f"{BASE_URL}/catalog",
        "title": "Test Catalog",
        "description": "Catalogo di test",
        "issued": "2021-01-01",
        "publisher_name": "Ente Test",
        "publisher_identifier": "test-ipa",
        "language": "ITA",
        "homepage": BASE_URL,
    },
    "output": {"path": "output/catalog.ttl"},
}


def _make_graph() -> Graph:
    from dcat_ap_it_generator.namespaces import BINDINGS
    g = Graph()
    for p, n in BINDINGS.items():
        g.bind(p, n)
    return g


# --- frequency_uri ---

def test_frequency_uri_weekly():
    assert frequency_uri("WEEKLY") == EU_FREQUENCY["WEEKLY"]

def test_frequency_uri_case_insensitive():
    assert frequency_uri("weekly") == EU_FREQUENCY["WEEKLY"]

def test_frequency_uri_none():
    assert frequency_uri(None) is None

def test_frequency_uri_unknown_value():
    assert frequency_uri("FOOBAR") is None


# --- language_uris ---

def test_language_uris_single():
    assert language_uris("ITA") == [EU_LANGUAGE["ITA"]]

def test_language_uris_multi():
    result = language_uris("{ENG,ITA}")
    assert EU_LANGUAGE["ENG"] in result
    assert EU_LANGUAGE["ITA"] in result
    assert len(result) == 2

def test_language_uris_iso2():
    assert language_uris("it") == [EU_LANGUAGE["ITA"]]

def test_language_uris_none():
    assert language_uris(None) == []

def test_language_uris_empty():
    assert language_uris("") == []


# --- license_uri ---

def test_license_uri_cc_by_40():
    uri = license_uri("Creative Commons Attribution 4.0")
    assert uri is not None
    assert "CC_BY_4_0" in str(uri)

def test_license_uri_unknown():
    assert license_uri("Some Unknown License XYZ") is None

def test_license_uri_none():
    assert license_uri(None) is None


# --- map_dataset (dataset completo da Trentino) ---

def test_map_dataset_trentino():
    with open(FIXTURES / "dataset_trentino.json") as f:
        payload = json.load(f)
    ds = payload["result"]
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)

    assert uri is not None
    assert (uri, RDF.type, DCATAPIT.Dataset) in g
    assert (uri, RDF.type, DCAT.Dataset) in g
    assert (uri, DCT.title, None) in g
    assert (uri, DCT.identifier, None) in g

def test_map_dataset_trentino_has_distribution():
    with open(FIXTURES / "dataset_trentino.json") as f:
        payload = json.load(f)
    ds = payload["result"]
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    distributions = list(g.objects(uri, DCAT.distribution))
    assert len(distributions) > 0

def test_map_dataset_trentino_has_publisher():
    with open(FIXTURES / "dataset_trentino.json") as f:
        payload = json.load(f)
    ds = payload["result"]
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    publishers = list(g.objects(uri, DCT.publisher))
    assert len(publishers) > 0


# --- map_dataset (dataset minimale — campi opzionali assenti) ---

def test_map_dataset_minimal_no_crash():
    with open(FIXTURES / "dataset_minimal.json") as f:
        ds = json.load(f)
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    assert uri is not None

def test_map_dataset_minimal_frequency_fallback_unknown():
    """Senza frequency esplicita, il mapper usa UNKNOWN come fallback OWL obbligatorio."""
    with open(FIXTURES / "dataset_minimal.json") as f:
        ds = json.load(f)
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    assert (uri, DCT.accrualPeriodicity, EU_FREQUENCY["UNKNOWN"]) in g

def test_map_dataset_minimal_issued_from_metadata_created():
    """issued cade su metadata_created quando non c'è campo issued esplicito."""
    with open(FIXTURES / "dataset_minimal.json") as f:
        ds = json.load(f)
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    issued_values = list(g.objects(uri, DCT.issued))
    assert len(issued_values) == 1
    assert str(issued_values[0]) == "2023-01-01T00:00:00"

def test_map_dataset_without_title_returns_none():
    ds = {"id": "no-title-ds", "title": None}
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    assert uri is None


# --- build_catalog ---

def test_build_catalog_is_parsable_turtle():
    with open(FIXTURES / "dataset_trentino.json") as f:
        payload = json.load(f)
    ds = payload["result"]
    g = build_catalog(CONFIG, [ds], BASE_URL)
    ttl = g.serialize(format="turtle")
    # Verifica che il Turtle sia ri-parsabile
    g2 = Graph()
    g2.parse(data=ttl, format="turtle")
    assert len(g2) > 0

def test_build_catalog_has_catalog_node():
    g = build_catalog(CONFIG, [], BASE_URL)
    cat_uri = URIRef(f"{BASE_URL}/catalog")
    assert (cat_uri, RDF.type, DCATAPIT.Catalog) in g
    assert (cat_uri, RDF.type, DCAT.Catalog) in g

def test_build_catalog_links_datasets():
    with open(FIXTURES / "dataset_trentino.json") as f:
        payload = json.load(f)
    ds = payload["result"]
    g = build_catalog(CONFIG, [ds], BASE_URL)
    cat_uri = URIRef(f"{BASE_URL}/catalog")
    linked = list(g.objects(cat_uri, DCAT.dataset))
    assert len(linked) == 1


# --- catalog spatial ---

def test_build_catalog_spatial():
    config = {**CONFIG, "catalog": {**CONFIG["catalog"], "spatial": "https://www.geonames.org/123"}}
    g = build_catalog(config, [], BASE_URL)
    cat_uri = URIRef(f"{BASE_URL}/catalog")
    spatial_nodes = list(g.objects(cat_uri, DCT.spatial))
    assert len(spatial_nodes) == 1
    geo_id = list(g.objects(spatial_nodes[0], DCATAPIT.geographicalIdentifier))
    assert len(geo_id) == 1
    assert str(geo_id[0]) == "https://www.geonames.org/123"

def test_build_catalog_no_spatial_without_config():
    g = build_catalog(CONFIG, [], BASE_URL)
    cat_uri = URIRef(f"{BASE_URL}/catalog")
    spatial_nodes = list(g.objects(cat_uri, DCT.spatial))
    assert len(spatial_nodes) == 0


# --- LicenseDocument ---

def test_license_document_emitted():
    """Quando un dataset ha licenza CC BY 4.0, il grafo deve contenere un nodo LicenseDocument."""
    ds = {
        "id": "test-lic-doc",
        "title": "Test LicenseDocument",
        "metadata_created": "2024-01-01",
        "resources": [{"id": "r1", "url": "http://example.com/data.csv", "format": "CSV"}],
        "license_id": "cc-by",
    }
    g = build_catalog(CONFIG, [ds], BASE_URL)
    lic_docs = list(g.subjects(RDF.type, DCATAPIT.LicenseDocument))
    assert len(lic_docs) >= 1
    # Deve avere foaf:name
    names = list(g.objects(lic_docs[0], FOAF.name))
    assert len(names) > 0

def test_license_document_has_version():
    ds = {
        "id": "test-lic-ver",
        "title": "Test License Version",
        "metadata_created": "2024-01-01",
        "resources": [{"id": "r1", "url": "http://example.com/data.csv", "format": "CSV"}],
        "license_id": "cc-by",
    }
    g = build_catalog(CONFIG, [ds], BASE_URL)
    lic_docs = list(g.subjects(RDF.type, DCATAPIT.LicenseDocument))
    versions = list(g.objects(lic_docs[0], OWL.versionInfo))
    assert len(versions) == 1


# --- themes_aggregate (subthemes EuroVoc) ---

def test_subject_from_themes_aggregate():
    """dct:subject deve essere estratto da themes_aggregate quando theme non ha subthemes."""
    ds = {
        "id": "test-agg",
        "title": "Test Aggregate",
        "metadata_created": "2024-01-01",
        "extras": [
            {"key": "theme", "value": '["ENVI"]'},
            {"key": "themes_aggregate", "value": '[{"theme": "ENVI", "subthemes": ["http://eurovoc.europa.eu/100242"]}]'},
        ],
        "resources": [],
    }
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    subjects = list(g.objects(uri, DCT.subject))
    assert URIRef("http://eurovoc.europa.eu/100242") in subjects

def test_subject_fallback_to_theme_with_subthemes():
    """Se themes_aggregate manca, legge subthemes dal campo theme (formato con dict)."""
    ds = {
        "id": "test-theme-sub",
        "title": "Test Theme Sub",
        "metadata_created": "2024-01-01",
        "extras": [
            {"key": "theme", "value": '[{"theme": "TRAN", "subthemes": ["http://eurovoc.europa.eu/100238"]}]'},
        ],
        "resources": [],
    }
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    subjects = list(g.objects(uri, DCT.subject))
    assert URIRef("http://eurovoc.europa.eu/100238") in subjects

def test_no_subject_without_subthemes():
    """Nessun dct:subject se theme ha solo codici semplici e niente themes_aggregate."""
    ds = {
        "id": "test-no-sub",
        "title": "Test No Sub",
        "metadata_created": "2024-01-01",
        "extras": [
            {"key": "theme", "value": '["GOVE"]'},
        ],
        "resources": [],
    }
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    subjects = list(g.objects(uri, DCT.subject))
    assert len(subjects) == 0


# --- multi-language on dataset ---

def test_dataset_multi_language():
    ds = {
        "id": "test-multi-lang",
        "title": "Test Multi Lang",
        "metadata_created": "2024-01-01",
        "extras": [
            {"key": "language", "value": "{ENG,ITA}"},
        ],
        "resources": [],
    }
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    langs = list(g.objects(uri, DCT.language))
    assert EU_LANGUAGE["ENG"] in langs
    assert EU_LANGUAGE["ITA"] in langs
    assert len(langs) == 2

def test_dataset_single_language():
    ds = {
        "id": "test-single-lang",
        "title": "Test Single Lang",
        "metadata_created": "2024-01-01",
        "extras": [
            {"key": "language", "value": "ITA"},
        ],
        "resources": [],
    }
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    langs = list(g.objects(uri, DCT.language))
    assert langs == [EU_LANGUAGE["ITA"]]


# --- contact point: solo se email presente ---

def test_no_contact_point_without_email():
    """Senza email, non deve essere emesso dcatapit:Organization (Rule 209)."""
    from dcat_ap_it_generator.namespaces import VCARD
    ds = {
        "id": "test-no-email",
        "title": "Test No Email",
        "metadata_created": "2024-01-01",
        "author": "Mario Rossi",
        "author_email": None,
        "maintainer_email": None,
        "organization": {"id": "org-1", "title": "Ente Test", "name": "ente-test"},
        "resources": [],
    }
    g = _make_graph()
    map_dataset(ds, BASE_URL, g)
    orgs = list(g.subjects(RDF.type, DCATAPIT.Organization))
    assert len(orgs) == 0

def test_contact_point_with_email():
    """Con email, il contact point deve essere emesso con vcard:hasEmail."""
    from dcat_ap_it_generator.namespaces import VCARD
    ds = {
        "id": "test-with-email",
        "title": "Test With Email",
        "metadata_created": "2024-01-01",
        "author_email": "test@example.com",
        "organization": {"id": "org-2", "title": "Ente Test", "name": "ente-test"},
        "resources": [],
    }
    g = _make_graph()
    map_dataset(ds, BASE_URL, g)
    orgs = list(g.subjects(RDF.type, DCATAPIT.Organization))
    assert len(orgs) == 1
    emails = list(g.objects(orgs[0], VCARD.hasEmail))
    assert len(emails) == 1


# --- PeriodOfTime: solo se startDate presente ---

def test_no_temporal_without_start():
    """Solo end_date senza start: non deve essere emesso dct:temporal (Rule 196)."""
    ds = {
        "id": "test-no-start",
        "title": "Test No Start",
        "metadata_created": "2024-01-01",
        "extras": [
            {"key": "temporal_coverage", "value": '[{"temporal_start": "", "temporal_end": "2024-12-31"}]'},
        ],
        "resources": [],
    }
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    periods = list(g.objects(uri, DCT.temporal))
    assert len(periods) == 0

def test_temporal_with_start_only():
    """Solo start_date: deve essere emesso dct:temporal senza endDate."""
    ds = {
        "id": "test-start-only",
        "title": "Test Start Only",
        "metadata_created": "2024-01-01",
        "extras": [
            {"key": "temporal_coverage", "value": '[{"temporal_start": "2020-01-01", "temporal_end": ""}]'},
        ],
        "resources": [],
    }
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    periods = list(g.objects(uri, DCT.temporal))
    assert len(periods) == 1


# --- Bug fix 2: dcat:theme dal campo top-level (non solo extras) ---

def test_theme_from_toplevel_field_string():
    """Bug fix: dcat:theme deve essere letto anche dal campo top-level 'theme' (stringa JSON)."""
    from dcat_ap_it_generator.namespaces import EU_DATA_THEME
    ds = {
        "id": "test-theme-toplevel",
        "title": "Test Theme Top-Level",
        "metadata_created": "2024-01-01",
        "theme": '["GOVE", "TRAN"]',
        "resources": [],
    }
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    themes = list(g.objects(uri, DCAT.theme))
    assert EU_DATA_THEME["GOVE"] in themes
    assert EU_DATA_THEME["TRAN"] in themes

def test_theme_from_toplevel_field_list():
    """Bug fix: dcat:theme deve funzionare anche quando il campo 'theme' è già una lista Python."""
    from dcat_ap_it_generator.namespaces import EU_DATA_THEME
    ds = {
        "id": "test-theme-list",
        "title": "Test Theme List",
        "metadata_created": "2024-01-01",
        "theme": ["ENVI"],
        "resources": [],
    }
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    themes = list(g.objects(uri, DCAT.theme))
    assert EU_DATA_THEME["ENVI"] in themes


# --- Bug fix 3: contact point con stessa org ma email diverse ---

def test_contact_point_same_org_different_email():
    """Bug fix: due dataset con stessa org ma email diverse devono avere contact point distinti."""
    from dcat_ap_it_generator.namespaces import VCARD
    org = {"id": "org-shared", "title": "Ente Condiviso", "name": "ente-condiviso"}
    ds1 = {
        "id": "ds-email-a",
        "title": "Dataset Email A",
        "metadata_created": "2024-01-01",
        "author_email": "a@example.com",
        "organization": org,
        "resources": [],
    }
    ds2 = {
        "id": "ds-email-b",
        "title": "Dataset Email B",
        "metadata_created": "2024-01-01",
        "author_email": "b@example.com",
        "organization": org,
        "resources": [],
    }
    g = build_catalog(CONFIG, [ds1, ds2], BASE_URL)

    orgs = list(g.subjects(RDF.type, DCATAPIT.Organization))
    assert len(orgs) == 2, f"Expected 2 contact points, got {len(orgs)}: {orgs}"

    all_emails = set()
    for org_node in orgs:
        for email in g.objects(org_node, VCARD.hasEmail):
            all_emails.add(str(email))
    assert "mailto:a@example.com" in all_emails
    assert "mailto:b@example.com" in all_emails

def test_contact_point_same_org_same_email_deduped():
    """Due dataset con stessa org e stessa email devono condividere UN SOLO contact point."""
    from dcat_ap_it_generator.namespaces import VCARD
    org = {"id": "org-shared", "title": "Ente Condiviso", "name": "ente-condiviso"}
    ds1 = {
        "id": "ds-same-a",
        "title": "Dataset Same Email A",
        "metadata_created": "2024-01-01",
        "author_email": "same@example.com",
        "organization": org,
        "resources": [],
    }
    ds2 = {
        "id": "ds-same-b",
        "title": "Dataset Same Email B",
        "metadata_created": "2024-01-01",
        "author_email": "same@example.com",
        "organization": org,
        "resources": [],
    }
    g = build_catalog(CONFIG, [ds1, ds2], BASE_URL)
    orgs = list(g.subjects(RDF.type, DCATAPIT.Organization))
    assert len(orgs) == 1, f"Expected 1 deduplicated contact point, got {len(orgs)}"


# --- Agent deduplication (publisher/rightsHolder BNode) ---

def test_publisher_bnode_deduplicated():
    """Due dataset con stesso publisher devono condividere lo stesso BNode agent."""
    ds1 = {
        "id": "ds-pub-a",
        "title": "Dataset Pub A",
        "metadata_created": "2024-01-01",
        "organization": {"id": "org-1", "title": "Ente Comune", "name": "ente-comune"},
        "publisher_name": "Ente Comune",
        "publisher_identifier": "ipa-123",
        "resources": [],
    }
    ds2 = {
        "id": "ds-pub-b",
        "title": "Dataset Pub B",
        "metadata_created": "2024-01-01",
        "organization": {"id": "org-1", "title": "Ente Comune", "name": "ente-comune"},
        "publisher_name": "Ente Comune",
        "publisher_identifier": "ipa-123",
        "resources": [],
    }
    g = build_catalog(CONFIG, [ds1, ds2], BASE_URL)

    agents = list(g.subjects(RDF.type, DCATAPIT.Agent))
    # catalog publisher + 1 shared publisher + 1 shared rightsHolder = max 3 distinct BNodes
    # but publisher == rightsHolder (same name/id) so should be 2: catalog pub + shared one
    publisher_nodes_ds1 = list(g.objects(
        URIRef(f"{BASE_URL}/dataset/ds-pub-a"), DCT.publisher
    ))
    publisher_nodes_ds2 = list(g.objects(
        URIRef(f"{BASE_URL}/dataset/ds-pub-b"), DCT.publisher
    ))
    assert len(publisher_nodes_ds1) == 1
    assert len(publisher_nodes_ds2) == 1
    assert publisher_nodes_ds1[0] == publisher_nodes_ds2[0], "Same publisher should reuse same BNode"


def test_datetime_preserves_timezone():
    """xsd:dateTime deve preservare il timezone (Z → +00:00)."""
    from dcat_ap_it_generator.mapper import _literal_date
    lit = _literal_date("2024-01-01T12:34:56Z")
    assert lit is not None
    assert "+00:00" in str(lit), f"Timezone lost: {lit}"


def test_datetime_naive_no_spurious_tz():
    """Datetime naive non deve aggiungere timezone spurio."""
    from dcat_ap_it_generator.mapper import _literal_date
    lit = _literal_date("2024-01-01T12:34:56")
    assert lit is not None
    assert str(lit) == "2024-01-01T12:34:56"


def test_different_publishers_not_deduplicated():
    """Due dataset con publisher diversi devono avere BNode distinti."""
    ds1 = {
        "id": "ds-diff-a",
        "title": "Dataset Diff A",
        "metadata_created": "2024-01-01",
        "publisher_name": "Ente Alpha",
        "publisher_identifier": "ipa-alpha",
        "resources": [],
    }
    ds2 = {
        "id": "ds-diff-b",
        "title": "Dataset Diff B",
        "metadata_created": "2024-01-01",
        "publisher_name": "Ente Beta",
        "publisher_identifier": "ipa-beta",
        "resources": [],
    }
    g = build_catalog(CONFIG, [ds1, ds2], BASE_URL)
    pub_a = list(g.objects(URIRef(f"{BASE_URL}/dataset/ds-diff-a"), DCT.publisher))
    pub_b = list(g.objects(URIRef(f"{BASE_URL}/dataset/ds-diff-b"), DCT.publisher))
    assert pub_a[0] != pub_b[0], "Different publishers should have different BNodes"
