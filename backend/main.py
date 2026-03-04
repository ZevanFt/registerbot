"""CLI entrypoint for register-bot."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from src.config.settings import load_settings
from src.pipeline import Pipeline, PipelineContext, PipelineRunner
from src.steps import (
    CreateTempEmailStep,
    SetPasswordStep,
    SetProfileStep,
    SubmitRegistrationStep,
    UpgradePlusStep,
    VerifyEmailStep,
    VerifyPhoneStep,
    WaitForVerificationCodeStep,
)
from src.storage.account_store import AccountStore
from src.utils.logger import setup_logger

console = Console()


def _build_step_registry() -> dict[str, object]:
    return {
        "create_temp_email": CreateTempEmailStep(),
        "submit_registration": SubmitRegistrationStep(),
        "wait_for_verification_code": WaitForVerificationCodeStep(),
        "verify_email": VerifyEmailStep(),
        "verify_phone": VerifyPhoneStep(),
        "set_password": SetPasswordStep(),
        "set_profile": SetProfileStep(),
        "upgrade_plus": UpgradePlusStep(),
    }


def _build_pipeline() -> Pipeline:
    steps = list(_build_step_registry().values())
    return Pipeline(
        name="openai_register",
        description="Complete OpenAI registration flow",
        steps=steps,
    )


def _load_store() -> AccountStore:
    settings = load_settings()
    return AccountStore(settings.storage.db_path, settings.storage.encryption_key)


@click.group()
def cli() -> None:
    """register-bot command line interface."""


@cli.command("run")
def run_pipeline() -> None:
    """Run full registration pipeline."""

    settings = load_settings()
    logger = setup_logger("main", settings.logging.level)
    context = PipelineContext(metadata={"settings": settings})
    pipeline = _build_pipeline()
    runner = PipelineRunner()
    result = asyncio.run(runner.run(pipeline, context))

    if result.success:
        console.print("[green]Pipeline completed successfully[/green]")
    else:
        console.print("[red]Pipeline failed[/red]")
    console.print(result)
    logger.info("pipeline_finished", success=result.success, completed=result.steps_completed)


@cli.command("step")
@click.argument("name")
def run_single_step(name: str) -> None:
    """Run one pipeline step by name."""

    settings = load_settings()
    registry = _build_step_registry()
    step = registry.get(name)
    if step is None:
        raise click.ClickException(f"Unknown step: {name}")

    context = PipelineContext(metadata={"settings": settings})
    runner = PipelineRunner()
    result = asyncio.run(runner.run_step(step, context))
    console.print(result)


@cli.command("list")
def list_steps() -> None:
    """List all available steps."""

    table = Table(title="Available Steps")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="magenta")
    for name, step in _build_step_registry().items():
        table.add_row(name, getattr(step, "description", ""))
    console.print(table)


def _render_accounts() -> None:
    """Render accounts list table."""

    """List all saved accounts."""

    store = _load_store()
    items = store.list_accounts()
    table = Table(title="Accounts")
    table.add_column("ID")
    table.add_column("Email")
    table.add_column("Plan")
    table.add_column("Status")
    for item in items:
        table.add_row(str(item["id"]), str(item["email"]), str(item["plan"]), str(item["status"]))
    console.print(table)


@cli.group("accounts", invoke_without_command=True)
@click.pass_context
def accounts(ctx: click.Context) -> None:
    """Inspect stored accounts."""

    if ctx.invoked_subcommand is None:
        _render_accounts()


@accounts.command("show")
@click.argument("account_id", type=int)
def show_account(account_id: int) -> None:
    """Show account details by id."""

    store = _load_store()
    item = store.get_account(account_id)
    if item is None:
        raise click.ClickException(f"Account not found: {account_id}")
    console.print(item)


if __name__ == "__main__":
    if not Path("config/settings.yaml").exists():
        console.print("[yellow]Tip: copy config/settings.yaml.example -> config/settings.yaml[/yellow]")
    cli()
