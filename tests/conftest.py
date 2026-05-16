import shutil
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path):
    """创建一个临时项目目录，包含基本的 .py 文件结构"""
    project = tmp_path / "myproject"
    project.mkdir()

    # 创建源文件
    (project / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (project / "utils.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    (project / "models").mkdir()
    (project / "models" / "__init__.py").write_text("", encoding="utf-8")
    (project / "models" / "user.py").write_text("class User: pass\n", encoding="utf-8")

    # 创建非 Python 文件
    (project / "README.md").write_text("# My Project\n", encoding="utf-8")
    (project / "config.json").write_text('{"key": "value"}\n', encoding="utf-8")
    (project / ".CyBuilder.toml").write_text(
        '[build]\noutput = "dist"\nentry = ["main.py"]\n',
        encoding="utf-8",
    )

    # 创建应被排除的目录
    (project / "dist").mkdir()
    (project / "dist" / "old.pyd").write_bytes(b"\x00")
    (project / "build").mkdir()
    (project / ".venv").mkdir()
    (project / "__pycache__").mkdir()
    (project / "tests").mkdir()
    (project / "tests" / "test_something.py").write_text("pass\n", encoding="utf-8")

    return project


@pytest.fixture
def tmp_dist(tmp_path):
    """创建一个临时 dist 目录"""
    dist = tmp_path / "dist"
    dist.mkdir()
    return dist


@pytest.fixture
def sample_py_files(tmp_project):
    """返回临时项目中的 .py 文件列表（不含排除目录中的）"""
    return [
        tmp_project / "main.py",
        tmp_project / "utils.py",
        tmp_project / "models" / "__init__.py",
        tmp_project / "models" / "user.py",
    ]
