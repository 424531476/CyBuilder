import os
import re
import shutil
import subprocess
import multiprocessing
from pathlib import Path

from CyBuilder.incremental import (
    calculate_file_hash,
    load_build_cache,
    save_build_cache,
    get_changed_files,
)
from CyBuilder.parallel import parallel_compile, sequential_compile
from CyBuilder.config import normalize_entry_files
from CyBuilder.utils import (
    find_python_files,
    copy_non_python_files,
    copy_entry_files,
    create_progress_bar,
    update_progress,
    close_progress,
)


def compile_to_pyd(project_root: Path, config: dict):
    """
    主编译函数：将所有 .py 文件编译为 .pyd

    Args:
        project_root: 项目根目录
        config: 合并后的配置字典
    """
    output_dir = config["output"]
    entry_files = normalize_entry_files(config["entry"])
    boundscheck = config["boundscheck"]
    wraparound = config["wraparound"]
    max_workers = config["jobs"]
    incremental = config["incremental"]
    sequential = config["sequential"]
    show_progress = config["progress"]
    extra_exclude = config.get("exclude", [])

    print("=" * 60)
    print("CyBuilder 项目编译器")
    print("=" * 60)

    # 1. 加载构建缓存
    cache_data = load_build_cache(project_root) if incremental else None
    compiler_options = {"boundscheck": boundscheck, "wraparound": wraparound}

    # 2. 查找 Python 文件
    print("\n[1/10] 扫描 Python 文件...")
    py_files = find_python_files(
        project_root,
        entry_files=entry_files,
        extra_exclude=extra_exclude,
        show_progress=show_progress,
    )

    # 3. 增量编译筛选
    dist_dir = project_root / output_dir
    files_to_compile = py_files
    if incremental and cache_data is not None:
        files_to_compile, skipped = get_changed_files(
            py_files, cache_data, project_root, dist_dir, compiler_options
        )
        if skipped:
            print(f"  [SKIP] 跳过 {len(skipped)} 个未变化的文件")
    elif not incremental:
        print("  [SKIP] 增量编译已禁用，将编译所有文件")

    print(f"  找到 {len(files_to_compile)} 个需要编译的 Python 文件")
    if entry_files:
        print(f"  入口文件: {', '.join(entry_files)} (不编译，直接复制)")

    if not files_to_compile and not entry_files:
        print("  [WARN] 未找到需要编译的文件")
        return

    is_incremental = incremental and cache_data is not None and dist_dir.exists()

    if not is_incremental:
        # 全量编译：清空 dist
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
    dist_dir.mkdir(exist_ok=True)

    pyd_files = []
    compiled_dist_map = {}

    if files_to_compile:
        # 4. 准备构建环境
        print("\n[2/10] 准备构建环境...")
        build_dir = project_root / "build"
        if not is_incremental:
            # 全量编译：清空 build
            if build_dir.exists():
                shutil.rmtree(build_dir)
        build_dir.mkdir(exist_ok=True)

        # 5. 安装编译依赖
        print("\n[3/10] 检查编译依赖...")
        try:
            subprocess.run(
                ["uv", "pip", "install", "cython", "setuptools"],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"\n  [ERROR] 安装依赖失败: {e}")
            return

        # 6. 编译
        if sequential or max_workers == 1:
            print(f"\n[4/10] 串行编译 ({len(files_to_compile)} 个文件)...")
            pyd_files, errors = sequential_compile(
                files_to_compile, build_dir, project_root,
                boundscheck, wraparound, show_progress,
            )
        else:
            if max_workers is None:
                max_workers = multiprocessing.cpu_count()
            print(f"\n[4/10] 并行编译 ({len(files_to_compile)} 个文件, {max_workers} 进程)...")
            pyd_files, errors = parallel_compile(
                files_to_compile, build_dir, project_root,
                max_workers, boundscheck, wraparound, show_progress,
            )

        if errors:
            print(f"\n  [WARN] {len(errors)} 个批次编译失败:")
            for err in errors[:3]:
                for line in err.strip().split("\n")[:5]:
                    print(f"    {line}")
                print("    ...")

        # 7. 整理编译结果
        print("\n[5/10] 整理编译结果...")
        if not pyd_files:
            print("  [WARN] 未找到编译生成的 .pyd/.so 文件")
            return
        print(f"  找到 {len(pyd_files)} 个编译文件")

        # 8. 复制到 dist 目录
        print("\n[6/10] 复制编译文件...")
        # 记录 {源文件相对路径: dist中.pyd路径}，用于更新缓存
        compiled_dist_map = {}
        pbar = create_progress_bar(len(pyd_files), "复制文件", show_progress)
        for pyd_file in pyd_files:
            # 去掉 batch_N/ 前缀，得到相对于项目结构的路径
            parts = pyd_file.relative_to(build_dir).parts
            if parts[0].startswith("batch_"):
                rel_path = Path(*parts[1:])
            else:
                rel_path = Path(*parts)
            target_path = dist_dir / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pyd_file, target_path)
            # 反推源文件相对路径: my.module.cp314-win_amd64.pyd -> my.module.py
            stem = re.sub(r'\.(cpython|cp)\d+[-_].*', '', rel_path.stem)
            src_rel = str(rel_path.parent / (stem + ".py"))
            compiled_dist_map[src_rel] = target_path
            update_progress(pbar)
        close_progress(pbar)

    # 9. 复制配置文件
    print("\n[7/10] 复制配置文件...")
    copy_non_python_files(project_root, dist_dir, show_progress)

    # 10. 复制入口文件
    if entry_files:
        print("\n[8/10] 复制入口文件...")
        copy_entry_files(project_root, dist_dir, entry_files)

    # 11. 清理临时文件
    print("\n[9/10] 清理临时文件...")
    build_dir = project_root / "build"
    if build_dir.exists():
        if is_incremental:
            # 增量模式：保留缓存文件，删除其余内容
            for item in build_dir.iterdir():
                if item.name == ".CyBuilder_cache.json":
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            print("  [OK] 增量编译，保留缓存文件")
        else:
            # 全量模式：删除整个 build 目录
            shutil.rmtree(build_dir)

    # 12. 更新缓存
    if incremental and cache_data is not None:
        files = cache_data.get("files", {})
        current_paths = set()

        for py_file in py_files:
            rel_path = str(py_file.relative_to(project_root))
            current_paths.add(rel_path)
            try:
                h = calculate_file_hash(py_file)
            except (OSError, IOError):
                continue

            entry = files.get(rel_path, {})
            entry["hash"] = h
            # 本次编译的文件更新 dist 修改时间
            if rel_path in compiled_dist_map:
                entry["dist_mtime"] = os.path.getmtime(compiled_dist_map[rel_path])
            files[rel_path] = entry

        # 移除已删除源文件的缓存条目
        for key in list(files.keys()):
            if key not in current_paths:
                del files[key]

        cache_data["files"] = files
        cache_data["compiler_options"] = compiler_options
        save_build_cache(project_root, cache_data)

    # 13. 完成
    print("\n[10/10] 完成")
    print("=" * 60)
    print(f"[OK] 完成！结果保存在: {dist_dir}")
    if pyd_files:
        print(f"  - {len(pyd_files)} 个编译文件 (.pyd/.so)")
    if files_to_compile and incremental and cache_data is not None:
        skipped_count = len(py_files) - len(files_to_compile)
        if skipped_count > 0:
            print(f"  - 增量编译：跳过 {skipped_count} 个文件")
    print(f"  - 配置文件已复制")
    if entry_files:
        print(f"  - 入口文件: {', '.join(entry_files)}")
    print("=" * 60)
