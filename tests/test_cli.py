"""Tests for the CLI entry point."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from paper_boy.cli import cli
from paper_boy.main import BuildResult


# --- Helpers ---


def _make_build_result(epub_path="/tmp/paper-boy-2026-03-01.epub"):
    """Create a mock BuildResult."""
    return BuildResult(
        epub_path=Path(epub_path),
        sections=[],
        total_articles=5,
    )


# --- TestCliGroup ---


class TestCliGroup:
    def test_help_output(self):
        """--help shows usage information."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Paper Boy News" in result.output

    def test_verbose_flag_accepted(self):
        """--help with -v flag does not error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["-v", "--help"])
        assert result.exit_code == 0


# --- TestBuildCommand ---


class TestBuildCommand:
    @patch("paper_boy.cli.build", name="build_cmd")
    def test_build_help(self, mock_build_cmd):
        """build --help shows usage."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--help"])
        assert result.exit_code == 0
        assert "Build" in result.output or "build" in result.output.lower()

    @patch("paper_boy.main.build_newspaper")
    @patch("paper_boy.cli.load_config")
    def test_build_success_prints_path(self, mock_load, mock_build):
        """Successful build prints the epub path."""
        mock_load.return_value = MagicMock()
        mock_build.return_value = _make_build_result()

        runner = CliRunner()
        result = runner.invoke(cli, ["build", "-c", "test.yaml"])

        assert result.exit_code == 0
        assert "paper-boy-2026-03-01.epub" in result.output

    @patch("paper_boy.main.build_newspaper")
    @patch("paper_boy.cli.load_config")
    def test_build_with_custom_config(self, mock_load, mock_build):
        """--config flag forwards to load_config."""
        mock_load.return_value = MagicMock()
        mock_build.return_value = _make_build_result()

        runner = CliRunner()
        runner.invoke(cli, ["build", "-c", "custom.yaml"])

        mock_load.assert_called_once_with("custom.yaml")

    @patch("paper_boy.main.build_newspaper")
    @patch("paper_boy.cli.load_config")
    def test_build_with_output_path(self, mock_load, mock_build):
        """--output flag forwards to build_newspaper."""
        mock_load.return_value = MagicMock()
        mock_build.return_value = _make_build_result()

        runner = CliRunner()
        runner.invoke(cli, ["build", "-c", "t.yaml", "-o", "/tmp/out.epub"])

        mock_build.assert_called_once()
        _, kwargs = mock_build.call_args
        assert kwargs.get("output_path") == "/tmp/out.epub" or mock_build.call_args[0][1] == "/tmp/out.epub"

    @patch("paper_boy.cli.load_config", side_effect=FileNotFoundError("not found"))
    def test_build_config_not_found_exits_1(self, mock_load):
        """FileNotFoundError from load_config causes exit 1."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "-c", "missing.yaml"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    @patch("paper_boy.main.build_newspaper", side_effect=RuntimeError("No articles"))
    @patch("paper_boy.cli.load_config")
    def test_build_runtime_error_exits_1(self, mock_load, mock_build):
        """RuntimeError during build causes exit 1."""
        mock_load.return_value = MagicMock()

        runner = CliRunner()
        result = runner.invoke(cli, ["build"])

        assert result.exit_code == 1


# --- TestDeliverCommand ---


class TestDeliverCommand:
    @patch("paper_boy.main.build_and_deliver")
    @patch("paper_boy.cli.load_config")
    def test_deliver_success_prints_path(self, mock_load, mock_deliver):
        """Successful deliver prints confirmation."""
        mock_load.return_value = MagicMock()
        mock_deliver.return_value = _make_build_result()

        runner = CliRunner()
        result = runner.invoke(cli, ["deliver", "-c", "test.yaml"])

        assert result.exit_code == 0
        assert "delivered" in result.output.lower() or "paper-boy" in result.output.lower()

    @patch("paper_boy.main.build_and_deliver")
    @patch("paper_boy.cli.load_config")
    def test_deliver_with_custom_config(self, mock_load, mock_deliver):
        """--config flag forwards to load_config."""
        mock_load.return_value = MagicMock()
        mock_deliver.return_value = _make_build_result()

        runner = CliRunner()
        runner.invoke(cli, ["deliver", "-c", "my-config.yaml"])

        mock_load.assert_called_once_with("my-config.yaml")

    @patch("paper_boy.cli.load_config", side_effect=Exception("boom"))
    def test_deliver_error_exits_1(self, mock_load):
        """Exception causes exit code 1."""
        runner = CliRunner()
        result = runner.invoke(cli, ["deliver"])

        assert result.exit_code == 1
