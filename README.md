<a id="language"></a>

**Language / 语言:** [English](#english) | [简体中文](#chinese)

<a id="english"></a>

# xyzrender GUI

**xyzrender GUI is a bilingual (English and Chinese) desktop interface for molecular structure visualization, built with Python and Tkinter.**

The original [xyzrender](https://github.com/aligfellow/xyzrender) provides a command-line tool and Python API, but does not include a desktop GUI. This project adds a graphical interface on top of xyzrender's molecular input and rendering features, so you can select structure files, adjust rendering options, preview results, and save images in a desktop window.

## Features

- **Molecule management:** Add or remove structure files and select which molecules to load.
- **Multiple input methods:** Open structure files or enter SMILES directly.
- **Live preview:** Render changes in the preview; previewing and saving are separate actions.
- **Rendering options:** Choose presets and adjust the background, atom and bond styles, display options, and orientation.
- **Advanced options:** Configure TS/NCI, GIF animations, molecular surfaces, structure overlays, crystals, annotations, vectors, hulls and pores, and geometric measurements.
- **Export:** Save images as SVG, PNG, PDF, TIFF, and other formats; animation features are provided by the xyzrender engine.
- **Bilingual UI:** Switch between English and Chinese.

Supported input formats and some advanced rendering features depend on the bundled xyzrender engine and its optional dependencies. For the engine's command-line and Python API documentation, see the [upstream documentation](https://xyzrender.readthedocs.io/).

## Run from source

Requires Python 3.10 or later. Install [uv](https://docs.astral.sh/uv/), then run these commands from the project root:

```bash
uv sync --dev
uv run xyzrender-gui
```

Alternatively, start the GUI from a Python environment with the project dependencies installed:

```bash
python -m xyzrender.gui.main
```

## Build on Windows

Install PyInstaller in the Python environment that has the project dependencies, then run the build script:

```bat
python -m pip install pyinstaller
build_gui.bat
```

To use a specific Python environment:

```bat
set PYTHON=C:\path\to\environment\python.exe
build_gui.bat
```

The build is written to `dist\xyzrender-gui\`. PyInstaller uses onedir mode, so distribute the entire folder rather than only the `.exe`. Build output is excluded from Git; you can publish a packaged archive separately on GitHub Releases.

## Project structure

```text
src/xyzrender/gui/   GUI and English/Chinese text
src/xyzrender/       xyzrender engine used by the GUI
tests/               Tests
docs/                Engine documentation
examples/            Example structures and engine output
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

Run the following commands to set up the development environment and run checks:

```bash
just setup
just check
```

## Acknowledgements and citation

This project is built on [xyzrender](https://github.com/aligfellow/xyzrender), the molecular visualization engine that provides its core input and rendering capabilities. We sincerely thank the xyzrender authors and contributors for creating and maintaining this excellent project, as well as the authors and contributors of its dependencies.

If you use methods from the xyzrender engine in your research, please follow the [upstream citation guidelines](https://xyzrender.readthedocs.io/en/latest/citation.html).

## License

This repository is distributed under the [MIT License](LICENSE). Please preserve the upstream attributions included with the xyzrender engine code.

[Back to language selection](#language)

<a id="chinese"></a>

# xyzrender GUI

**xyzrender GUI 是一个基于 Python Tkinter 的分子结构可视化桌面界面，支持中英文。**

原版 [xyzrender](https://github.com/aligfellow/xyzrender) 提供命令行工具和 Python API，并不包含桌面 GUI。本项目在 xyzrender 的分子读取与绘图功能之上增加了图形界面，让用户可以通过窗口选择结构文件、设置绘图参数、预览并保存结果。

## 界面功能

- **分子管理：** 添加、移除结构文件，并从分子列表中选择要加载的结构。
- **多种输入：** 打开结构文件，或直接输入 SMILES。
- **实时预览：** 调整选项后渲染至预览区域；预览和保存操作分开。
- **绘图设置：** 选择预设，调整背景、原子与化学键样式、显示效果和方向。
- **高级选项：** 设置 TS/NCI、GIF 动画、分子表面、结构叠加、晶体、标注、向量、凸包/孔洞及几何测量。
- **导出结果：** 保存 SVG、PNG、PDF、TIFF 等图像；动画功能由 xyzrender 引擎提供。
- **双语界面：** 在英文和中文界面之间切换。

具体可读取的输入格式和部分高级绘图能力取决于项目所带的 xyzrender 引擎及其可选依赖。有关引擎命令行和 Python API 的说明，请参考[上游项目文档](https://xyzrender.readthedocs.io/)。

## 从源码运行

需要 Python 3.10 或更新版本。安装 [uv](https://docs.astral.sh/uv/)，然后在项目根目录运行：

```bash
uv sync --dev
uv run xyzrender-gui
```

也可以在已安装项目依赖的 Python 环境中启动：

```bash
python -m xyzrender.gui.main
```

## 在 Windows 上打包

在已安装项目运行依赖的 Python 环境中安装 PyInstaller，然后运行构建脚本：

```bat
python -m pip install pyinstaller
build_gui.bat
```

如果要使用指定的 Python 环境：

```bat
set PYTHON=C:\path\to\environment\python.exe
build_gui.bat
```

打包结果位于 `dist\xyzrender-gui\`。这是 PyInstaller 的 onedir 模式，分发时需要保留整个文件夹，而不只是其中的 `.exe`。构建结果不会提交到 Git；可以在 GitHub Releases 中单独发布压缩包。

## 项目结构

```text
src/xyzrender/gui/   GUI 界面及中英文文本
src/xyzrender/       GUI 使用的 xyzrender 引擎代码
tests/               项目测试
docs/                引擎相关文档
examples/            示例结构及引擎输出示例
```

## 参与贡献

请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。开发环境可使用以下命令运行检查：

```bash
just setup
just check
```

## 致谢与引用

本项目的核心分子读取与绘图能力基于 [xyzrender](https://github.com/aligfellow/xyzrender)。衷心感谢 xyzrender 项目的作者和贡献者创建并维护了这一优秀项目，同时感谢其依赖项目的作者和贡献者。

如果科研工作使用了 xyzrender 引擎中的方法，请参考[上游项目的引用说明](https://xyzrender.readthedocs.io/en/latest/citation.html)。

## 许可证

本仓库使用 [MIT License](LICENSE)。其中包含的 xyzrender 引擎代码及其上游署名信息请一并保留。

[返回语言选择](#language)
