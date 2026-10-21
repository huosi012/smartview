# smartview · aiexport

把 SVG / HTML / PDF 设计稿导出成客户要的 **Adobe Illustrator `.ai` 文件**。提供命令行工具，也可以作为 **MCP 服务**接进 Claude（Claude Code / Claude Desktop），由 Claude 直接交付 `.ai`。

默认输出的就是印刷厂和设计客户常要的规格：

- **CMYK** 颜色，渐变保持为可编辑的矢量渐变，不会被栅格化成图片
- **文字转曲**，客户电脑上没有字体也不会乱
- 黑色和灰色只用 **K 版**（黑字 = K100，不出现四色黑）
- 标记 **出血 / 成品线**（TrimBox / BleedBox）
- 自带检查报告：尺寸、出血、残留字体、色彩空间、图片分辨率（低于 300 ppi 会提醒），并生成预览图

## 生成的 .ai 是什么

从 Illustrator 9 开始，`.ai` 本质上就是一个 PDF，后面附带 Illustrator 的私有数据。这个工具生成的是不带私有数据的 **PDF 兼容 .ai**：

| | aiexport 生成的 .ai | Illustrator 原生 .ai |
|---|---|---|
| Illustrator 直接双击打开 | ✅ | ✅ |
| 路径、渐变、透明度、图片可编辑 | ✅ | ✅ |
| CMYK / 转曲 / 出血 | ✅ | ✅ |
| 图层 | ❌ 打开后全部在同一个图层里（按对象编组） | ✅ |
| 文字可以改字 | ❌（转曲后）/ ⚠️ 不转曲时文字常被拆成多段 | ✅ |
| 需要 Illustrator | 不需要 | 需要 |

大多数「要 AI 源文件」的客户（印刷、改尺寸、改颜色、拿去做物料）用第一种就够了。如果客户要**分图层、能改文字**的原生文件，见下文「原生 .ai」。

## 安装

