import argparse
from pathlib import Path
from typing import List, Union

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

_UNSET = object()


def get_default_config() -> dict:
    """获取默认配置"""
    return {
        "output": "dist",
        "entry": ["main.py"],
        "boundscheck": True,
        "wraparound": True,
        "jobs": None,
        "incremental": True,
        "progress": True,
        "sequential": False,
        "exclude": [],
        "verbose": False,
        "quiet": False,
    }


def load_config_file(project_root: Path) -> dict:
    """
    加载 .CyBuilder.toml 配置文件
    返回: 配置字典，如果文件不存在返回空字典
    """
    if tomllib is None:
        return {}

    config_paths = [
        project_root / ".CyBuilder.toml",
        project_root / "CyBuilder.toml",
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, "rb") as f:
                    raw = tomllib.load(f)
                config = {}
                config.update(raw.get("build", {}))
                config.update(raw.get("display", {}))
                return config
            except Exception as e:
                print(f"[WARN] 配置文件 {config_path} 解析失败: {e}")
                return {}

    return {}


def merge_config_with_args(config: dict, args: argparse.Namespace, cli_defaults: dict) -> dict:
    """
    合并配置文件和命令行参数
    命令行参数优先级更高
    cli_defaults: argparse 的默认值字典，用于判断用户是否显式指定了参数
    """
    defaults = get_default_config()
    final = defaults.copy()

    for key in defaults:
        if key in config:
            final[key] = config[key]

    for config_key in defaults:
        cli_value = getattr(args, config_key, _UNSET)
        if cli_value is _UNSET:
            continue
        default_value = cli_defaults.get(config_key)
        if cli_value != default_value:
            final[config_key] = cli_value

    if hasattr(args, "entry") and args.entry:
        if isinstance(args.entry, list):
            final["entry"] = args.entry
        elif isinstance(args.entry, str):
            final["entry"] = [e.strip() for e in args.entry.split(",") if e.strip()]

    return final


def normalize_entry_files(entry_arg: Union[str, List[str], None]) -> List[str]:
    """
    标准化入口文件参数
    支持: "main.py" 或 "main.py,cli.py" 或 ["main.py", "cli.py"]
    返回: ["main.py", "cli.py"]
    """
    if entry_arg is None:
        return []
    if isinstance(entry_arg, list):
        result = []
        for item in entry_arg:
            result.extend(e.strip() for e in str(item).split(",") if e.strip())
        return list(dict.fromkeys(result))
    if isinstance(entry_arg, str):
        return [e.strip() for e in entry_arg.split(",") if e.strip()]
    return []
