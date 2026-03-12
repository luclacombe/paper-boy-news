"""CLI entry point for Paper Boy."""

from __future__ import annotations

import logging
import sys

import click

from paper_boy.config import load_config


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool) -> None:
    """Paper Boy — Automated morning newspaper for e-readers."""
    _setup_logging(verbose)


@cli.command()
@click.option(
    "-c",
    "--config",
    "config_path",
    default="config.yaml",
    help="Path to config file.",
    type=click.Path(),
)
@click.option(
    "-o",
    "--output",
    "output_path",
    default=None,
    help="Output file path for the EPUB.",
    type=click.Path(),
)
@click.option(
    "--no-limit",
    is_flag=True,
    help="Disable article budget — fetch all articles from every source.",
)
def build(config_path: str, output_path: str | None, no_limit: bool) -> None:
    """Build the newspaper EPUB locally."""
    from paper_boy.main import build_newspaper

    try:
        config = load_config(config_path)
        if no_limit:
            config.newspaper.total_article_budget = 0
        result = build_newspaper(config, output_path)
        click.echo(f"Newspaper built: {result.epub_path}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "-c",
    "--config",
    "config_path",
    default="config.yaml",
    help="Path to config file.",
    type=click.Path(),
)
@click.option(
    "-o",
    "--output",
    "output_path",
    default=None,
    help="Output file path for the EPUB.",
    type=click.Path(),
)
@click.option(
    "--no-limit",
    is_flag=True,
    help="Disable article budget — fetch all articles from every source.",
)
def deliver(config_path: str, output_path: str | None, no_limit: bool) -> None:
    """Build the newspaper and deliver it to the configured destination."""
    from paper_boy.main import build_and_deliver

    try:
        config = load_config(config_path)
        if no_limit:
            config.newspaper.total_article_budget = 0
        result = build_and_deliver(config, output_path)
        click.echo(f"Newspaper built and delivered: {result.epub_path}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