需要 Python 3.10+。推荐用 [uv](https://docs.astral.sh/uv/)：

```bash
git clone <本仓库> smartview && cd smartview
uv run aiexport doctor           # 首次运行会自动装依赖，并检查本机环境
```

或者用 pip：`pip install -e .`（HTML 支持：`pip install -e '.[html]'`）。

另外需要这几个外部程序，`aiexport doctor` 会告诉你缺哪个：

| 程序 | 作用 | 安装 |
|---|---|---|
| **Inkscape 1.x**（推荐） | 渲染 SVG，还原度最高，自带转曲 | [inkscape.org](https://inkscape.org)；macOS `brew install --cask inkscape` |
| **Ghostscript** | 渲染器不能转曲时（HTML、PDF、cairosvg）负责文字转曲 | macOS `brew install ghostscript`；Windows 从 [ghostscript.com](https://ghostscript.com/releases/gsdnld.html) 安装；Linux `apt install ghostscript` |
| Chrome / Edge + playwright | 渲染 HTML，也可作为 SVG 备用渲染器 | `pip install playwright`，已装 Chrome 即可；否则 `playwright install chromium` |

**CMYK 配置文件**会自动查找，优先级：Japan Color 2001 Coated → Coated FOGRA39 → ISO Coated v2 → U.S. Web Coated (SWOP) → 系统通用 CMYK → Ghostscript 自带。装过 Adobe 软件的电脑上一般能找到前几个。也可以用环境变量 `AIEXPORT_CMYK_PROFILE` 或参数 `--profile` 指定印刷厂给的 `.icc` 文件。

## 命令行

```bash
# SVG → .ai（CMYK + 转曲 + 单 K 黑）
aiexport convert examples/business-card.svg -o card.ai --bleed 3

# 指定成品尺寸（毫米，不含出血），内容等比缩放到该尺寸；比例不符会报错
aiexport convert poster.svg -o poster.ai --size 420x570 --bleed 3

# HTML（CSS 里用 @page { size: A5; margin: 0 } 定尺寸）；多页会拆成 flyer-1.ai、flyer-2.ai…
aiexport convert flyer.html -o flyer.ai

# 同样的流程输出印刷用 PDF（多页保持在一个文件里）
aiexport convert flyer.html -o flyer.pdf

# 检查任意 .ai / .pdf，并另存预览图
aiexport inspect card.ai --preview card.png
```

其他选项：`--rgb` 保留 RGB，`--keep-text` 不转曲，`--rich-black` 黑色也按 ICC 换算成四色，`--renderer inkscape|chromium|cairosvg`，`--title`。

## 接入 Claude（MCP）

MCP 服务提供 3 个工具：

- `export_ai`：传入文件路径（或直接传 SVG/HTML 代码），生成 `.ai`，返回检查报告和预览图
- `inspect_ai`：检查已有的 `.ai` / `.pdf`
- `check_environment`：检查本机缺什么

**Claude Code**：在本仓库目录里启动 Claude Code 即可，`.mcp.json` 已经配置好（首次会询问是否启用）。在其他项目里使用：

```bash
claude mcp add ai-export -- uv run --directory /绝对路径/smartview aiexport-mcp
```

**Claude Desktop**：编辑 `claude_desktop_config.json`（设置 → 开发者 → 编辑配置），加入：

```json
{
  "mcpServers": {
    "ai-export": {
      "command": "/绝对路径/uv",
      "args": ["run", "--directory", "/绝对路径/smartview", "aiexport-mcp"]
    }
  }
}
```

`uv` 的绝对路径可以用 `which uv`（Windows：`where uv`）查到。Claude Desktop 不一定继承终端的 PATH，所以这里要写全路径。

接好之后可以直接说：「设计一张 90×54mm 的名片，3mm 出血，导出成 ai 发给客户」。

## 设计稿规范

- **尺寸**：SVG 根元素写物理单位，例如 `<svg width="96mm" height="60mm" viewBox="0 0 960 600">`；HTML 用 `@page { size: 148mm 210mm; margin: 0 }`。
- **出血**：画布按「成品 + 2×出血」做（名片 90×54 + 3mm 出血 → 96×60mm），背景铺满到画布边缘，导出时加 `--bleed 3`。文字和重要内容离成品线至少 3mm。参考 `examples/business-card.svg`。
- **字体**：转曲时用的是本机字体，导出前确认字体已安装（中文推荐写成 `'Noto Sans CJK SC', 'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei'` 这样的回退列表）。
- **图片**：印刷要求 300 ppi 以上，检查报告会标出不达标的图片。
- **颜色**：屏幕上很鲜艳的 RGB 蓝、绿、荧光色超出 CMYK 色域，转换后会变暗，这是印刷本身的限制。对颜色要求高的项目，以 CMYK 预览为准，或者请印刷厂打样。

## 原生 .ai（分图层、可改文字）

原生 `.ai` 里的私有数据只有 Illustrator 自己能写。有 Illustrator 的电脑上（自己或客户的），可以用 `illustrator/save_as_native_ai.jsx`：

1. Illustrator → 文件 → 脚本 → 其他脚本…，选择这个文件
2. 选择 SVG 设计稿所在文件夹，再选择输出文件夹

SVG 的顶层 `<g id="背景">`、`<g id="文字">` 会变成同名图层，`<text>` 保留为可改的文字，文档转为 CMYK，图片嵌入，保存为 Illustrator CC 兼容格式。

如果想让 Claude 直接操作 Illustrator，可以再装一个开源的 Illustrator MCP（例如 [krVatsal/illustrator-mcp](https://github.com/krVatsal/illustrator-mcp)，支持 macOS 和 Windows），然后让 Claude 执行：

```javascript
var AIEXPORT_NO_UI = true;
$.evalFile("/绝对路径/smartview/illustrator/save_as_native_ai.jsx");
saveAsNativeAi("/路径/card.svg", "/路径/card.ai", { cmyk: true, outlineText: false });
```

这类第三方 MCP 会让 Claude 在你的 Illustrator 里执行任意脚本，安装前请先看过它的代码。

## 开发

```bash
uv run --extra dev --extra html pytest
```

不依赖外部程序的测试（CMYK 转换、尺寸、出血、MCP 工具列表）总会运行；需要 Inkscape / Ghostscript / Chromium 的测试在缺少这些程序时自动跳过。可以用环境变量 `AIEXPORT_INKSCAPE`、`AIEXPORT_GS`、`AIEXPORT_CHROMIUM` 指定可执行文件路径。
