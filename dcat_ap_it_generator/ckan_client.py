import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Generator, Iterable

import requests

log = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "dcat-ap-it-generator/1.0"})


def _api_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/api/3/action"


def check_portal(base_url: str, api_key: str = "", timeout: int = 30) -> tuple[bool, str]:
    """Verifica che il portale CKAN sia raggiungibile.

    Returns:
        (ok, message) — ok=True se il portale risponde, False altrimenti.
    """
    headers = {}
    if api_key:
        headers["Authorization"] = api_key

    api = _api_url(base_url)
    try:
        resp = _SESSION.get(
            f"{api}/status_show",
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            return True, f"CKAN {data['result'].get('ckan_version', '?')}"
        return False, f"API responded but success=false: {data.get('error')}"
    except requests.ConnectionError:
        return False, f"Connessione rifiutata: {base_url}"
    except requests.Timeout:
        return False, f"Timeout dopo {timeout}s: {base_url}"
    except requests.RequestException:
        # Fallback: alcuni portali bloccano status_show ma rispondono a package_search
        try:
            resp2 = _SESSION.get(
                f"{api}/package_search",
                params={"rows": 0},
                headers=headers,
                timeout=timeout,
            )
            resp2.raise_for_status()
            data2 = resp2.json()
            if data2.get("success"):
                return True, f"CKAN (status_show bloccato, {data2['result']['count']} dataset)"
        except requests.RequestException:
            pass
        return False, f"Portale non raggiungibile: {base_url}"


def fetch_all_datasets(
    base_url: str,
    query_template: str = "",
    rows_per_page: int = 100,
    api_key: str = "",
    max_datasets: int | None = None,
    timeout: int = 30,
) -> Generator[dict, None, None]:
    """Yield ogni dataset dal portale CKAN, con paginazione automatica.

    Args:
        max_datasets: se impostato, si ferma dopo aver restituito questo numero di dataset.
                      Utile per debug su portali grandi.
    """
    headers = {}
    if api_key:
        headers["Authorization"] = api_key

    api = _api_url(base_url)
    start = 0
    yielded = 0

    while True:
        remaining = None
        if max_datasets is not None:
            remaining = max_datasets - yielded
            if remaining <= 0:
                break

        params: dict[str, str | int] = {
            "rows": min(rows_per_page, remaining) if remaining is not None else rows_per_page,
            "start": start,
        }
        if query_template:
            params["fq"] = query_template

        try:
            resp = _SESSION.get(
                f"{api}/package_search",
                params=params,
                headers=headers,
                timeout=timeout,
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
                    timeout=timeout,
                )
                resp.raise_for_status()
            except requests.RequestException as e2:
                raise RuntimeError(f"Retry fallito start={start}: {e2}") from e2

        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"CKAN API error: {data.get('error')}")

        results = data["result"]["results"]
        if not results:
            break

        yield from results
        yielded += len(results)

        start += len(results)
        total = data["result"]["count"]
        if start >= total:
            break

        time.sleep(0.1)


def fetch_organization(base_url: str, org_name: str, api_key: str = "", timeout: int = 30) -> dict | None:
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
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            return data["result"]
    except requests.RequestException as e:
        log.error("Errore fetch organizzazione %s: %s", org_name, e)

    return None


def fetch_organizations(
    base_url: str,
    org_names: Iterable[str],
    api_key: str = "",
    timeout: int = 30,
    max_workers: int = 8,
) -> dict[str, dict | None]:
    """Fetch metadati di più organization in parallelo.

    Returns: dict org_name → dict (o None se la fetch fallisce).
    Tollerante: errori sulla singola org non interrompono le altre.
    Riusa la sessione HTTP esistente per il connection pooling.
    """
    names = [n for n in dict.fromkeys(org_names) if n]  # dedup preservando ordine
    if not names:
        return {}

    results: dict[str, dict | None] = {n: None for n in names}
    # Limita i worker al numero di org per evitare thread inutili
    workers = max(1, min(max_workers, len(names)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(fetch_organization, base_url, name, api_key, timeout): name
            for name in names
        }
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except Exception as e:  # pragma: no cover - safety net
                log.warning("fetch_organizations %s fallita: %s", name, e)
                results[name] = None
    return results


def count_datasets(
    base_url: str,
    query_template: str = "",
    api_key: str = "",
    timeout: int = 30,
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
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            return data["result"]["count"]
    except requests.RequestException as e:
        log.error("Errore count dataset: %s", e)

    return 0
