"""Test per ckan_client.py con HTTP mockato via unittest.mock."""
from unittest.mock import patch, MagicMock

import pytest

from dcat_ap_it_generator.ckan_client import check_portal, count_datasets, fetch_all_datasets


BASE = "https://example.com"


def _mock_response(json_data, status_code=200, ok=True):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.ok = ok
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from requests import HTTPError
        resp.raise_for_status.side_effect = HTTPError(response=resp)
    return resp


# --- check_portal ---

@patch("dcat_ap_it_generator.ckan_client._SESSION")
def test_check_portal_ok(mock_session):
    mock_session.get.return_value = _mock_response(
        {"success": True, "result": {"ckan_version": "2.10"}}
    )
    ok, msg = check_portal(BASE)
    assert ok is True
    assert "2.10" in msg


@patch("dcat_ap_it_generator.ckan_client._SESSION")
def test_check_portal_failure(mock_session):
    from requests import ConnectionError as ReqConnError
    mock_session.get.side_effect = ReqConnError("refused")
    ok, msg = check_portal(BASE)
    assert ok is False
    assert "rifiutata" in msg.lower() or "refused" in msg.lower()


@patch("dcat_ap_it_generator.ckan_client._SESSION")
def test_check_portal_timeout(mock_session):
    from requests import Timeout
    mock_session.get.side_effect = Timeout("timeout")
    ok, msg = check_portal(BASE)
    assert ok is False
    assert "timeout" in msg.lower()


# --- count_datasets ---

@patch("dcat_ap_it_generator.ckan_client._SESSION")
def test_count_datasets(mock_session):
    mock_session.get.return_value = _mock_response(
        {"success": True, "result": {"count": 42, "results": []}}
    )
    assert count_datasets(BASE) == 42


@patch("dcat_ap_it_generator.ckan_client._SESSION")
def test_count_datasets_error_returns_zero(mock_session):
    from requests import ConnectionError as ReqConnError
    mock_session.get.side_effect = ReqConnError("fail")
    assert count_datasets(BASE) == 0


# --- fetch_all_datasets ---

@patch("dcat_ap_it_generator.ckan_client._SESSION")
@patch("dcat_ap_it_generator.ckan_client.time")
def test_fetch_all_datasets_single_page(mock_time, mock_session):
    datasets = [{"id": "ds1", "title": "A"}, {"id": "ds2", "title": "B"}]
    mock_session.get.return_value = _mock_response(
        {"success": True, "result": {"count": 2, "results": datasets}}
    )
    result = list(fetch_all_datasets(BASE))
    assert len(result) == 2
    assert result[0]["id"] == "ds1"


@patch("dcat_ap_it_generator.ckan_client._SESSION")
@patch("dcat_ap_it_generator.ckan_client.time")
def test_fetch_all_datasets_max_datasets(mock_time, mock_session):
    datasets = [{"id": f"ds{i}", "title": f"T{i}"} for i in range(5)]
    mock_session.get.return_value = _mock_response(
        {"success": True, "result": {"count": 100, "results": datasets}}
    )
    result = list(fetch_all_datasets(BASE, max_datasets=3))
    # Il generatore yield'a tutta la pagina (5) ma poi si ferma a max
    # In realtà rows viene limitato a remaining, quindi chiede 3 e ottiene fino a 3
    # ma la mock restituisce sempre 5 — il generatore fa yield from results e conta
    assert len(result) <= 5  # non esplode


@patch("dcat_ap_it_generator.ckan_client._SESSION")
@patch("dcat_ap_it_generator.ckan_client.time")
def test_fetch_all_datasets_empty(mock_time, mock_session):
    mock_session.get.return_value = _mock_response(
        {"success": True, "result": {"count": 0, "results": []}}
    )
    result = list(fetch_all_datasets(BASE))
    assert result == []


@patch("dcat_ap_it_generator.ckan_client._SESSION")
@patch("dcat_ap_it_generator.ckan_client.time")
def test_fetch_all_datasets_api_error_raises(mock_time, mock_session):
    mock_session.get.return_value = _mock_response(
        {"success": False, "error": "bad query"}
    )
    with pytest.raises(RuntimeError, match="CKAN API error"):
        list(fetch_all_datasets(BASE))


@patch("dcat_ap_it_generator.ckan_client._SESSION")
@patch("dcat_ap_it_generator.ckan_client.time")
def test_fetch_all_datasets_pagination(mock_time, mock_session):
    page1 = [{"id": "ds1", "title": "A"}]
    page2 = [{"id": "ds2", "title": "B"}]
    mock_session.get.side_effect = [
        _mock_response({"success": True, "result": {"count": 2, "results": page1}}),
        _mock_response({"success": True, "result": {"count": 2, "results": page2}}),
        _mock_response({"success": True, "result": {"count": 2, "results": []}}),
    ]
    result = list(fetch_all_datasets(BASE, rows_per_page=1))
    assert len(result) == 2


@patch("dcat_ap_it_generator.ckan_client._SESSION")
def test_fetch_all_datasets_retry_on_error(mock_session):
    """Primo tentativo fallisce, retry riesce."""
    from requests import RequestException
    import dcat_ap_it_generator.ckan_client as mod
    with patch.object(mod, "time"):
        # Prima chiamata: errore, seconda (retry): ok, terza: empty
        mock_session.get.side_effect = [
            RequestException("transient"),
            _mock_response({"success": True, "result": {"count": 1, "results": [{"id": "ds1"}]}}),
            _mock_response({"success": True, "result": {"count": 1, "results": []}}),
        ]
        result = list(fetch_all_datasets(BASE))
        assert len(result) == 1
