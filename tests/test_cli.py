"""Test per cli.py con typer CliRunner."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from dcat_ap_it_generator.cli import app

runner = CliRunner()

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = "https://dati.trentino.it"

_CONFIG = {
    "portal": {"url": BASE_URL, "rows_per_page": 100},
    "catalog": {
        "uri": f"{BASE_URL}/catalog",
        "title": "Test",
        "publisher_name": "Ente",
        "language": "ITA",
    },
    "output": {"path": "output/catalog.ttl"},
}


def _write_config(tmp_path: Path, cfg: dict | None = None) -> Path:
    config_path = tmp_path / "config.yml"
    import yaml
    config_path.write_text(yaml.dump(cfg or _CONFIG))
    return config_path


# --- generate: dry-run ---

@patch("dcat_ap_it_generator.ckan_client.check_portal", return_value=(True, "CKAN 2.10"))
@patch("dcat_ap_it_generator.ckan_client.count_datasets", return_value=1)
@patch("dcat_ap_it_generator.ckan_client.fetch_all_datasets")
def test_generate_dry_run(mock_fetch, mock_count, mock_check, tmp_path):
    with open(FIXTURES / "dataset_minimal.json") as f:
        ds = json.load(f)
    mock_fetch.return_value = iter([ds])

    config_path = _write_config(tmp_path)
    result = runner.invoke(app, ["generate", "--config", str(config_path), "--dry-run"])
    # dry-run esce con codice 0
    assert result.exit_code == 0


# --- generate: config mancante ---

def test_generate_missing_config(tmp_path):
    result = runner.invoke(app, ["generate", "--config", str(tmp_path / "nope.yml")])
    assert result.exit_code == 1


# --- generate: config senza portal.url ---

def test_generate_invalid_config(tmp_path):
    config_path = _write_config(tmp_path, {"portal": {}, "catalog": {"uri": "x"}})
    result = runner.invoke(app, ["generate", "--config", str(config_path)])
    assert result.exit_code == 1


# --- generate: portale non raggiungibile ---

@patch("dcat_ap_it_generator.ckan_client.check_portal", return_value=(False, "refused"))
def test_generate_portal_unreachable(mock_check, tmp_path):
    config_path = _write_config(tmp_path)
    result = runner.invoke(app, ["generate", "--config", str(config_path)])
    assert result.exit_code == 1


# --- generate: --multi-catalog ---

@patch("dcat_ap_it_generator.ckan_client.check_portal", return_value=(True, "CKAN 2.10"))
@patch("dcat_ap_it_generator.ckan_client.count_datasets", return_value=2)
@patch("dcat_ap_it_generator.ckan_client.fetch_all_organizations")
@patch("dcat_ap_it_generator.ckan_client.fetch_all_datasets")
def test_generate_multi_catalog(mock_fetch, mock_orgs, mock_count, mock_check, tmp_path):
    ds1 = {
        "id": "ds-a", "title": "DS A", "metadata_created": "2024-01-01",
        "organization": {"id": "o1", "name": "atm", "title": "ATM"},
        "resources": [],
    }
    ds2 = {
        "id": "ds-b", "title": "DS B", "metadata_created": "2024-01-01",
        "organization": {"id": "o2", "name": "camcom", "title": "CamCom"},
        "resources": [],
    }
    mock_fetch.return_value = iter([ds1, ds2])
    mock_orgs.return_value = {
        "atm": {"name": "atm", "title": "ATM", "url": "https://atm.example/"},
        "camcom": {"name": "camcom", "title": "CamCom", "url": "https://camcom.example/"},
    }

    output = tmp_path / "out.ttl"
    config_path = _write_config(tmp_path)
    result = runner.invoke(
        app,
        ["generate", "--config", str(config_path), "--output", str(output), "--multi-catalog"],
    )
    assert result.exit_code == 0, result.output
    assert output.exists()

    # Verifica struttura: aggregator + 2 sub-catalog + dct:hasPart
    from rdflib import Graph, URIRef
    from dcat_ap_it_generator.namespaces import DCAT, DCATAPIT, DCT
    g = Graph(); g.parse(str(output), format="turtle")
    catalogs = set(g.subjects(None, None))  # not used
    cat_nodes = set(g.subjects(predicate=None, object=DCATAPIT.Catalog))
    # rdflib pattern correction:
    from rdflib.namespace import RDF
    cat_nodes = set(g.subjects(RDF.type, DCATAPIT.Catalog))
    assert len(cat_nodes) == 3  # 1 aggregator + 2 sub
    aggregator = URIRef(f"{BASE_URL}/catalog")
    assert aggregator in cat_nodes
    parts = set(g.objects(aggregator, DCT.hasPart))
    assert len(parts) == 2


def test_generate_multi_catalog_conflicts_with_organizations(tmp_path):
    config_path = _write_config(tmp_path)
    result = runner.invoke(
        app,
        ["generate", "--config", str(config_path), "--multi-catalog", "--organizations", "x"],
    )
    assert result.exit_code == 1
    assert "mutuamente esclusivi" in result.output


# --- validate: file non trovato ---

def test_validate_missing_file(tmp_path):
    result = runner.invoke(app, ["validate", str(tmp_path / "nope.ttl")])
    assert result.exit_code == 1


# --- validate: file valido (catalogo vuoto) ---

def test_validate_valid_empty_catalog(tmp_path):
    from dcat_ap_it_generator.mapper import build_catalog
    g = build_catalog(_CONFIG, [], BASE_URL)
    ttl_path = tmp_path / "test.ttl"
    g.serialize(destination=str(ttl_path), format="turtle")

    result = runner.invoke(app, ["validate", str(ttl_path)])
    # Può avere violazioni (catalogo vuoto), ma non deve crashare
    assert result.exit_code in (0, 1)
    # Non deve mostrare traceback Python
    assert "Traceback" not in result.output


# --- validate: regola SPARQL rotta viene segnalata ---

def test_validate_broken_rule_logged(tmp_path):
    from dcat_ap_it_generator.mapper import build_catalog
    g = build_catalog(_CONFIG, [], BASE_URL)
    ttl_path = tmp_path / "test.ttl"
    g.serialize(destination=str(ttl_path), format="turtle")

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "broken.rq").write_text("THIS IS NOT VALID SPARQL")

    result = runner.invoke(app, ["validate", str(ttl_path), "--rules-dir", str(rules_dir)])
    assert result.exit_code == 0  # nessuna violazione trovata
    # La regola rotta deve essere segnalata in output (stderr catturato da CliRunner)
    assert "Skip broken" in result.output or "Regole saltate: 1" in result.output


# --- validate: regola SPARQL valida trova violazione ---

def test_validate_finds_violation(tmp_path):
    """Una regola SPARQL che cerca Catalog senza dct:description deve trovare violazione."""
    from dcat_ap_it_generator.mapper import build_catalog
    cfg_no_desc = {**_CONFIG, "catalog": {**_CONFIG["catalog"], "description": None}}
    g = build_catalog(cfg_no_desc, [], BASE_URL)
    ttl_path = tmp_path / "test.ttl"
    g.serialize(destination=str(ttl_path), format="turtle")

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    # Regola semplice: trova Catalog senza description
    (rules_dir / "test-rule.rq").write_text("""
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dct: <http://purl.org/dc/terms/>
SELECT ?Rule_ID ?Rule_Severity ?Class_Name ?Rule_Description ?Message WHERE {
    ?s a dcat:Catalog .
    FILTER NOT EXISTS { ?s dct:description ?d }
    BIND("test-rule" AS ?Rule_ID)
    BIND("warning" AS ?Rule_Severity)
    BIND("Catalog" AS ?Class_Name)
    BIND("Missing description" AS ?Rule_Description)
    BIND("Catalog without description" AS ?Message)
}
""")

    result = runner.invoke(app, ["validate", str(ttl_path), "--rules-dir", str(rules_dir)])
    assert result.exit_code == 0  # solo warning, non errori
    assert "1 warning" in result.output
    assert "Catalog without description" in result.output
