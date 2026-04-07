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
) -> None:
    """Genera un file Turtle DCAT-AP IT da un portale CKAN.

    Examples:
      dcat-ap-it generate --config config.yml
      dcat-ap-it generate --config config.yml --output /tmp/catalog.ttl
      dcat-ap-it generate --config config.yml --dry-run
      dcat-ap-it generate --config config.yml --organizations pat,comune-trento
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

    output_path = output or Path(output_cfg.get("path", "output/catalog.ttl"))

    org_list = [o.strip() for o in organizations.split(",")] if organizations else []

    from .ckan_client import count_datasets, fetch_all_datasets
    from .mapper import build_catalog

    # Conta dataset totali per progress bar
    total = count_datasets(base_url, query_template, api_key)
    if verbose:
        console.print(f"Portale: [cyan]{base_url}[/cyan]")
        console.print(f"Dataset stimati: [cyan]{total}[/cyan]")

    datasets: list[dict] = []
    errors: list[str] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
        transient=not verbose,
    ) as progress:
        task = progress.add_task("Fetching datasets...", total=total or None)
        for ds in fetch_all_datasets(base_url, query_template, rows_per_page, api_key):
            if ds.get("title"):
                datasets.append(ds)
            else:
                errors.append(ds.get("id", "unknown"))
            progress.update(task, advance=1)

    if dry_run:
        n_dist = sum(len(ds.get("resources") or []) for ds in datasets)
        _print_summary(base_url, output_path, len(datasets), n_dist, 0, dry_run=True)
        raise typer.Exit(0)

    start_time = time.time()

    if org_list:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        for org in org_list:
            org_datasets = [d for d in datasets if _dataset_org(d) == org]
            g = build_catalog(cfg, org_datasets, base_url)
            org_path = output_path.parent / f"{org}.ttl"
            g.serialize(destination=str(org_path), format="turtle")
            n_dist = sum(len(d.get("resources") or []) for d in org_datasets)
            if verbose:
                console.print(f"  [green]✓[/green] {org_path} — {len(org_datasets)} dataset, {n_dist} distribuzioni")
    else:
        g = build_catalog(cfg, datasets, base_url)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        g.serialize(destination=str(output_path), format="turtle")

    duration = int(time.time() - start_time)
    n_dist = sum(len(ds.get("resources") or []) for ds in datasets)

    if verbose:
        _print_summary(base_url, output_path, len(datasets), n_dist, duration)
    else:
        # Output strutturato per agenti
        console.print(
            f"generated {output_path}  "
            f"datasets={len(datasets)} "
            f"distributions={n_dist} "
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    app()
