import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from CyBuilder.parallel import compile_batch


class TestCompileBatch:
    def _setup_batch_dir(self, tmp_path):
        """创建编译批次所需的目录结构"""
        project_root = tmp_path / "project"
        project_root.mkdir()
        build_dir = tmp_path / "build"
        build_dir.mkdir()

        # 创建源文件
        (project_root / "mod_a.py").write_text("x = 1\n", encoding="utf-8")
        (project_root / "mod_b.py").write_text("y = 2\n", encoding="utf-8")
        py_files = [project_root / "mod_a.py", project_root / "mod_b.py"]

        return project_root, build_dir, py_files

    @patch("CyBuilder.parallel.subprocess.run")
    def test_success(self, mock_run, tmp_path):
        project_root, build_dir, py_files = self._setup_batch_dir(tmp_path)

        # 模拟编译成功：在 batch 目录中创建 .pyd 文件
        def side_effect(*args, **kwargs):
            # subprocess.run 被调用后，需要在 batch 目录中创建 pyd 文件
            batch_dir = build_dir / "batch_0"
            if batch_dir.exists():
                (batch_dir / "mod_a.cp314-win_amd64.pyd").write_bytes(b"\x00")
                (batch_dir / "mod_b.cp314-win_amd64.pyd").write_bytes(b"\x00")
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        mock_run.side_effect = side_effect

        result = compile_batch(
            py_files, build_dir, project_root,
            boundscheck=True, wraparound=True, batch_index=0,
        )

        assert result["success"] is True
        assert len(result["pyd_files"]) == 2
        assert result["error"] is None
        assert len(result["files"]) == 2

    @patch("CyBuilder.parallel.subprocess.run")
    def test_failure(self, mock_run, tmp_path):
        project_root, build_dir, py_files = self._setup_batch_dir(tmp_path)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Compilation error: syntax error"
        mock_run.return_value = mock_result

        result = compile_batch(
            py_files, build_dir, project_root,
            boundscheck=True, wraparound=True, batch_index=0,
        )

        assert result["success"] is False
        assert result["pyd_files"] == []
        assert "syntax error" in result["error"]

    @patch("CyBuilder.parallel.subprocess.run")
    def test_creates_batch_dir(self, mock_run, tmp_path):
        project_root, build_dir, py_files = self._setup_batch_dir(tmp_path)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "fail"
        mock_run.return_value = mock_result

        compile_batch(
            py_files, build_dir, project_root,
            boundscheck=True, wraparound=True, batch_index=3,
        )

        batch_dir = build_dir / "batch_3"
        assert batch_dir.exists()

    @patch("CyBuilder.parallel.subprocess.run")
    def test_exception_returns_failure(self, mock_run, tmp_path):
        project_root, build_dir, py_files = self._setup_batch_dir(tmp_path)

        mock_run.side_effect = OSError("uv not found")

        result = compile_batch(
            py_files, build_dir, project_root,
            boundscheck=True, wraparound=True, batch_index=0,
        )

        assert result["success"] is False
        assert "uv not found" in result["error"]

    @patch("CyBuilder.parallel.subprocess.run")
    def test_copies_source_files_to_batch_dir(self, mock_run, tmp_path):
        project_root, build_dir, py_files = self._setup_batch_dir(tmp_path)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "fail"
        mock_run.return_value = mock_result

        compile_batch(
            py_files, build_dir, project_root,
            boundscheck=True, wraparound=True, batch_index=0,
        )

        batch_dir = build_dir / "batch_0"
        assert (batch_dir / "mod_a.py").exists()
        assert (batch_dir / "mod_b.py").exists()
        # setup.py 也应该被创建
        assert (batch_dir / "setup.py").exists()
