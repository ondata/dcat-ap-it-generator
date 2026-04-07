import json
from pathlib import Path
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from dcat_ap_it_generator.mapper import build_catalog, map_dataset, frequency_uri, language_uri, license_uri
from dcat_ap_it_generator.namespaces import DCAT, DCATAPIT, DCT, EU_FREQUENCY, EU_LANGUAGE, FOAF

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


# --- language_uri ---

def test_language_uri_ita():
    assert language_uri("ITA") == EU_LANGUAGE["ITA"]

def test_language_uri_braces_takes_first():
    assert language_uri("{ITA,DEU}") == EU_LANGUAGE["ITA"]

def test_language_uri_iso2():
    assert language_uri("it") == EU_LANGUAGE["ITA"]

def test_language_uri_none():
    assert language_uri(None) is None


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

def test_map_dataset_minimal_no_frequency():
    with open(FIXTURES / "dataset_minimal.json") as f:
        ds = json.load(f)
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    assert (uri, DCT.accrualPeriodicity, None) not in g

def test_map_dataset_minimal_issued_from_metadata_created():
    """issued cade su metadata_created quando non c'è campo issued esplicito."""
    with open(FIXTURES / "dataset_minimal.json") as f:
        ds = json.load(f)
    g = _make_graph()
    uri = map_dataset(ds, BASE_URL, g)
    issued_values = list(g.objects(uri, DCT.issued))
    assert len(issued_values) == 1
    assert str(issued_values[0]) == "2023-01-01"

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
