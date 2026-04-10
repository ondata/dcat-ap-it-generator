#!/usr/bin/env python3
"""DCAT-AP IT Generator — genera cataloghi RDF Turtle da portali CKAN."""

import logging
import time
from pathlib import Path

import typer
import yaml
from pyfiglet import figlet_format
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(
    name="dcat-ap-it",
    help="Genera cataloghi RDF DCAT-AP IT da portali CKAN.",
    add_completion=False,
    invoke_without_command=True,
)


@app.callback()
def default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
console = Console()
err_console = Console(stderr=True)


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        err_console.print(f"[red]Error:[/red] config file not found: {config_path}")
        err_console.print(f"  dcat-ap-it generate --config [bold]{config_path}[/bold]")
        err_console.print("  dcat-ap-it configure  # to create a new config interactively")
        raise typer.Exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def _validate_config(cfg: dict) -> None:
    portal = cfg.get("portal", {})
    if not portal.get("url"):
        err_console.print("[red]Error:[/red] portal.url is required in config")
        raise typer.Exit(1)
    catalog = cfg.get("catalog", {})
    if not catalog.get("uri"):
        err_console.print("[red]Error:[/red] catalog.uri is required in config")
        raise typer.Exit(1)


@app.command()
def generate(
    config: Path = typer.Option(Path("config.yml"), "--config", "-c", help="File YAML config"),
    output: Path = typer.Option(None, "--output", "-o", help="Override output path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Output dettagliato con banner"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Solo fetch, non scrive file"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Salta conferme interattive"),
    organizations: str = typer.Option(
        None,
        "--organizations",
        help="Filtra per org (comma-separated). Genera un file per org.",
    ),
    multi_catalog: bool = typer.Option(
        False,
        "--multi-catalog",
        help="Produce 1 catalogo aggregator + 1 sub-catalog per organization (dct:hasPart).",
    ),
) -> None:
    """Genera un file Turtle DCAT-AP IT da un portale CKAN.

    Examples:
      dcat-ap-it generate --config config.yml
      dcat-ap-it generate --config config.yml --output /tmp/catalog.ttl
      dcat-ap-it generate --config config.yml --dry-run
      dcat-ap-it generate --config config.yml --organizations pat,comune-trento
      dcat-ap-it generate --config config.yml --multi-catalog
    """
    if verbose:
        console.print(figlet_format("DCAT-AP IT", font="slant"), style="bold cyan")

    cfg = _load_config(config)
    _validate_config(cfg)

    portal_cfg = cfg.get("portal", {})
    catalog_cfg = cfg.get("catalog", {})
    output_cfg = cfg.get("output", {})

    base_url: str = portal_cfg["url"]
    api_key: str = portal_cfg.get("api_key", "")
    rows_per_page: int = int(portal_cfg.get("rows_per_page", 100))
    query_template: str = portal_cfg.get("query_template", "")
    max_datasets_cfg = portal_cfg.get("max_datasets")
    max_datasets: int | None = (int(max_datasets_cfg) or None) if max_datasets_cfg is not None else None
    chunk_size_cfg = portal_cfg.get("chunk_size")
    chunk_size: int | None = (int(chunk_size_cfg) or None) if chunk_size_cfg is not None else None
    timeout: int = int(portal_cfg.get("timeout", 30))

    output_path = output or Path(output_cfg.get("path", "output/catalog.ttl"))

    org_list = [o.strip() for o in organizations.split(",")] if organizations else []

    if multi_catalog and org_list:
        err_console.print(
            "[red]Error:[/red] --multi-catalog e --organizations sono mutuamente esclusivi"
        )
        raise typer.Exit(1)
    if multi_catalog and chunk_size:
        err_console.print(
            "[red]Error:[/red] --multi-catalog non è compatibile con portal.chunk_size "
            "(modalità streaming a chunk)"
        )
        raise typer.Exit(1)

    from .ckan_client import check_portal, count_datasets, fetch_all_datasets, fetch_all_organizations
    from .mapper import build_catalog, build_catalog_multi

    # Health check portale
    ok, msg = check_portal(base_url, api_key, timeout=timeout)
    if not ok:
        err_console.print(f"[red]Portale non raggiungibile:[/red] {msg}")
        raise typer.Exit(1)
    if verbose:
        console.print(f"Portale OK: [green]{msg}[/green]")

    # Conta dataset totali per progress bar (limitato da max_datasets se impostato)
    total = count_datasets(base_url, query_template, api_key, timeout=timeout)
    if max_datasets is not None:
        total = min(total, max_datasets)
    if verbose:
        console.print(f"Portale: [cyan]{base_url}[/cyan]")
        console.print(f"Dataset stimati: [cyan]{total}[/cyan]")

    # --- Streaming chunk mode: fetch + serialize senza accumulare tutto ---
    stream_chunks = chunk_size and not org_list and not dry_run

    datasets: list[dict] = []
    errors: list[str] = []
    n_total_datasets = 0
    n_total_dist = 0
    n_chunks_written = 0

    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
        transient=not verbose,
    ) as progress:
        task = progress.add_task("Fetching datasets...", total=total or None)
        try:
            if stream_chunks:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                stem = output_path.stem
                chunk_buf: list[dict] = []
                for ds in fetch_all_datasets(base_url, query_template, rows_per_page, api_key, max_datasets, timeout=timeout):
                    progress.update(task, advance=1)
                    if not ds.get("title"):
                        errors.append(ds.get("id", "unknown"))
                        continue
                    chunk_buf.append(ds)
                    if chunk_size and len(chunk_buf) >= chunk_size:
                        n_chunks_written += 1
                        n_total_datasets += len(chunk_buf)
                        n_total_dist += sum(len(d.get("resources") or []) for d in chunk_buf)
                        g = build_catalog(cfg, chunk_buf, base_url)
                        chunk_path = output_path.parent / f"{stem}_{n_chunks_written:03d}.ttl"
                        g.serialize(destination=str(chunk_path), format="turtle")
                        if verbose:
                            console.print(f"  [green]✓[/green] {chunk_path} — {len(chunk_buf)} dataset")
                        chunk_buf = []
                # flush residuo
                if chunk_buf:
                    n_chunks_written += 1
                    n_total_datasets += len(chunk_buf)
                    n_total_dist += sum(len(d.get("resources") or []) for d in chunk_buf)
                    g = build_catalog(cfg, chunk_buf, base_url)
                    chunk_path = output_path.parent / f"{stem}_{n_chunks_written:03d}.ttl"
                    g.serialize(destination=str(chunk_path), format="turtle")
                    if verbose:
                        console.print(f"  [green]✓[/green] {chunk_path} — {len(chunk_buf)} dataset")
            else:
                for ds in fetch_all_datasets(base_url, query_template, rows_per_page, api_key, max_datasets, timeout=timeout):
                    if ds.get("title"):
                        datasets.append(ds)
                    else:
                        errors.append(ds.get("id", "unknown"))
                    progress.update(task, advance=1)
        except RuntimeError as e:
            err_console.print(f"[red]Errore fetch dataset:[/red] {e}")
            raise typer.Exit(1)

    if dry_run:
        n_dist = sum(len(ds.get("resources") or []) for ds in datasets)
        _print_summary(base_url, output_path, len(datasets), n_dist, 0, dry_run=True)
        raise typer.Exit(0)

    if not stream_chunks:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if org_list:
            for org in org_list:
                org_datasets = [d for d in datasets if _dataset_org(d) == org]
                g = build_catalog(cfg, org_datasets, base_url)
                org_path = output_path.parent / f"{org}.ttl"
                g.serialize(destination=str(org_path), format="turtle")
                n_dist = sum(len(d.get("resources") or []) for d in org_datasets)
                if verbose:
                    console.print(f"  [green]✓[/green] {org_path} — {len(org_datasets)} dataset, {n_dist} distribuzioni")
        elif multi_catalog:
            # Raggruppamento O(N) per org
            datasets_by_org: dict[str, list[dict]] = {}
            for d in datasets:
                datasets_by_org.setdefault(_dataset_org(d), []).append(d)

            # Fetch metadati di tutte le org con una singola chiamata API
            if verbose:
                console.print("Fetch metadati organization...")
            org_metadata = fetch_all_organizations(
                base_url, api_key=api_key, timeout=timeout
            )

            g = build_catalog_multi(cfg, datasets_by_org, base_url, org_metadata)
            g.serialize(destination=str(output_path), format="turtle")
            if verbose:
                console.print(
                    f"  [green]✓[/green] {output_path} — "
                    f"1 aggregator + {sum(1 for n in datasets_by_org if n)} sub-catalog"
                )
        else:
            g = build_catalog(cfg, datasets, base_url)
            g.serialize(destination=str(output_path), format="turtle")

        n_total_datasets = len(datasets)
        n_total_dist = sum(len(ds.get("resources") or []) for ds in datasets)

    duration = int(time.time() - start_time)

    if stream_chunks or (chunk_size and not org_list):
        out_label = f"{output_path.parent}/{output_path.stem}_*.ttl ({n_chunks_written} chunks)"
    else:
        out_label = str(output_path)

    if verbose:
        _print_summary(base_url, output_path, n_total_datasets, n_total_dist, duration)
    else:
        console.print(
            f"generated {out_label}  "
            f"datasets={n_total_datasets} "
            f"distributions={n_total_dist} "
            f"duration={duration}s"
        )

    if errors:
        err_console.print(f"[yellow]Warning:[/yellow] {len(errors)} dataset saltati (senza title)")

    raise typer.Exit(0)


