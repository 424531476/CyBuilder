# CyBuilder - Python 项目编译器

CyBuilder 是一个 Python 项目编译工具，能够将 `.py` 源文件编译为 `.pyd`（Windows）或 `.so`（Linux/Mac）二进制文件，保护源代码并提升执行性能。

## 主要特性

- **代码保护**：将 Python 源码编译为二进制文件，防止源代码泄露
- **性能优化**：通过 Cython 编译提升代码执行速度
- **增量编译**：基于文件哈希和修改时间检测变化，只重新编译修改过的文件
- **并行编译**：多进程并行编译，充分利用多核 CPU
- **配置文件**：支持 `.CyBuilder.toml` 配置文件，无需每次传参
- **多入口文件**：支持指定多个入口文件，逗号分隔
- **进度条**：编译过程中显示实时进度
- **完整打包**：自动复制配置文件、图片资源等非 Python 文件

## 前置要求

- Python 3.8 或更高版本
- [uv](https://github.com/astral-sh/uv) 包管理工具

## 快速开始

### 安装

#### 方式一：通过 PyPI 安装（推荐）

```bash
pip install CyBuilder
```

#### 方式二：从源码安装

```bash
uv tool install .
```

更新已安装版本：

```bash
# PyPI 安装的用户
pip install --upgrade CyBuilder

# uv 安装的用户
uv tool install . --reinstall
```

### 基本使用

```
# 使用默认配置编译
CyBuilder

# 指定输出目录
CyBuilder -o output

# 指定入口文件
CyBuilder -e app.py

# 指定多个入口文件
CyBuilder -e main.py,cli.py

# 使用 8 个进程并行编译
CyBuilder -j 8

# 强制全量编译（禁用增量）
CyBuilder --no-incremental

# 禁用进度条（适用于 CI/CD）
CyBuilder --no-progress

# 查看当前生效的配置
CyBuilder --show-config

# 显示版本号
CyBuilder --version
```

也可以作为 Python 模块运行：

```
python -m CyBuilder
```

## 命令行参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--output` | `-o` | 输出目录名称 | `dist` |
| `--entry` | `-e` | 入口文件名，支持逗号分隔多个 | `main.py` |
| `--jobs` | `-j` | 并行编译进程数 | CPU 核心数 |
| `--boundscheck` | - | 启用边界检查 | 启用 |
| `--no-boundscheck` | - | 禁用边界检查（更快） | - |
| `--wraparound` | - | 启用负数索引支持 | 启用 |
| `--no-wraparound` | - | 禁用负数索引支持（更快） | - |
| `--sequential` | - | 使用串行编译 | 禁用 |
| `--no-incremental` | - | 禁用增量编译 | - |
| `--no-progress` | - | 禁用进度条 | - |
| `--show-config` | - | 显示当前配置并退出 | - |
| `--version` | `-V` | 显示版本号并退出 | - |

## 配置文件

在项目根目录创建 `.CyBuilder.toml` 或 `CyBuilder.toml`：

``toml
[build]
output = "dist"
entry = ["main.py", "cli.py"]
boundscheck = true
wraparound = true
# jobs = 4              # 并行进程数，注释则自动检测
incremental = true
exclude = ["scripts/*"] # 额外排除的文件模式

[display]
progress = true
verbose = false
```

配置文件与命令行参数合并时，命令行参数优先。

## 编译流程

1. **扫描文件**：递归查找项目中所有 `.py` 文件
2. **增量检测**：对比文件哈希和编译产物修改时间，筛选需要编译的文件
3. **准备环境**：创建构建目录，安装编译依赖
4. **并行编译**：将文件按大小分组，多进程并行编译
5. **整理结果**：收集 `.pyd`/`.so` 文件到输出目录
6. **复制资源**：复制配置文件、图片等非 Python 文件
7. **更新缓存**：记录文件哈希和编译时间，供下次增量判断

## 项目结构

```
your-project/
├── .CyBuilder.toml       # CyBuilder 配置文件（可选）
├── main.py             # 入口文件（不编译，直接复制）
├── module1.py          # 待编译模块
├── module2.py          # 待编译模块
├── config.toml         # 配置文件（会自动复制）
└── dist/               # 编译输出目录
    ├── main.py         # 入口文件（源码）
    ├── module1.pyd     # 编译后的模块
    ├── module2.pyd     # 编译后的模块
    └── config.toml     # 配置文件
```

## 编译选项说明

- **边界检查（boundscheck）**：启用时在数组访问时进行边界验证，更安全但略慢
- **负数索引（wraparound）**：启用时支持 `arr[-1]` 语法，禁用后需使用正数索引

禁用这两个选项可获得最佳性能：

```
CyBuilder --no-boundscheck --no-wraparound
```

## 重要说明

### .pyd 文件的使用限制

编译生成的 `.pyd` 文件是 Python C 扩展模块，**不能直接执行**，只能在 Python 中导入使用：

```python
import module
module.some_function()
```

### 入口文件处理

- 入口文件**不会被编译**，以源码形式复制到输出目录
- 入口文件中的 `if __name__ == "__main__":` 可以正常运行
- 可指定多个入口文件：`CyBuilder -e main.py,cli.py,web.py`

### 自动排除的目录

`dist`、`build`、`build_temp`、`.venv`、`__pycache__`、`.git`、`tests`

## 跨平台支持

CyBuilder 完全支持跨平台编译，会根据操作系统自动生成对应的二进制文件：

| 操作系统 | 输出文件格式 | 示例文件名 |
|---------|------------|-----------|
| Windows | `.pyd` | `module.cp314-win_amd64.pyd` |
| Linux | `.so` | `module.cpython-310-x86_64-linux-gnu.so` |
| macOS | `.so` | `module.cpython-310-darwin.so` |

### Linux 环境要求

在 Linux 上使用 CyBuilder 需要安装 C 编译器：

```bash
# Ubuntu/Debian
sudo apt-get install build-essential

# CentOS/RHEL
sudo yum groupinstall "Development Tools"

# Fedora
sudo dnf groupinstall "Development Tools"
```

### macOS 环境要求

在 macOS 上需要安装 Xcode Command Line Tools：

```bash
xcode-select --install
```

### 增量编译的跨平台特性

CyBuilder 的增量编译功能会自动识别不同平台的编译文件：
- 在 Windows 上检测 `.pyd` 文件
- 在 Linux/macOS 上检测 `.so` 文件
- 缓存数据与平台无关，可以安全地在不同系统间共享项目

## 开发

### 安装开发依赖

```
uv sync --group dev
```

### 运行测试

```
uv run pytest tests/ -v
```

## 许可证

MIT License

## 常见问题 (FAQ)

### Q: CyBuilder 支持哪些操作系统？

A: CyBuilder 支持所有主流操作系统：
- ✅ Windows 10/11
- ✅ Linux（Ubuntu、CentOS、Fedora、Debian 等）
- ✅ macOS（10.15+）

### Q: 在 Linux 上编译失败怎么办？

A: 请确保已安装 C 编译器：
```bash
# 检查是否安装了 gcc
gcc --version

# 如果未安装，执行：
sudo apt-get install build-essential  # Ubuntu/Debian
sudo yum groupinstall "Development Tools"  # CentOS/RHEL
```

### Q: .pyd 和 .so 文件有什么区别？

A: 它们是同一概念在不同平台的实现：
- `.pyd` = Windows 平台的 Python 扩展模块（本质是 DLL）
- `.so` = Linux/macOS 平台的共享对象文件（本质是动态库）
- 功能完全相同，只是文件格式不同

### Q: 能否在 Windows 上编译出 Linux 的 .so 文件？

A: 不能。Cython 编译需要目标平台的编译器：
- Windows 上使用 MSVC 生成 `.pyd`
- Linux 上使用 GCC 生成 `.so`
- 需要在对应平台上分别编译

### Q: 编译后的文件能在不同 Python 版本间通用吗？

A: 不能。编译文件与 Python 版本紧密相关：
- `module.cp314-win_amd64.pyd` 只能用于 Python 3.14
- `module.cpython-310-x86_64-linux-gnu.so` 只能用于 Python 3.10
- 每个 Python 版本需要单独编译
