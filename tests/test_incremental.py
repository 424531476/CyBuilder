import hashlib
import json
import os
from pathlib import Path

import pytest

from CyBuilder.incremental import (
    calculate_file_hash,
    load_build_cache,
    save_build_cache,
    get_changed_files,
)


class TestCalculateFileHash:
    def test_basic_hash(self, tmp_path):
        f = tmp_path / "test.py"
        content = b"print('hello')"
        f.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert calculate_file_hash(f) == expected

    def test_same_content_same_hash(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("x = 1\n", encoding="utf-8")
        f2.write_text("x = 1\n", encoding="utf-8")
        assert calculate_file_hash(f1) == calculate_file_hash(f2)

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("x = 1\n", encoding="utf-8")
        f2.write_text("x = 2\n", encoding="utf-8")
        assert calculate_file_hash(f1) != calculate_file_hash(f2)

    def test_large_file(self, tmp_path):
        f = tmp_path / "large.py"
        content = b"x" * 100_000
        f.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert calculate_file_hash(f) == expected


class TestLoadBuildCache:
    def test_no_file(self, tmp_path):
        result = load_build_cache(tmp_path)
        assert result == {"version": "2.0", "files": {}, "compiler_options": {}}

    def test_valid_cache(self, tmp_path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        cache = {
            "version": "2.0",
            "files": {"main.py": {"hash": "abc123"}},
            "compiler_options": {"boundscheck": True},
        }
        (build_dir / ".CyBuilder_cache.json").write_text(
            json.dumps(cache), encoding="utf-8"
        )
        result = load_build_cache(tmp_path)
        assert result["files"]["main.py"]["hash"] == "abc123"

    def test_invalid_json(self, tmp_path):
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / ".CyBuilder_cache.json").write_text("not json!!!", encoding="utf-8")
        result = load_build_cache(tmp_path)
        assert result == {"version": "2.0", "files": {}, "compiler_options": {}}


class TestSaveBuildCache:
    def test_save_and_load(self, tmp_path):
        cache = {"version": "2.0", "files": {"a.py": {"hash": "xxx"}}, "compiler_options": {}}
        save_build_cache(tmp_path, cache)
        loaded = load_build_cache(tmp_path)
        assert loaded["files"]["a.py"]["hash"] == "xxx"
        assert "last_build_time" in loaded

    def test_creates_build_dir(self, tmp_path):
        cache = {"version": "2.0", "files": {}, "compiler_options": {}}
        save_build_cache(tmp_path, cache)
        assert (tmp_path / "build" / ".CyBuilder_cache.json").exists()


class TestGetChangedFiles:
    def _make_pyd(self, dist_dir, module_name, content=b"\x00", platform="win"):
        """在 dist 目录中创建一个假的编译文件（支持 .pyd 和 .so）"""
        if platform == "win":
            compiled = dist_dir / f"{module_name}.cp314-win_amd64.pyd"
        elif platform == "linux":
            compiled = dist_dir / f"{module_name}.cpython-310-x86_64-linux-gnu.so"
        else:  # mac
            compiled = dist_dir / f"{module_name}.cpython-310-darwin.so"
        compiled.write_bytes(content)
        return compiled

    def test_no_cache_all_files_need_compile(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        dist = tmp_path / "dist"
        dist.mkdir()
        cache = {"version": "2.0", "files": {}, "compiler_options": {}}
        compiler_options = {"boundscheck": True, "wraparound": True}

        changed, unchanged = get_changed_files([f], cache, tmp_path, dist, compiler_options)
        assert len(changed) == 1
        assert len(unchanged) == 0

    def test_all_unchanged(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        dist = tmp_path / "dist"
        dist.mkdir()
        pyd = self._make_pyd(dist, "a")

        h = calculate_file_hash(f)
        cache = {
            "version": "2.0",
            "files": {"a.py": {"hash": h, "dist_mtime": os.path.getmtime(pyd)}},
            "compiler_options": {"boundscheck": True, "wraparound": True},
        }
        compiler_options = {"boundscheck": True, "wraparound": True}

        changed, unchanged = get_changed_files([f], cache, tmp_path, dist, compiler_options)
        assert len(changed) == 0
        assert len(unchanged) == 1

    def test_hash_changed(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        dist = tmp_path / "dist"
        dist.mkdir()
        pyd = self._make_pyd(dist, "a")

        cache = {
            "version": "2.0",
            "files": {"a.py": {"hash": "old_hash", "dist_mtime": os.path.getmtime(pyd)}},
            "compiler_options": {"boundscheck": True, "wraparound": True},
        }
        compiler_options = {"boundscheck": True, "wraparound": True}

        changed, unchanged = get_changed_files([f], cache, tmp_path, dist, compiler_options)
        assert len(changed) == 1
        assert f in changed

    def test_pyd_missing(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        dist = tmp_path / "dist"
        dist.mkdir()
        # 不创建 pyd 文件

        h = calculate_file_hash(f)
        cache = {
            "version": "2.0",
            "files": {"a.py": {"hash": h, "dist_mtime": 0}},
            "compiler_options": {"boundscheck": True, "wraparound": True},
        }
        compiler_options = {"boundscheck": True, "wraparound": True}

        changed, unchanged = get_changed_files([f], cache, tmp_path, dist, compiler_options)
        assert len(changed) == 1

    def test_mtime_mismatch(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        dist = tmp_path / "dist"
        dist.mkdir()
        pyd = self._make_pyd(dist, "a")

        h = calculate_file_hash(f)
        cache = {
            "version": "2.0",
            "files": {"a.py": {"hash": h, "dist_mtime": 0.0}},
            "compiler_options": {"boundscheck": True, "wraparound": True},
        }
        compiler_options = {"boundscheck": True, "wraparound": True}

        # 实际 mtime 不是 0.0，所以应该检测到变化
        changed, unchanged = get_changed_files([f], cache, tmp_path, dist, compiler_options)
        assert len(changed) == 1

    def test_compiler_options_changed_full_rebuild(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        dist = tmp_path / "dist"
        dist.mkdir()

        cache = {
            "version": "2.0",
            "files": {"a.py": {"hash": calculate_file_hash(f)}},
            "compiler_options": {"boundscheck": True, "wraparound": True},
        }
        compiler_options = {"boundscheck": False, "wraparound": True}

        changed, unchanged = get_changed_files([f], cache, tmp_path, dist, compiler_options)
        assert len(changed) == 1
        assert len(unchanged) == 0

    def test_multiple_files_mixed(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("x = 1\n")
        f2.write_text("x = 2\n")
        dist = tmp_path / "dist"
        dist.mkdir()

        # a.py 有对应的 pyd，b.py 没有
        pyd_a = self._make_pyd(dist, "a")
        h1 = calculate_file_hash(f1)
        h2 = calculate_file_hash(f2)

        cache = {
            "version": "2.0",
            "files": {
                "a.py": {"hash": h1, "dist_mtime": os.path.getmtime(pyd_a)},
                "b.py": {"hash": h2, "dist_mtime": 0},
            },
            "compiler_options": {"boundscheck": True, "wraparound": True},
        }
        compiler_options = {"boundscheck": True, "wraparound": True}

        changed, unchanged = get_changed_files(
            [f1, f2], cache, tmp_path, dist, compiler_options
        )
        assert f1 in unchanged
        assert f2 in changed

    def test_linux_so_file_detected(self, tmp_path):
        """测试 Linux .so 文件能被正确检测"""
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        dist = tmp_path / "dist"
        dist.mkdir()
        
        # 创建 Linux 风格的 .so 文件
        so_file = self._make_pyd(dist, "a", platform="linux")
        
        h = calculate_file_hash(f)
        cache = {
            "version": "2.0",
            "files": {"a.py": {"hash": h, "dist_mtime": os.path.getmtime(so_file)}},
            "compiler_options": {"boundscheck": True, "wraparound": True},
        }
        compiler_options = {"boundscheck": True, "wraparound": True}

        changed, unchanged = get_changed_files([f], cache, tmp_path, dist, compiler_options)
        assert len(changed) == 0  # 应该检测到 .so 文件，不需要重新编译
        assert len(unchanged) == 1

    def test_macos_so_file_detected(self, tmp_path):
        """测试 macOS .so 文件能被正确检测"""
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        dist = tmp_path / "dist"
        dist.mkdir()
        
        # 创建 macOS 风格的 .so 文件
        so_file = self._make_pyd(dist, "a", platform="mac")
        
        h = calculate_file_hash(f)
        cache = {
            "version": "2.0",
            "files": {"a.py": {"hash": h, "dist_mtime": os.path.getmtime(so_file)}},
            "compiler_options": {"boundscheck": True, "wraparound": True},
        }
        compiler_options = {"boundscheck": True, "wraparound": True}

        changed, unchanged = get_changed_files([f], cache, tmp_path, dist, compiler_options)
        assert len(changed) == 0  # 应该检测到 .so 文件，不需要重新编译
        assert len(unchanged) == 1

    def test_mixed_platform_files(self, tmp_path):
        """测试同时存在 .pyd 和 .so 文件的场景"""
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("x = 1\n")
        f2.write_text("x = 2\n")
        dist = tmp_path / "dist"
        dist.mkdir()

        # a.py 对应 Windows .pyd，b.py 对应 Linux .so
        pyd_a = self._make_pyd(dist, "a", platform="win")
        so_b = self._make_pyd(dist, "b", platform="linux")
        
        h1 = calculate_file_hash(f1)
        h2 = calculate_file_hash(f2)

        cache = {
            "version": "2.0",
            "files": {
                "a.py": {"hash": h1, "dist_mtime": os.path.getmtime(pyd_a)},
                "b.py": {"hash": h2, "dist_mtime": os.path.getmtime(so_b)},
            },
            "compiler_options": {"boundscheck": True, "wraparound": True},
        }
        compiler_options = {"boundscheck": True, "wraparound": True}

        changed, unchanged = get_changed_files(
            [f1, f2], cache, tmp_path, dist, compiler_options
        )
        assert len(changed) == 0
        assert len(unchanged) == 2
