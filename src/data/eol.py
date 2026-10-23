"""Extract end-of-support dates from the public endoflife.date API (Issue #41).

Steps of :func:`run_extraction`: initialise (read the configuration), fetch each product
(one request per second at most, retries with growing waits on 5xx/429/network errors, unknown
product in 404 logged and skipped, same-day local cache), normalise one row per version, save
``data/raw/eol/products.jsonl`` (ignored by Git) and an execution report.

Network, clock and sleeping are injectable so that the tests make no real call and no real wait.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx2
import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "config" / "eol_products.yaml"

logger = logging.getLogger("eol")

# Exit codes of scripts/fetch_eol.py
EXIT_OK = 0
EXIT_PARTIAL = 1  # some products missing (404 or errors), others were saved
EXIT_CONFIG = 2  # invalid configuration or unknown --only value
EXIT_NOTHING = 3  # nothing could be extracted (source unreachable)


class ProductNotFound(Exception):
    """The API answered 404 for this product."""


class FetchError(Exception):
    """The product could not be fetched (retries exhausted or unexpected answer)."""


# --------------------------------------------------------------------------- configuration


@dataclass(frozen=True)
class EolConfig:
    base_url: str
    user_agent: str
    license: str
    attribution: str
    timeout: float
    min_interval: float
    max_retries: int
    backoff: float
    output_directory: Path
    output_file: str
    report_file: str
    cache_directory: Path
    products: tuple[str, ...]


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> EolConfig:
    """Read and check the configuration (relative paths are relative to the repository root)."""
    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    products = tuple(raw["products"])
    if not products or len(set(products)) != len(products):
        raise ValueError("liste de produits vide ou avec doublons")
    if any(not isinstance(p, str) or "/" in p or not p.strip() for p in products):
        raise ValueError("identifiant de produit invalide")
    http = raw["http"]
    if http["min_interval_seconds"] < 1.0:
        raise ValueError("min_interval_seconds doit rester >= 1 (respect de la source)")
    out = raw["output"]
    directory = Path(out["directory"])
    if not directory.is_absolute():
        directory = ROOT / directory
    return EolConfig(
        base_url=raw["source"]["base_url"],
        user_agent=raw["source"]["user_agent"],
        license=raw["source"]["license"],
        attribution=raw["source"]["attribution"],
        timeout=float(http["timeout_seconds"]),
        min_interval=float(http["min_interval_seconds"]),
        max_retries=int(http["max_retries"]),
        backoff=float(http["backoff_seconds"]),
        output_directory=directory,
        output_file=out["file"],
        report_file=out["report_file"],
        cache_directory=directory / out["cache_directory"],
        products=products,
    )


# --------------------------------------------------------------------------- HTTP client


class EolClient:
    """Polite client: rate limit, timeout, retries with growing waits, 404 handling."""

    def __init__(
        self,
        config: EolConfig,
        transport: httpx2.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._http = httpx2.Client(
            headers={"User-Agent": config.user_agent, "Accept": "application/json"},
            timeout=config.timeout,
            transport=transport,
        )
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None
        self.requests_made = 0
        self.retries = 0

    def close(self) -> None:
        self._http.close()

    def _wait_turn(self) -> None:
        """Keep at least ``min_interval`` seconds between two requests."""
        if self._last_request is not None:
            wait = self._config.min_interval - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()

    def fetch_product(self, product: str) -> dict[str, Any]:
        """Return the JSON of one product. Raise ProductNotFound or FetchError."""
        url = f"{self._config.base_url}{product}/"
        reason = "inconnue"
        for attempt in range(self._config.max_retries + 1):
            if attempt:
                self.retries += 1
                self._sleep(self._config.backoff * 2 ** (attempt - 1))
            self._wait_turn()
            self.requests_made += 1
            try:
                response = self._http.get(url)
            except httpx2.TransportError as error:  # timeout, connection reset, DNS...
                reason = type(error).__name__
                continue
            status = response.status_code
            if status == 404:
                raise ProductNotFound(product)
            if status == 429 or status >= 500:
                reason = f"HTTP {status}"
                continue
            if status != 200:
                raise FetchError(f"{product}: HTTP {status}")
            try:
                data = response.json()
            except ValueError as error:
                raise FetchError(f"{product}: réponse non JSON") from error
            if not isinstance(data, dict) or not isinstance(data.get("result"), dict):
                raise FetchError(f"{product}: format de réponse inattendu")
            return data
        raise FetchError(
            f"{product}: échec après {self._config.max_retries} nouvelles tentatives ({reason})"
        )


# --------------------------------------------------------------------------- normalisation


def normalize_date(value: Any) -> str | None:
    """Return an ISO 8601 date (YYYY-MM-DD) or None (absent, boolean or unparsable value)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return None


