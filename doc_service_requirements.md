# 文档生成服务 - 需求讨论记录

## 最后更新：2026-02-28

## 一、背景

目前已有的文档生成实践（如 ACL 权限文档生成）验证了 AI 生成文档的可行性，但流程存在以下问题：

### 1.1 现有流程
- 有几类格式相对固定的文档需要定期生成
- 已有历史文档 + 预设的生成 prompt
- 每次只需提供本期新增功能和截图，让 Gemini 生成对应文档

### 1.2 痛点
1. **经验无法沉淀**：Gemini chatbot 没有办法总结每次调整的经验，需要手动调整 prompt，不灵活
2. **上下文丢失**：可能是上下文限制，拿不到上次文档的最终版本，没办法遵循之前的经验
3. **核心问题概括**：LLM 是无状态的，但文档生成是一个需要持续积累经验的有状态过程

## 二、迁移预期

1. 一类文档的**历史生成文档**和**历史调整过程**都被记录
2. 基于最新文档 + 处理经验来指导下一次文档生成
3. 考虑起一个文档服务，其他人也可以使用

## 三、方案讨论

### 3.1 核心概念模型

```
DocumentType（文档类型）
├── template          # 基础模板/prompt
├── experience_log[]  # 经验日志（每次调整的记录）
├── versions[]        # 历史生成版本
│   ├── v1_initial    # AI 初版
│   ├── v1_final      # 人工调整后终版
│   ├── v1_diff       # 初版 vs 终版的差异
│   └── v1_lessons    # 从差异中提炼的经验
└── evolved_prompt    # 基于经验演化后的 prompt
```

### 3.2 核心流程设计

```
每次文档生成的生命周期：

  ┌─────────────────────────────────────────────────┐
  │ 1. 输入阶段                                      │
  │    - 用户提供：本期新增功能描述 + 截图             │
  │    - 系统加载：最新版文档 + 累积经验 + 演化prompt  │
  └──────────────────────┬──────────────────────────┘
                         ▼
  ┌─────────────────────────────────────────────────┐
  │ 2. 生成阶段                                      │
  │    - 组装上下文：template + experience + 上期文档  │
  │    - 调用 Gemini 生成初版文档                     │
  └──────────────────────┬──────────────────────────┘
                         ▼
  ┌─────────────────────────────────────────────────┐
  │ 3. 审阅/调整阶段                                  │
  │    - 用户审阅 AI 初版                             │
  │    - 用户进行修改调整                             │
  │    - 系统记录所有修改（diff）                      │
  └──────────────────────┬──────────────────────────┘
                         ▼
  ┌─────────────────────────────────────────────────┐
  │ 4. 经验提炼阶段                                   │
  │    - 对比初版 vs 终版，提取差异                    │
  │    - AI 分析差异，总结为可复用的经验规则            │
  │    - 更新 experience_log                          │
  │    - （可选）自动演化 prompt                       │
  └──────────────────────┬──────────────────────────┘
                         ▼
  ┌─────────────────────────────────────────────────┐
  │ 5. 归档阶段                                      │
  │    - 保存终版文档为新版本                          │
  │    - 更新文档类型的最新状态                        │
  └─────────────────────────────────────────────────┘
```

### 3.3 经验系统设计思路

经验系统是本方案的核心差异化能力，分为两层：

#### 第一层：事实经验（Factual Experience）
- 记录每次 diff 的具体内容
- 例如："用户总是把'功能说明'改成'功能概述'" → 下次直接用'功能概述'

#### 第二层：策略经验（Strategic Experience）
- 从多次调整中归纳出的生成策略
- 例如："该类型文档中，表格描述应简洁不超过20字" 
- 这些策略会被注入到 prompt 中

#### 经验裁剪
- 经验不是越多越好，过多的经验会干扰 LLM
- 需要定期裁剪、合并、去重
- 可以用 AI 定期对经验库进行整理

### 3.4 服务化考虑

如果要做成服务让其他人也能使用，需要考虑：

