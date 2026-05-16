import argparse
from pathlib import Path

import pytest

from CyBuilder.config import (
    _UNSET,
    get_default_config,
    load_config_file,
    merge_config_with_args,
    normalize_entry_files,
)


class TestGetDefaultConfig:
    def test_returns_expected_keys(self):
        config = get_default_config()
        assert config["output"] == "dist"
        assert config["entry"] == ["main.py"]
        assert config["boundscheck"] is True
        assert config["wraparound"] is True
        assert config["jobs"] is None
        assert config["incremental"] is True
        assert config["progress"] is True
        assert config["sequential"] is False
        assert config["exclude"] == []
        assert config["verbose"] is False
        assert config["quiet"] is False


class TestLoadConfigFile:
    def test_no_file(self, tmp_path):
        result = load_config_file(tmp_path)
        assert result == {}

    def test_with_build_section(self, tmp_path):
        (tmp_path / ".CyBuilder.toml").write_text(
            '[build]\noutput = "release"\nentry = ["app.py"]\n',
            encoding="utf-8",
        )
        result = load_config_file(tmp_path)
        assert result["output"] == "release"
        assert result["entry"] == ["app.py"]

    def test_with_display_section(self, tmp_path):
        (tmp_path / ".CyBuilder.toml").write_text(
            "[display]\nprogress = false\nverbose = true\n",
            encoding="utf-8",
        )
        result = load_config_file(tmp_path)
        assert result["progress"] is False
        assert result["verbose"] is True

    def test_both_sections(self, tmp_path):
        (tmp_path / ".CyBuilder.toml").write_text(
            '[build]\noutput = "release"\n[display]\nprogress = false\n',
            encoding="utf-8",
        )
        result = load_config_file(tmp_path)
        assert result["output"] == "release"
        assert result["progress"] is False

    def test_CyBuilder_toml_fallback(self, tmp_path):
        """优先 .CyBuilder.toml，其次 CyBuilder.toml"""
        (tmp_path / "CyBuilder.toml").write_text(
            '[build]\noutput = "from_CyBuilder"\n',
            encoding="utf-8",
        )
        result = load_config_file(tmp_path)
        assert result["output"] == "from_CyBuilder"

    def test_CyBuilder_toml_takes_priority(self, tmp_path):
        (tmp_path / ".CyBuilder.toml").write_text(
            '[build]\noutput = "dotfile"\n',
            encoding="utf-8",
        )
        (tmp_path / "CyBuilder.toml").write_text(
            '[build]\noutput = "regular"\n',
            encoding="utf-8",
        )
        result = load_config_file(tmp_path)
        assert result["output"] == "dotfile"

    def test_invalid_toml(self, tmp_path):
        (tmp_path / ".CyBuilder.toml").write_text("not valid toml [[[[", encoding="utf-8")
        result = load_config_file(tmp_path)
        assert result == {}


class TestNormalizeEntryFiles:
    def test_none(self):
        assert normalize_entry_files(None) == []

    def test_single_string(self):
        assert normalize_entry_files("main.py") == ["main.py"]

    def test_comma_separated(self):
        result = normalize_entry_files("main.py,cli.py")
        assert result == ["main.py", "cli.py"]

    def test_comma_with_spaces(self):
        result = normalize_entry_files("main.py , cli.py , web.py")
        assert result == ["main.py", "cli.py", "web.py"]

    def test_list_input(self):
        result = normalize_entry_files(["main.py", "cli.py"])
        assert result == ["main.py", "cli.py"]

    def test_list_with_comma_items(self):
        result = normalize_entry_files(["main.py,cli.py", "web.py"])
        assert result == ["main.py", "cli.py", "web.py"]

    def test_dedup_preserves_order(self):
        result = normalize_entry_files(["main.py", "cli.py", "main.py"])
        assert result == ["main.py", "cli.py"]

    def test_empty_string(self):
        assert normalize_entry_files("") == []

    def test_empty_list(self):
        assert normalize_entry_files([]) == []


class TestMergeConfigWithArgs:
    def _make_args(self, **kwargs):
        """创建一个模拟的 argparse.Namespace"""
        defaults = {
            "output": None,
            "entry": None,
            "boundscheck": _UNSET,
            "wraparound": _UNSET,
            "jobs": None,
            "incremental": _UNSET,
            "progress": _UNSET,
            "sequential": False,
            "exclude": None,
            "verbose": False,
            "quiet": False,
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_cli_wins_over_config(self):
        args = self._make_args(output="cli_output")
        cli_defaults = {"output": None}
        config = {"output": "file_output"}

        result = merge_config_with_args(config, args, cli_defaults)
        assert result["output"] == "cli_output"

    def test_file_config_wins_over_default(self):
        args = self._make_args()
        cli_defaults = {}
        config = {"output": "file_output"}

        result = merge_config_with_args(config, args, cli_defaults)
        assert result["output"] == "file_output"

    def test_default_fallback(self):
        args = self._make_args()
        cli_defaults = {}
        config = {}

        result = merge_config_with_args(config, args, cli_defaults)
        assert result["output"] == "dist"
        assert result["boundscheck"] is True

    def test_entry_from_cli_string(self):
        args = self._make_args(entry="a.py,b.py")
        cli_defaults = {}
        config = {}

        result = merge_config_with_args(config, args, cli_defaults)
        assert result["entry"] == ["a.py", "b.py"]

    def test_entry_from_cli_list(self):
        args = self._make_args(entry=["a.py", "b.py"])
        cli_defaults = {}
        config = {}

        result = merge_config_with_args(config, args, cli_defaults)
        assert result["entry"] == ["a.py", "b.py"]

    def test_boundscheck_explicit_false(self):
        args = self._make_args(boundscheck=False)
        cli_defaults = {"boundscheck": True}
        config = {}

        result = merge_config_with_args(config, args, cli_defaults)
        assert result["boundscheck"] is False

    def test_boundscheck_not_passed_uses_config(self):
        args = self._make_args(boundscheck=_UNSET)
        cli_defaults = {}
        config = {"boundscheck": False}

        result = merge_config_with_args(config, args, cli_defaults)
        assert result["boundscheck"] is False