def normalize_product_name(name: str) -> str:
    """Normalised product identifier: lowercase, trimmed (the API already uses slugs)."""
    return name.strip().lower()


def parse_product(data: dict[str, Any], extracted_at: str) -> tuple[list[dict[str, Any]], int]:
    """Turn an API answer into one row per version. Return (rows, number of invalid dates)."""
    result = data["result"]
    product = normalize_product_name(result["name"])
    rows: list[dict[str, Any]] = []
    invalid_dates = 0
    for release in result.get("releases", []):
        raw_dates = {
            "release_date": release.get("releaseDate"),
            "active_support_end": release.get("eoasFrom"),
            "security_support_end": release.get("eolFrom"),
            "extended_support_end": release.get("eoesFrom"),
        }
        dates = {key: normalize_date(value) for key, value in raw_dates.items()}
        invalid_dates += sum(
            1 for key, value in raw_dates.items() if isinstance(value, str) and dates[key] is None
        )
        maintained = release.get("isMaintained")
        if maintained is None:
            maintained = not release.get("isEol", False)
        latest = release.get("latest") or {}
        rows.append(
            {
                "product": product,
                "product_label": result.get("label"),
                "category": result.get("category"),
                "version": str(release.get("name")),
                "version_label": release.get("label"),
                "codename": release.get("codename"),
                **dates,
                "is_lts": bool(release.get("isLts")),
                "is_maintained": bool(maintained),
                "latest_version": latest.get("name"),
                "extracted_at": extracted_at,
                "source": "endoflife.date",
            }
        )
    return rows, invalid_dates


# --------------------------------------------------------------------------- cache and run


def _cache_path(config: EolConfig, product: str, day: str) -> Path:
    return config.cache_directory / f"{product}-{day}.json"


def _read_cache(config: EolConfig, product: str, day: str) -> dict[str, Any] | None:
    path = _cache_path(config, product, day)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None  # corrupted cache: fetch again
    return data if isinstance(data, dict) and isinstance(data.get("result"), dict) else None


def _write_cache(config: EolConfig, product: str, day: str, data: dict[str, Any]) -> None:
    config.cache_directory.mkdir(parents=True, exist_ok=True)
    _cache_path(config, product, day).write_text(json.dumps(data), encoding="utf-8")


@dataclass
class EolReport:
    started_at: str
    products_requested: int = 0
    products_ok: int = 0
    from_cache: int = 0
    not_found: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    versions: int = 0
    invalid_dates: int = 0
    requests: int = 0
    retries: int = 0
    duration_seconds: float = 0.0
    versions_by_product: dict[str, int] = field(default_factory=dict)

    def exit_code(self) -> int:
        if self.products_ok == 0:
            return EXIT_NOTHING
        return EXIT_PARTIAL if (self.failed or self.not_found) else EXIT_OK


def run_extraction(
    config: EolConfig,
    only: list[str] | None = None,
    client: EolClient | None = None,
    today: date | None = None,
) -> EolReport:
    """Fetch the products, write products.jsonl and the report. Log metadata only."""
    started = time.monotonic()
    today = today or datetime.now(UTC).date()
    day = today.isoformat()
    products = [p for p in config.products if not only or p in only]
    report = EolReport(
        started_at=datetime.now(UTC).isoformat(timespec="seconds"),
        products_requested=len(products),
    )
    own_client = client is None
    client = client or EolClient(config)
    rows: list[dict[str, Any]] = []
    try:
        for product in products:
            data = _read_cache(config, product, day)
            if data is not None:
                report.from_cache += 1
            else:
                try:
                    data = client.fetch_product(product)
                except ProductNotFound:
                    logger.warning("produit inconnu (404), ignoré : %s", product)
                    report.not_found.append(product)
                    continue
                except FetchError as error:
                    logger.error("échec : %s", error)
                    report.failed.append(product)
                    continue
                _write_cache(config, product, day, data)
            product_rows, invalid = parse_product(data, day)
            rows.extend(product_rows)
            report.products_ok += 1
            report.invalid_dates += invalid
            report.versions_by_product[product] = len(product_rows)
            logger.info("%s : %d versions", product, len(product_rows))
    finally:
        if own_client:
            client.close()
    report.versions = len(rows)
    report.requests = client.requests_made
    report.retries = client.retries
    report.duration_seconds = round(time.monotonic() - started, 2)
    # Do not replace a good file with an empty one when the source is unreachable.
    if rows:
        _save(config, rows)
    config.output_directory.mkdir(parents=True, exist_ok=True)
    (config.output_directory / config.report_file).write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def _save(config: EolConfig, rows: list[dict[str, Any]]) -> None:
    """Write the JSONL atomically (temporary file then replace)."""
    config.output_directory.mkdir(parents=True, exist_ok=True)
    target = config.output_directory / config.output_file
    temporary = target.with_suffix(".tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(target)