#### 最小可用版本（MVP）
- REST API
- 文档类型注册（上传模板 + 历史文档）
- 文档生成接口（接受功能描述 + 截图）
- 版本浏览 + 对比
- 经验查看

#### 存储方案
- 文档内容：文件系统或对象存储（Markdown/PDF）
- 元数据 + 经验：数据库（SQLite → PostgreSQL）
- 截图等二进制：对象存储

#### 技术选型初步考虑
- 后端：Python（复用现有 Gemini 调用链路）
- API 框架：FastAPI
- 前端：简单 Web UI（或先不做，API + CLI 优先）
- AI：Gemini（已有经验）

## 四、决策记录（2026-02-28）

### 4.1 文档类型范围
- **SCALE 发版文档** — 固定格式，定期生成 ✅ 首批支持
- **SQLE 发版文档** — 固定格式，定期生成 ✅ 首批支持
- **用户手册更新** — 涉及 git 仓库联动，⏳ 后续再看

### 4.2 交互方式
- **以 Cursor 对话框为入口**
  - 用户在 Cursor 对话框中描述本期发版需求
  - 截图由用户拖放到 `versions/{version}/screenshots/` 目录
  - AI 助手负责：整理输入到 input.md → 触发生成脚本 → 协助审阅修改 → 触发定稿经验提炼
  - 用户不需要手动创建文件或运行命令

### 4.3 优先级
- **先做经验系统**，验证经验闭环有效
- 服务化后续再考虑

### 4.4 截图处理
- 使用 Gemini 多模态能力直接理解截图，不做额外预处理

### 4.5 经验演化方式
- **自动化为主**：每次调整后自动提炼经验
- 用户定期 review 经验库，确保质量

### 4.6 项目定位
- 这是一个**全新独立项目**，与 /opt 下其他目录无关
- 项目目录：`/opt/SCALE_file/`

## 五、基于决策的方案细化

### 5.1 以 Cursor 为中心的工作流重新设计

既然交互都在 Cursor 中完成，整个系统的定位应调整为：
**一个本地的文档生成工具库 + 文件系统存储**，而不是 C/S 架构。

```
用户在 Cursor 中的操作流程：

1. 【启动生成】
   用户：描述本期新增功能 + 贴截图
   ↓
   系统（脚本/工具）：
   - 读取该文档类型的最新模板
   - 读取该文档类型的经验库
   - 读取上一期终版文档
   - 把截图发给 Gemini 做理解
   - 组装 prompt → 调用 Gemini 生成初版
   - 保存初版到 versions/vN_initial.md
   ↓
2. 【审阅修改】
   用户：在 Cursor 中直接编辑生成的 .md 文件
   （可以继续让 Cursor + 大模型辅助修改）
   ↓
3. 【确认定稿】
   用户：确认修改完成
   ↓
   系统（脚本/工具）：
   - diff 初版 vs 终版
   - 调用 Gemini 分析 diff → 提炼经验
   - 更新经验库
   - 归档终版到 versions/vN_final.md
```

### 5.2 项目目录结构设计

```
/opt/SCALE_file/
├── doc_service_requirements.md    # 本文件 - 需求讨论记录
│
├── doc_types/                     # 文档类型定义
│   ├── scale_release/             # SCALE 发版文档
│   │   ├── template.md            # 基础模板（含 prompt 指导）
│   │   ├── experience.json        # 累积经验库
│   │   ├── versions/              # 历史版本
│   │   │   ├── v2026.02/
│   │   │   │   ├── input.md       # 用户输入的功能描述
│   │   │   │   ├── screenshots/   # 本期截图
│   │   │   │   ├── initial.md     # AI 生成初版
│   │   │   │   ├── final.md       # 人工调整终版
│   │   │   │   └── diff_report.md # 差异分析 + 经验提炼
│   │   │   └── v2026.01/
│   │   │       └── ...
│   │   └── latest_final.md        # → 指向最新终版（symlink 或复制）
│   │
│   └── sqle_release/              # SQLE 发版文档
│       ├── template.md
│       ├── experience.json
│       ├── versions/
│       └── latest_final.md
│
├── tools/                         # 工具脚本
│   ├── generate.py                # 文档生成脚本
│   ├── finalize.py                # 定稿 + 经验提炼脚本
│   ├── experience_manager.py      # 经验库管理（查看/裁剪/合并）
│   └── gemini_client.py           # Gemini API 封装
│
└── config.yaml                    # 全局配置（API key 等）
```

