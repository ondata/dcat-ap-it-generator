import logging
import time
from typing import Generator

import requests

log = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "dcat-ap-it-generator/1.0"})


def _api_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/api/3/action"


def fetch_all_datasets(
    base_url: str,
    query_template: str = "",
    rows_per_page: int = 100,
    api_key: str = "",
) -> Generator[dict, None, None]:
    """Yield ogni dataset dal portale CKAN, con paginazione automatica."""
    headers = {}
    if api_key:
        headers["Authorization"] = api_key

    api = _api_url(base_url)
    start = 0

    while True:
        params: dict[str, str | int] = {
            "rows": rows_per_page,
            "start": start,
        }
        if query_template:
            params["fq"] = query_template

        try:
            resp = _SESSION.get(
                f"{api}/package_search",
                params=params,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            log.warning("Errore fetch pagina start=%d: %s — retry", start, e)
            time.sleep(1)
            try:
                resp = _SESSION.get(
                    f"{api}/package_search",
                    params=params,
                    headers=headers,
                    timeout=30,
                )
                resp.raise_for_status()
            except requests.RequestException as e2:
                log.error("Retry fallito start=%d: %s — skip pagina", start, e2)
                break

        data = resp.json()
        if not data.get("success"):
            log.error("CKAN API error: %s", data.get("error"))
            break

        results = data["result"]["results"]
        if not results:
            break

        yield from results

        start += len(results)
        total = data["result"]["count"]
        if start >= total:
            break

        time.sleep(0.1)


def fetch_organization(base_url: str, org_name: str, api_key: str = "") -> dict | None:
    """Ritorna i metadati di un'organizzazione CKAN."""
    headers = {}
    if api_key:
        headers["Authorization"] = api_key

    api = _api_url(base_url)

    try:
        resp = _SESSION.get(
            f"{api}/organization_show",
            params={"id": org_name},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            return data["result"]
    except requests.RequestException as e:
        log.error("Errore fetch organizzazione %s: %s", org_name, e)

    return None


def count_datasets(
    base_url: str,
    query_template: str = "",
    api_key: str = "",
) -> int:
    """Ritorna il numero totale di dataset corrispondenti alla query."""
    headers = {}
    if api_key:
        headers["Authorization"] = api_key

    api = _api_url(base_url)
    params: dict[str, str | int] = {"rows": 0}
    if query_template:
        params["fq"] = query_template

    try:
        resp = _SESSION.get(
            f"{api}/package_search",
            params=params,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            return data["result"]["count"]
    except requests.RequestException as e:
        log.error("Errore count dataset: %s", e)

    return 0
