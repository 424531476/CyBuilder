import os
import shutil
import subprocess
import concurrent.futures
from pathlib import Path
from typing import List, Tuple

from CyBuilder.utils import create_setup_py, create_progress_bar, update_progress, close_progress


def compile_batch(
    batch_files: List[Path],
    build_dir: Path,
    project_root: Path,
    boundscheck: bool,
    wraparound: bool,
    batch_index: int,
) -> dict:
    """
    编译一批文件（供并行调用）
    返回: {'success': bool, 'files': List[str], 'pyd_files': List[Path], 'error': str or None}
    """
    batch_build_dir = build_dir / f"batch_{batch_index}"
    batch_build_dir.mkdir(parents=True, exist_ok=True)

    try:
        for py_file in batch_files:
            rel_path = py_file.relative_to(project_root)
            target_path = batch_build_dir / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(py_file, target_path)

        create_setup_py(batch_build_dir, batch_files, project_root, boundscheck, wraparound)

        original_dir = os.getcwd()
        try:
            os.chdir(batch_build_dir)
            result = subprocess.run(
                ["uv", "run", "python", "setup.py", "build_ext", "--inplace"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return {
                    "success": False,
                    "files": [str(f.relative_to(project_root)) for f in batch_files],
                    "pyd_files": [],
                    "error": result.stderr,
                }
        finally:
            os.chdir(original_dir)

        pyd_files = []
        for ext in ("*.pyd", "*.so"):
            for f in batch_build_dir.rglob(ext):
                if "build" not in f.relative_to(batch_build_dir).parts[:-1]:
                    pyd_files.append(f)

        return {
            "success": True,
            "files": [str(f.relative_to(project_root)) for f in batch_files],
            "pyd_files": pyd_files,
            "error": None,
        }
    except Exception as e:
        return {
            "success": False,
            "files": [str(f.relative_to(project_root)) for f in batch_files],
            "pyd_files": [],
            "error": str(e),
        }


def parallel_compile(
    py_files: List[Path],
    build_dir: Path,
    project_root: Path,
    max_workers: int,
    boundscheck: bool,
    wraparound: bool,
    show_progress: bool = True,
) -> Tuple[List[Path], List[str]]:
    """
    并行编译多个文件
    返回: (成功编译的 .pyd 文件列表, 错误信息列表)
    """
    # 按文件大小降序排列，贪心分配到最小总大小的批次
    sorted_files = sorted(py_files, key=lambda f: f.stat().st_size, reverse=True)
    batches = [[] for _ in range(max_workers)]
    batch_sizes = [0] * max_workers
    for py_file in sorted_files:
        idx = batch_sizes.index(min(batch_sizes))
        batches[idx].append(py_file)
        batch_sizes[idx] += py_file.stat().st_size
    batches = [b for b in batches if b]

    pbar = create_progress_bar(len(py_files), "并行编译", show_progress)
    all_pyd_files = []
    errors = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for idx, batch in enumerate(batches):
            future = executor.submit(
                compile_batch,
                batch, build_dir, project_root,
                boundscheck, wraparound, idx,
            )
            futures[future] = idx

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            update_progress(pbar, len(result["files"]))
            if result["success"]:
                all_pyd_files.extend(result["pyd_files"])
            else:
                errors.append(result["error"])

    close_progress(pbar)
    return all_pyd_files, errors


def sequential_compile(
    py_files: List[Path],
    build_dir: Path,
    project_root: Path,
    boundscheck: bool,
    wraparound: bool,
    show_progress: bool = True,
) -> Tuple[List[Path], List[str]]:
    """
    串行编译多个文件
    返回: (成功编译的 .pyd 文件列表, 错误信息列表)
    """
    pbar = create_progress_bar(len(py_files), "编译文件", show_progress)
    all_pyd_files = []
    errors = []

    result = compile_batch(
        py_files, build_dir, project_root,
        boundscheck, wraparound, 0,
    )
    update_progress(pbar, len(py_files))
    if result["success"]:
        all_pyd_files.extend(result["pyd_files"])
    else:
        errors.append(result["error"])

    close_progress(pbar)
    return all_pyd_files, errors