### 5.3 经验库数据结构设计

```json
{
  "doc_type": "scale_release",
  "last_updated": "2026-02-28",
  "experience_version": 3,
  "rules": [
    {
      "id": "r001",
      "category": "formatting",
      "rule": "功能描述表格中，描述列控制在30字以内",
      "source_version": "v2026.01",
      "confidence": "high",
      "times_applied": 5
    },
    {
      "id": "r002",
      "category": "naming",
      "rule": "使用'功能概述'而非'功能说明'作为章节标题",
      "source_version": "v2025.12",
      "confidence": "high",
      "times_applied": 3
    }
  ],
  "anti_patterns": [
    {
      "id": "ap001",
      "description": "AI 倾向于生成过长的功能说明段落，需要精简",
      "solution": "在 prompt 中明确要求每个功能点说明不超过3句话"
    }
  ],
  "prompt_patches": [
    {
      "id": "pp001",
      "content": "每个功能点的描述应精简，不超过3句话，重点说明用户价值而非技术实现",
      "added_at": "v2026.01"
    }
  ]
}
```

### 5.4 Cursor 集成方式

工具脚本设计为可以在 Cursor 终端中直接调用：

```bash
# 启动新一期文档生成
python tools/generate.py --type scale_release --version v2026.03

# 用户在 Cursor 中编辑 initial.md → 修改完保存

# 定稿并提炼经验
python tools/finalize.py --type scale_release --version v2026.03

# 查看当前经验库
python tools/experience_manager.py --type scale_release --action show

# 整理经验库（AI 辅助合并/裁剪）
python tools/experience_manager.py --type scale_release --action optimize
```

## 六、已完成的初始化工作（2026-02-28）

1. ✅ 目录结构创建：`doc_types/scale_release/` 含 versions、screenshots
2. ✅ 历史文档导入：3 份 docx 转换为 markdown 归档到 versions/
   - `v2025.11/final.md` — 11月发版（Gemini 3 Pro + DeepSeek-V3.2-Exp）
   - `v2025.12/final.md` — 12月发版（数据集升级 + 多模型评测）
   - `v_sqlflash_202512/final.md` — SQLFlash 专项测评
3. ✅ 模板初始化：`template.md` 包含两种子类型结构、撰写规则、SCALE 框架知识
4. ✅ 经验库冷启动：`experience.json` 含 14 条规则 + 3 条反模式 + 3 条 prompt 补丁
5. ✅ 配置文件：`config.yaml`（需填写 Gemini API key）

## 七、后续路线图

### Phase 1：经验系统 MVP（当前阶段）
- [x] 用户填写 `config.yaml` 中的 Gemini API key
- [x] 实现 `tools/generate.py` — 文档生成脚本
- [x] 实现 `tools/finalize.py` — 定稿 + 经验提炼脚本
- [x] 实现 `tools/experience_manager.py` — 经验库管理
- [x] 实现 `tools/gemini_client.py` — Gemini API 封装
- [ ] 用一次真实的 SCALE 发版来验证闭环

### Phase 2：SQLE 文档支持
- [ ] 导入 SQLE 历史文档
- [ ] 创建 SQLE 模板和经验库
- [ ] 验证多文档类型并行工作

### Phase 3：服务化
- [ ] FastAPI 服务包装
- [ ] 多用户支持
- [ ] Web UI（文档浏览、经验管理）

### Phase 4：用户手册联动
- [ ] Git 仓库集成
- [ ] 增量更新检测