def _dataset_org(ds: dict) -> str:
    org = ds.get("organization")
    if isinstance(org, dict):
        return org.get("name", "")
    return str(org or "")


def _print_summary(base_url: str, output_path: Path, n_ds: int, n_dist: int, duration: int, dry_run: bool = False) -> None:
    mode = "[yellow]DRY RUN — nessun file scritto[/yellow]" if dry_run else f"Output:       {output_path}"
    console.print(
        Panel(
            f"Portale:      {base_url}\n"
            f"Dataset:      {n_ds}\n"
            f"Distribuzioni:{n_dist}\n"
            f"{mode}" + (f"\nDurata:       {duration}s" if not dry_run else ""),
            title="[bold green]Catalog generato[/bold green]" if not dry_run else "[bold yellow]Dry run[/bold yellow]",
            border_style="green" if not dry_run else "yellow",
        )
    )


@app.command()
def configure(
    output: Path = typer.Option(Path("config.yml"), "--output", "-o", help="Path file config da creare"),
) -> None:
    """Wizard interattivo per creare config.yml. Solo uso umano — non scriptabile.

    Examples:
      dcat-ap-it configure
      dcat-ap-it configure --output my-portal.yml
    """
    try:
        import questionary
    except ImportError:
        err_console.print("[red]Error:[/red] questionary non installato. Esegui: uv add questionary")
        raise typer.Exit(1)

    console.print(figlet_format("Configure", font="slant"), style="bold cyan")

    url = questionary.text("URL portale CKAN:", validate=lambda t: t.startswith("http") or "Deve iniziare con http").ask()
    if url is None:
        raise typer.Exit(0)

    cat_uri = questionary.text("URI del catalogo:", default=f"{url.rstrip('/')}/catalog").ask()
    cat_title = questionary.text("Titolo catalogo:").ask()
    cat_desc = questionary.text("Descrizione catalogo (opzionale):").ask()
    pub_name = questionary.text("Nome publisher:").ask()
    pub_id = questionary.text("Codice IPA publisher (opzionale):").ask()
    language = questionary.text("Lingua default (codice ISO 639-3):", default="ITA").ask()
    out_path = questionary.text("Path output:", default="output/catalog.ttl").ask()

    cfg = {
        "portal": {
            "url": url,
            "api_key": "",
            "rows_per_page": 100,
            "query_template": "",
        },
        "catalog": {
            "uri": cat_uri,
            "title": cat_title,
            "description": cat_desc or "",
            "issued": "",
            "publisher_name": pub_name,
            "publisher_identifier": pub_id or "",
            "language": language,
            "homepage": url,
        },
        "output": {
            "path": out_path,
        },
    }

    table = Table(title="Configurazione")
    table.add_column("Parametro", style="cyan")
    table.add_column("Valore", style="green")
    for k, v in {
        "portal.url": url,
        "catalog.uri": cat_uri,
        "catalog.title": cat_title,
        "catalog.publisher_name": pub_name,
        "output.path": out_path,
    }.items():
        table.add_row(k, str(v))
    console.print(table)

    import questionary as q
    if not q.confirm(f"Salvare in {output}?", default=True).ask():
        console.print("[yellow]Annullato[/yellow]")
        raise typer.Exit(0)

    with open(output, "w") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

    console.print(f"[green]✓[/green] {output} creato")


