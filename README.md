# Release Generator

一个基于 Gemini AI 的**智能发版文档生成工具**，核心特色是内置**经验闭环系统**——每次人工调整都会被自动提炼为可复用的经验规则，使 AI 生成的文档质量随使用次数持续提升。

## 核心理念

> LLM 是无状态的，但文档生成是一个需要持续积累经验的有状态过程。

传统的 AI 文档生成存在一个根本问题：每次生成都是"从零开始"，之前的调整经验无法沉淀。Release Generator 通过**经验系统**解决了这个问题：

```
生成初版 → 人工审阅修改 → 自动 diff → AI 提炼经验 → 注入下次生成
```

## 主要功能

### 📄 AI 文档生成
- 基于 **模板 + 经验 + 历史文档 + 用户输入** 组装上下文，调用 Gemini 生成文档
- 支持**多模态输入**：文本描述 + 截图（Gemini 直接理解图片内容）
- 自动清理 AI 输出格式，保存为可直接编辑的 Markdown 文件

### 🧠 经验闭环系统
- **自动提炼**：对比 AI 初版与人工终版的 diff，由 Gemini 分析差异并提炼为结构化经验规则
- **三层经验**：
  - **规则（Rules）**：具体可执行的撰写规则，按类别（structure / content / formatting / style / naming）和置信度（high / medium / low）分类
  - **反模式（Anti-patterns）**：AI 常犯的错误及对应的解决方案
  - **Prompt 补丁（Prompt Patches）**：直接注入 prompt 的额外撰写要求
- **AI 辅助优化**：经验库支持自动合并重复、裁剪低质量规则、提升表述清晰度

### 📁 版本管理
- 每次生成的文档按版本归档，保留完整的生成链路：
  - `input.md` — 用户输入
  - `screenshots/` — 本期截图
  - `initial.md` — AI 生成初版
  - `final.md` — 人工调整终版
  - `diff_report.md` — 差异分析与经验提炼结果
- `latest_final.md` 软链接始终指向最新终版

## 项目结构

```
release_generator/
├── config.yaml                    # 全局配置（Gemini API Key、生成参数等）
├── requirements.txt               # Python 依赖
├── doc_types/                     # 文档类型定义
│   └── scale_release/             # SCALE 发版文档
│       ├── template.md            # 文档模板（角色定义 + 章节结构 + 撰写规则）
│       ├── experience.json        # 累积经验库
│       ├── latest_final.md        # → 指向最新终版（symlink）
│       └── versions/              # 历史版本归档
│           ├── v2025.11/
│           ├── v2025.12/
│           └── ...
├── tools/                         # 工具脚本
│   ├── generate.py                # 文档生成
│   ├── finalize.py                # 定稿 + 经验提炼
│   ├── experience_manager.py      # 经验库管理
│   └── gemini_client.py           # Gemini API 封装
└── archive/                       # 早期历史文档存档
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

编辑 `config.yaml`，填入你的 Gemini API Key：

```yaml
gemini:
  api_key: "你的 Gemini API Key"
  model: "gemini-2.5-pro"
```

### 3. 完整工作流

#### Step 1：准备输入

创建版本目录，编写功能描述，放入截图：

```bash
mkdir -p doc_types/scale_release/versions/v2026.03/screenshots
```

在 `v2026.03/input.md` 中描述本期新增功能，将相关截图放入 `screenshots/` 目录。

#### Step 2：生成初版文档

```bash
python tools/generate.py --type scale_release --version v2026.03
```

系统会自动加载模板、经验库、上期终版文档和本期输入，调用 Gemini 生成 `initial.md`。

#### Step 3：审阅修改

在编辑器中打开 `initial.md`，进行人工审阅和修改，完成后保存为 `final.md`。

#### Step 4：定稿 + 经验提炼

```bash
python tools/finalize.py --type scale_release --version v2026.03
```

系统会自动：
- 对比 `initial.md` 与 `final.md` 的差异
- 调用 Gemini 分析差异，提炼新的经验规则
- 更新经验库 `experience.json`
- 更新 `latest_final.md` 软链接

### 4. 经验库管理

```bash
# 查看当前经验库
python tools/experience_manager.py --type scale_release --action show

# 查看经验库统计
python tools/experience_manager.py --type scale_release --action stats

# AI 辅助优化经验库（合并重复、裁剪低质量）
python tools/experience_manager.py --type scale_release --action optimize
```

## 在 Cursor 中使用

本项目设计为以 **Cursor IDE** 作为主要交互入口：

1. 在 Cursor 对话框中描述本期发版需求
2. 将截图拖放到 `versions/{version}/screenshots/` 目录
3. AI 助手负责：整理输入 → 触发生成脚本 → 协助审阅修改 → 触发定稿经验提炼
4. 用户不需要手动创建文件或运行命令

## 扩展新文档类型

在 `doc_types/` 下新建目录，创建以下文件即可支持新的文档类型：

```
doc_types/新类型名/
├── template.md        # 定义角色、章节结构、撰写规则
├── experience.json    # 初始经验库（可为空 JSON 对象）
└── versions/          # 历史版本目录
```

然后使用 `--type 新类型名` 参数调用工具脚本即可。

## 配置说明

`config.yaml` 支持以下配置项：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `gemini.api_key` | Gemini API Key | 必填 |
| `gemini.model` | 使用的 Gemini 模型 | `gemini-2.5-pro` |
| `generation.max_experience_rules` | 生成时携带的最大经验条数 | `20` |
| `generation.auto_open` | 生成后是否自动打开文件 | `true` |
| `experience.auto_extract` | 定稿后是否自动提炼经验 | `true` |
| `experience.optimize_threshold` | 触发自动整理的经验数量阈值 | `50` |
| `experience.low_confidence_ttl_days` | 低置信度经验的自动清理天数 | `90` |

## 技术栈

- **Python 3.10+**
- **Google Gemini API**（`google-generativeai`）— 文档生成与经验提炼
- **Pillow** — 图片处理（多模态输入）
- **PyYAML** — 配置文件解析
- **python-docx** — 历史 Word 文档解析

