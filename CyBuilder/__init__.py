import sys
import argparse
from pathlib import Path

from CyBuilder.core import compile_to_pyd
from CyBuilder.config import (
    _UNSET,
    load_config_file,
    merge_config_with_args,
    normalize_entry_files,
)

__version__ = "0.1.0"
__all__ = ["main", "compile_to_pyd", "load_config_file", "merge_config_with_args", "normalize_entry_files"]


def main():
    """命令行入口点"""
    parser = argparse.ArgumentParser(
        description="CyBuilder - Python 项目编译器，将 .py 文件编译为 .pyd/.so 文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python -m CyBuilder                            # 使用默认配置编译
  python -m CyBuilder -o output                  # 指定输出目录
  python -m CyBuilder -e main.py                 # 指定单个入口文件
  python -m CyBuilder -e main.py,cli.py          # 指定多个入口文件
  python -m CyBuilder --no-boundscheck           # 禁用边界检查以提升性能
  python -m CyBuilder --no-wraparound            # 禁用负数索引支持
  python -m CyBuilder -j 8                       # 使用 8 个进程并行编译
  python -m CyBuilder --no-incremental           # 强制全量编译
  python -m CyBuilder --no-progress              # 禁用进度条（适用于 CI/CD）
  python -m CyBuilder --show-config              # 显示当前生效的配置
  python -m CyBuilder --version                  # 显示版本号
        """
    )

    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"CyBuilder {__version__}",
        help="显示版本号"
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="输出目录名称（默认：dist）"
    )
    parser.add_argument(
        "-e", "--entry",
        type=str,
        default=None,
        help="入口文件名（不编译，直接复制），支持逗号分隔多个文件"
    )
    parser.add_argument(
        "--boundscheck",
        action="store_true",
        default=_UNSET,
        help="启用 Cython 边界检查（默认启用）"
    )
    parser.add_argument(
        "--wraparound",
        action="store_true",
        default=_UNSET,
        help="启用 Cython 负数索引环绕支持（默认启用）"
    )
    parser.add_argument(
        "--no-boundscheck",
        action="store_false",
        dest="boundscheck",
        default=_UNSET,
        help="禁用 Cython 边界检查（提升性能但可能不安全）"
    )
    parser.add_argument(
        "--no-wraparound",
        action="store_false",
        dest="wraparound",
        default=_UNSET,
        help="禁用 Cython 负数索引环绕支持"
    )
    parser.add_argument(
        "-j", "--jobs",
        type=int,
        default=None,
        help="并行编译的工作进程数（默认：CPU核心数）"
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        default=False,
        help="使用串行编译（禁用并行）"
    )
    parser.add_argument(
        "--no-incremental",
        action="store_false",
        dest="incremental",
        default=_UNSET,
        help="禁用增量编译，强制重新编译所有文件"
    )
    parser.add_argument(
        "--no-progress",
        action="store_false",
        dest="progress",
        default=_UNSET,
        help="禁用进度条显示（适用于 CI/CD 环境）"
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        default=False,
        help="显示当前生效的配置并退出"
    )

    cli_defaults = {k: v for k, v in parser._defaults.items() if v is not _UNSET}
    args = parser.parse_args()

    try:
        project_root = Path.cwd()

        file_config = load_config_file(project_root)
        config = merge_config_with_args(file_config, args, cli_defaults)

        if args.show_config:
            print("当前生效的配置:")
            print(f"  配置文件: {project_root / '.CyBuilder.toml'}")
            for key, value in sorted(config.items()):
                print(f"  {key}: {value}")
            return

        print(f"项目根目录: {project_root}")
        print(f"输出目录: {config['output']}")
        entry_files = normalize_entry_files(config["entry"])
        print(f"入口文件: {', '.join(entry_files)}")
        print(f"边界检查: {'启用' if config['boundscheck'] else '禁用'}")
        print(f"负数索引: {'启用' if config['wraparound'] else '禁用'}")
        print(f"增量编译: {'启用' if config['incremental'] else '禁用'}")
        print(f"并行编译: {'串行' if config['sequential'] else str(config['jobs'] or '自动') + ' 进程'}")
        print()

        compile_to_pyd(project_root, config)

    except KeyboardInterrupt:
        print("\n\n用户中断编译")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 编译失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
