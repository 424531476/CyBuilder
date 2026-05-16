import hashlib
import json
import os
from pathlib import Path
from typing import List, Tuple
from datetime import datetime


def calculate_file_hash(file_path: Path) -> str:
    """计算文件的 SHA256 哈希值"""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _cache_path(project_root: Path) -> Path:
    """缓存文件路径：build/.CyBuilder_cache.json"""
    return project_root / "build" / ".CyBuilder_cache.json"


def load_build_cache(project_root: Path) -> dict:
    """加载构建缓存文件"""
    path = _cache_path(project_root)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"version": "2.0", "files": {}, "compiler_options": {}}


def save_build_cache(project_root: Path, cache_data: dict):
    """保存构建缓存文件到 build/.CyBuilder_cache.json"""
    path = _cache_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    cache_data["last_build_time"] = datetime.now().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)


def get_changed_files(
    py_files: List[Path],
    cache_data: dict,
    project_root: Path,
    dist_dir: Path,
    compiler_options: dict
) -> Tuple[List[Path], List[Path]]:
    """
    获取需要编译的文件列表
    检查三个条件：
      1. 源文件哈希是否变化
      2. dist 中对应的 .pyd 文件是否存在
      3. dist 中 .pyd 文件的修改时间是否与缓存一致
    返回: (需要编译的文件, 可以跳过的文件)
    """
    cached_files = cache_data.get("files", {})
    cached_options = cache_data.get("compiler_options", {})

    # 编译选项变化时全量编译
    if cached_options != compiler_options:
        return py_files, []

    changed = []
    unchanged = []
    for py_file in py_files:
        rel_path = str(py_file.relative_to(project_root))
        entry = cached_files.get(rel_path)

        # 条件 1: 源文件哈希变化
        try:
            current_hash = calculate_file_hash(py_file)
        except (OSError, IOError):
            changed.append(py_file)
            continue

        if entry is None or entry.get("hash") != current_hash:
            changed.append(py_file)
            continue

        # 条件 2: dist 中对应的编译文件不存在（文件名含平台标签，如 module.cp314-win_amd64.pyd 或 module.cpython-310-x86_64-linux-gnu.so）
        stem = Path(rel_path).stem
        pyd_dir = dist_dir / Path(rel_path).parent
        
        # 同时查找 .pyd (Windows) 和 .so (Linux/Mac) 文件
        matches = []
        if pyd_dir.exists():
            matches.extend(list(pyd_dir.glob(f"{stem}*.pyd")))
            matches.extend(list(pyd_dir.glob(f"{stem}*.so")))
        
        if not matches:
            changed.append(py_file)
            continue

        # 条件 3: dist 中 .pyd 文件修改时间不匹配
        try:
            actual_mtime = os.path.getmtime(matches[0])
            cached_mtime = entry.get("dist_mtime", 0)
            if abs(actual_mtime - cached_mtime) > 1.0:
                changed.append(py_file)
                continue
        except OSError:
            changed.append(py_file)
            continue

        unchanged.append(py_file)

    return changed, unchanged