@app.command()
def validate(
    input: Path = typer.Argument(..., help="File TTL da validare"),
    rules_dir: Path = typer.Option(None, "--rules-dir", help="Directory regole SPARQL (default: built-in)"),
    errors_only: bool = typer.Option(False, "--errors-only", "-e", help="Mostra solo errori, non warning"),
) -> None:
    """Valida un file TTL contro le regole DCAT-AP IT."""
    from rdflib import Graph

    if not input.exists():
        err_console.print(f"[red]File non trovato:[/red] {input}")
        raise typer.Exit(1)

    rules_path = rules_dir or Path(__file__).parent / "rules"
    rule_files = sorted(f for f in rules_path.glob("*.rq") if not f.suffix == ".suspended")

    console.print(f"Caricamento [cyan]{input}[/cyan]...")
    g = Graph()
    g.parse(str(input), format="turtle")
    console.print(f"  Triple: {len(g)}")
    console.print(f"  Regole: {len(rule_files)}")

    violations: list[dict] = []
    skipped: list[str] = []
    for rule_file in rule_files:
        query = rule_file.read_text()
        try:
            results = g.query(query)
            for row in results:
                row_d = row.asdict()
                severity = str(row_d.get("Rule_Severity", "")).lower()
                if errors_only and severity != "error":
                    continue
                violations.append({
                    "rule": str(row_d.get("Rule_ID", rule_file.stem)),
                    "severity": severity,
                    "class": str(row_d.get("Class_Name", "")),
                    "description": str(row_d.get("Rule_Description", "")),
                    "message": str(row_d.get("Message", "")),
                })
        except Exception as exc:
            skipped.append(rule_file.stem)
            err_console.print(f"[dim]Skip {rule_file.stem}: {type(exc).__name__}: {exc}[/dim]")

    if skipped:
        console.print(f"[yellow]Regole saltate: {len(skipped)}/{len(rule_files)}[/yellow]")

    if not violations:
        console.print(f"[green]✓ Nessuna violazione trovata[/green]")
        raise typer.Exit(0)

    errors = [v for v in violations if v["severity"] == "error"]
    warnings = [v for v in violations if v["severity"] != "error"]

    table = Table(title=f"Violazioni DCAT-AP IT — {input.name}", show_lines=False)
    table.add_column("Rule", style="dim", width=6)
    table.add_column("Severity", width=8)
    table.add_column("Class", width=14)
    table.add_column("Message")

    for v in violations:
        color = "red" if v["severity"] == "error" else "yellow"
        table.add_row(v["rule"], f"[{color}]{v['severity']}[/{color}]", v["class"], v["message"])

    console.print(table)
    skip_msg = f", [dim]{len(skipped)} regole saltate[/dim]" if skipped else ""
    console.print(f"Totale: [red]{len(errors)} errori[/red], [yellow]{len(warnings)} warning[/yellow]{skip_msg}")
    raise typer.Exit(1 if errors else 0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    app()
