import os
import fnmatch
import shutil
from pathlib import Path
from typing import List

from tqdm import tqdm


# ============================================================
# 进度条
# ============================================================

def create_progress_bar(total: int, description: str = "处理中", enabled: bool = True):
    """创建进度条对象，禁用时返回 None"""
    if enabled:
        return tqdm(total=total, desc=description, unit="文件")
    return None


def update_progress(pbar, n: int = 1, postfix: dict = None):
    """更新进度条"""
    if pbar is not None:
        if postfix:
            pbar.set_postfix(postfix)
        pbar.update(n)


def close_progress(pbar):
    """关闭进度条"""
    if pbar is not None:
        pbar.close()


# ============================================================
# 文件扫描
# ============================================================

def find_python_files(
    root_dir: Path,
    exclude_dirs: List[str] = None,
    entry_files: List[str] = None,
    extra_exclude: List[str] = None,
    show_progress: bool = True,
) -> List[Path]:
    """递归查找所有 .py 文件"""
    if exclude_dirs is None:
        exclude_dirs = ["dist", "build", "build_temp", ".venv", "__pycache__", ".git", "tests"]
    if entry_files is None:
        entry_files = []
    if extra_exclude is None:
        extra_exclude = []

    all_files = list(root_dir.rglob("*.py"))
    pbar = create_progress_bar(len(all_files), "扫描文件", show_progress)

    py_files = []
    for py_file in all_files:
        rel_path_str = str(py_file.relative_to(root_dir))

        if any(excluded in py_file.parts for excluded in exclude_dirs):
            update_progress(pbar)
            continue

        if any(fnmatch.fnmatch(rel_path_str, pattern) for pattern in extra_exclude):
            update_progress(pbar)
            continue

        if rel_path_str in entry_files:
            update_progress(pbar)
            continue

        py_files.append(py_file)
        update_progress(pbar)

    close_progress(pbar)
    return py_files


# ============================================================
# 文件复制
# ============================================================

def copy_non_python_files(project_root: Path, dist_dir: Path, show_progress: bool = True):
    """复制非 Python 文件到 dist 目录（保持目录结构）"""
    include_extensions = [
        ".toml", ".md", ".txt", ".json", ".yaml", ".yml",
        ".bat", ".cfg", ".ini",
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".ico", ".webp",
        ".pyd", ".so",
    ]
    exclude_dirs = ["dist", "build", "build_temp", ".venv", "__pycache__", ".git", "tests"]
    exclude_files = {".CyBuilder_cache.json", ".CyBuilder.toml"}

    all_files = list(project_root.rglob("*"))
    pbar = create_progress_bar(len(all_files), "复制配置", show_progress)

    for file_path in all_files:
        if not file_path.is_file():
            update_progress(pbar)
            continue
        if file_path.name in exclude_files:
            update_progress(pbar)
            continue
        if any(excluded in file_path.parts for excluded in exclude_dirs):
            update_progress(pbar)
            continue

        if file_path.suffix.lower() in include_extensions or file_path.name in [".env.example"]:
            rel_path = file_path.relative_to(project_root)
            target_path = dist_dir / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, target_path)

        update_progress(pbar)

    close_progress(pbar)


def create_setup_py(build_dir: Path, py_files: List[Path], project_root: Path, boundscheck: bool = True, wraparound: bool = True):
    """创建 setup.py 用于 Cython 编译"""
    setup_content = """from setuptools import setup, Extension
from Cython.Build import cythonize
import os

extensions = []
"""

    for py_file in py_files:
        rel_path = py_file.relative_to(project_root)
        module_name = str(rel_path).replace(os.sep, ".")[:-3]
        rel_path_str = str(rel_path).replace(os.sep, "/")

        setup_content += f"""
extensions.append(Extension(
    "{module_name}",
    ["{rel_path_str}"],
))
"""

    setup_content += f"""

setup(
    ext_modules=cythonize(
        extensions,
        compiler_directives={{
            'language_level': "3",
            'boundscheck': {boundscheck},
            'wraparound': {wraparound},
        }},
        build_dir="build_temp"
    ),
)
"""

    setup_file = build_dir / "setup.py"
    setup_file.write_text(setup_content, encoding="utf-8")


def copy_entry_files(project_root: Path, dist_dir: Path, entry_files: List[str]):
    """复制多个入口文件到输出目录"""
    for entry_file in entry_files:
        entry_path = project_root / entry_file
        if entry_path.exists():
            target = dist_dir / entry_file
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry_path, target)
            print(f"  [OK] {entry_file} (未编译，可直接运行)")
        else:
            print(f"  [WARN] 入口文件 '{entry_file}' 不存在，跳过")
