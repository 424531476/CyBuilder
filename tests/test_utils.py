import shutil
from pathlib import Path

import pytest

from CyBuilder.utils import (
    find_python_files,
    copy_non_python_files,
    copy_entry_files,
    create_setup_py,
    create_progress_bar,
    update_progress,
    close_progress,
)


class TestFindPythonFiles:
    def test_basic(self, tmp_project):
        result = find_python_files(tmp_project, show_progress=False)
        names = {f.name for f in result}
        assert "main.py" in names
        assert "utils.py" in names
        assert "user.py" in names

    def test_excludes_default_dirs(self, tmp_project):
        result = find_python_files(tmp_project, show_progress=False)
        names = {f.name for f in result}
        # tests/ 目录应被排除
        assert "test_something.py" not in names
        # dist/ 目录应被排除（且 .pyd 不是 .py 文件）
        assert "old.pyd" not in names

    def test_extra_exclude_glob(self, tmp_project):
        result = find_python_files(
            tmp_project, extra_exclude=["models/*"], show_progress=False
        )
        names = {f.name for f in result}
        assert "user.py" not in names
        assert "main.py" in names

    def test_entry_files_excluded(self, tmp_project):
        result = find_python_files(
            tmp_project, entry_files=["main.py"], show_progress=False
        )
        names = {f.name for f in result}
        assert "main.py" not in names
        assert "utils.py" in names


class TestCopyNonPythonFiles:
    def test_copies_supported_extensions(self, tmp_project, tmp_dist):
        copy_non_python_files(tmp_project, tmp_dist, show_progress=False)
        assert (tmp_dist / "README.md").exists()
        assert (tmp_dist / "config.json").exists()
        content = (tmp_dist / "README.md").read_text(encoding="utf-8")
        assert content == "# My Project\n"

    def test_excludes_CyBuilder_files(self, tmp_project, tmp_dist):
        copy_non_python_files(tmp_project, tmp_dist, show_progress=False)
        assert not (tmp_dist / ".CyBuilder.toml").exists()

    def test_excludes_python_files(self, tmp_project, tmp_dist):
        copy_non_python_files(tmp_project, tmp_dist, show_progress=False)
        assert not (tmp_dist / "main.py").exists()

    def test_preserves_directory_structure(self, tmp_project, tmp_dist):
        # 创建子目录中的非 Python 文件
        (tmp_project / "assets").mkdir()
        (tmp_project / "assets" / "logo.png").write_bytes(b"\x89PNG")
        copy_non_python_files(tmp_project, tmp_dist, show_progress=False)
        assert (tmp_dist / "assets" / "logo.png").exists()


class TestCopyEntryFiles:
    def test_existing_entry(self, tmp_project, tmp_dist):
        copy_entry_files(tmp_project, tmp_dist, ["main.py"])
        assert (tmp_dist / "main.py").exists()
        content = (tmp_dist / "main.py").read_text(encoding="utf-8")
        assert "hello" in content

    def test_missing_entry(self, tmp_project, tmp_dist, capsys):
        copy_entry_files(tmp_project, tmp_dist, ["nonexistent.py"])
        assert not (tmp_dist / "nonexistent.py").exists()
        captured = capsys.readouterr()
        assert "WARN" in captured.out

    def test_multiple_entries(self, tmp_project, tmp_dist):
        copy_entry_files(tmp_project, tmp_dist, ["main.py", "utils.py"])
        assert (tmp_dist / "main.py").exists()
        assert (tmp_dist / "utils.py").exists()


class TestCreateSetupPy:
    def test_generates_valid_setup(self, tmp_path):
        py_files = [tmp_path / "module.py"]
        (tmp_path / "module.py").write_text("x = 1\n")
        create_setup_py(tmp_path, py_files, tmp_path, boundscheck=True, wraparound=False)
        setup_file = tmp_path / "setup.py"
        assert setup_file.exists()
        content = setup_file.read_text(encoding="utf-8")
        assert "cythonize" in content
        assert "module" in content
        assert "'boundscheck': True" in content
        assert "'wraparound': False" in content

    def test_multiple_modules(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 2\n")
        py_files = [tmp_path / "a.py", tmp_path / "b.py"]
        create_setup_py(tmp_path, py_files, tmp_path)
        content = (tmp_path / "setup.py").read_text(encoding="utf-8")
        assert '"a"' in content
        assert '"b"' in content

    def test_nested_module_names(self, tmp_path):
        sub = tmp_path / "pkg"
        sub.mkdir()
        (sub / "mod.py").write_text("z = 3\n")
        py_files = [sub / "mod.py"]
        create_setup_py(tmp_path, py_files, tmp_path)
        content = (tmp_path / "setup.py").read_text(encoding="utf-8")
        assert "pkg.mod" in content


class TestProgressBar:
    def test_create_enabled(self):
        pbar = create_progress_bar(10, "test", enabled=True)
        assert pbar is not None
        pbar.close()

    def test_create_disabled(self):
        pbar = create_progress_bar(10, "test", enabled=False)
        assert pbar is None

    def test_update_none(self):
        # 不应抛出异常
        update_progress(None, 1)

    def test_close_none(self):
        # 不应抛出异常
        close_progress(None)

    def test_update_with_postfix(self):
        pbar = create_progress_bar(10, "test", enabled=True)
        update_progress(pbar, 1, {"key": "value"})
        pbar.close()
