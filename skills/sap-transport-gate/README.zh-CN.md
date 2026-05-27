# sap-transport-gate

[English](README.md) | [中文](README.zh-CN.md)

> SAP 传输请求发布前门禁审查 AI 技能

一个基于证据驱动的 AI 智能体技能，用于对 SAP 传输请求（Transport Request）进行结构化发布准备评估，生成正式的 `GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE` 决策和发布准备报告。

---

## 功能概述

`sap-transport-gate` 引导 AI 智能体完成结构化审查工作流：

1. **提取 TR ID** — 从用户输入中识别传输请求编号（格式：大写字母 + K + 6 位数字，如 `DEVK900123`）；未找到时主动询问
2. **识别审查模式** — 离线包模式、本地离线模式或在线传输模式；在线模式下验证 SAP 凭证可用性
3. **选择审查范围** — 用户确认：**(A) 代码质量审查**，或 **(B) 功能 + 代码质量审查**（B 选项需提供规格书）
4. **证据收集** — 清点所有提供材料，标记缺失项
5. **证据级别评定** — 基于完整度评定 HIGH / MEDIUM / LOW / UNKNOWN
6. **多维度审查** — 覆盖 10 个维度的全面发布风险扫描
7. **发现分类** — 包含严重性、置信度、证据引用和整改建议的结构化发现
8. **发布决策** — 基于证据的 GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE
9. **报告生成** — Markdown 发布准备报告 + JSON 结构化摘要

---

## 核心原则

| 原则 | 说明 |
|---|---|
| **证据优先** | AI 不从不充分的证据中推断结论，每个发现必须追溯到真实代码、元数据或材料 |
| **AI 不登录 SAP** | AI 侧不持有、不请求凭证；在线模式下 CLI 工具以只读方式调用 SAP ADT 接口，不执行传输操作；AI 仅消费 CLI 采集的证据 |
| **单文件 ≠ TR 审查** | 提供单个 ABAP 文件不构成传输请求级别的发布门禁 |
| **LOW 证据不出 GO** | 证据级别为 `LOW` 时，决策只能是 `NEED_MORE_EVIDENCE` 或 `NO_GO` |
| **不捏造测试结果** | 未读对象不假设为安全；缺失测试证据必须声明 |

---

## 审查维度

| # | 维度 | 关键风险 |
|---|---|---|
| 1 | 代码质量 | 命名规范、硬编码、异常处理、死代码、圈复杂度 |
| 2 | 性能 | SELECT-IN-LOOP、全表扫描、缺失关键条件 |
| 3 | 安全性 | 动态 SQL、OS 命令注入、凭证暴露、未校验输入 |
| 4 | 权限控制 | 缺失 AUTHORITY-CHECK、绕过模式、权限提升 |
| 5 | 事务一致性 | COMMIT/ROLLBACK 位置、LOOP 内 BAPI 提交、LUW 完整性 |
| 6 | 集成影响 | RFC、IDoc、OData、HTTP、BAPI、文件接口风险 |
| 7 | 传输完整性 | 遗漏对象、跨 TR 依赖、DDIC/CDS 缺口 |
| 8 | 功能对齐 | 代码 vs. 规格书 — 业务规则、边界条件、异常流 |
| 9 | 发布就绪度 | 语法检查、激活状态、测试证据、回滚计划 |
| 10 | 证据缺口 | 缺失材料及其对决策的影响 |

---

## 发布决策逻辑

```
证据级别 UNKNOWN              → NEED_MORE_EVIDENCE（仅此）
证据级别 LOW                  → NEED_MORE_EVIDENCE 或 NO_GO
CRITICAL 安全/权限/事务风险   → NO_GO
任意维度 CRITICAL 风险        → NO_GO
HIGH 安全或权限风险           → NO_GO（视同 CRITICAL）
未缓解的 HIGH 风险（其他维度）→ NO_GO
证据缺口为主导                → NEED_MORE_EVIDENCE
MEDIUM 发现 + 有缓解路径      → CONDITIONAL_GO（证据级别需 MEDIUM+）
仅 LOW / INFO + 证据级别 HIGH → GO
```

---

## 三种审查模式

| 模式 | 适用场景 |
|---|---|
| **离线包模式**（推荐） | 用户提供从 SAP 导出的结构化审查包（含清单、源码、依赖信息） |
| **本地离线模式** | 用户仅提供部分材料（如仅有源代码文件，无清单） |
| **在线传输模式** | 提供 TR ID 并可访问 CLI 工具或内部工具进行数据采集 |

所有模式下：AI 不登录 SAP，不持有也不接受凭证；在线传输模式下，CLI 工具以只读方式调用 SAP ADT 接口。

---

## 证据级别

| 级别 | 含义 | 可出 GO？ |
|---|---|---|
| `HIGH` | 对象列表、源码、依赖、规格书、语法检查、激活状态、测试证据均齐全 | ✅ 是 |
| `MEDIUM` | 关键证据具备，但部分项缺失（如无测试证据） | ⚠️ 最多 CONDITIONAL_GO |
| `LOW` | 证据薄弱：单文件、缺对象列表、缺关键证据 | ❌ 否 |
| `UNKNOWN` | 材料结构不明或范围不确定 | ❌ 否（仅 NEED_MORE_EVIDENCE）|

---

## 快速开始（在线传输模式）

### 1. 安装依赖

```bash
cd scripts
pip install -r requirements.txt
```

### 2. 配置 SAP 凭证

**方式一：环境变量文件（推荐）**

```bash
cp .env.example .env
# 编辑 .env，填入 SAP 连接信息
```

`.env` 文件内容示例：

```ini
SAP_URL=https://your-sap-system.example.com:8000
SAP_USERNAME=YOUR_USERNAME
SAP_PASSWORD=YOUR_PASSWORD
SAP_CLIENT=100
SAP_LANGUAGE=EN
SAP_VERIFY_SSL=1   # 自签名证书请设为 0
```

**方式二：交互式配置（存入 `~/.sap-transport-gate/config.json`）**

```bash
python3 scripts/tr_collector.py configure
```

凭证读取优先级：`<skill目录>/.env` → `~/.sap-transport-gate/config.json` → 环境变量

### 3. 测试连接

```bash
python3 scripts/tr_collector.py ping
```

### 4. 采集传输请求审查包

```bash
python3 scripts/tr_collector.py collect DEVK900123
# 可选：指定输出目录
python3 scripts/tr_collector.py collect DEVK900123 --output-dir ./my-review
```

采集完成后，将 `review_package/` 目录的内容（`manifest.json` + 源码文件）提供给 AI 进行审查。

### 5. 提交给 AI 审查

将审查包目录交给加载了本技能的 AI 智能体：

```
请审查传输请求 DEVK900123，材料在 review_package/DEVK900123/
```

---

## 输出

### Markdown 报告

保存为 `reports/TR_REVIEW_{TR_ID}_{YYYYMMDD}.md`（决策为 NO_GO 时前缀为 `NOGO_`）。

**报告结构**：执行决策 → 审查范围 → 证据摘要 → 关键发现 → 分维度审查 → 必要措施 → 人工确认清单 → 决策依据 → 附录

### JSON 摘要

与 Markdown 报告并排保存。包含所有发现、决策元数据、必要措施和人工确认项，供 CI 流水线、仪表板和审计存档使用。

> 默认保存路径：`reports/`（工作区根目录，不存在时自动创建）

---

## 触发短语

当用户说以下内容时加载本技能：

- "审查传输请求 DEVK900123 发布到 QAS"
- "这个 TR 能上生产吗？"
- "发布门禁检查"
- "发布前检查这个传输请求"
- "传输风险评估"
- "生成发布准备报告"
- "Review transport request DEVK900123 for QAS"
- "Can this TR go to production?"
- "Generate a release readiness report"

---

## 不适用场景

- 单个 ABAP 程序的代码审查（无 TR 上下文，使用 `abap-code-review`）
- 执行传输发布、导入或回滚操作
- 直接连接 SAP 系统
- 生成或接受 SAP 密码或连接字符串
- 无人工审批流程的业务结果直接放行

---

## 文件结构

```
sap-transport-gate/
├── .env.example                      ← 凭证模板（请勿提交 .env）
├── .gitignore                        ← Git 忽略规则
├── changelog.md                      ← 版本历史与变更说明
├── LICENSE                           ← MIT 许可证
├── README.md                         ← English documentation
├── README.zh-CN.md                   ← 中文文档（本文件）
├── SKILL.md                          ← 智能体加载指令
├── evals/
│   ├── evals.json                    ← 评测用例（skill-creator 格式）
│   └── golden-set.yaml               ← 知识检索覆盖 Q&A 对
├── references/
│   ├── abap-quality-rules.md         ← ABAP 质量规则集
│   ├── abap-report-template.md       ← 报告章节模板
│   ├── abap-security-rules.md        ← 安全规则目录
│   ├── decision-policy.md            ← 证据级别与决策规则
│   ├── human-loop.md                 ← 人工确认触发规则
│   ├── regression-tests.md           ← 回归测试用例
│   ├── report-format.md              ← 报告 Markdown 模板 & JSON Schema
│   ├── review-dimensions.md          ← 10 维度详细检查项
│   ├── review-modes.md               ← 模式检测与证据清单
│   └── sap-connectivity.md           ← SAP 连接配置指南
└── scripts/
    ├── requirements.txt              ← Python 依赖
    ├── tr_collector.py               ← CLI：采集 TR 审查包
    └── lib/
        ├── __init__.py
        ├── client.py                 ← SAP ADT HTTP 客户端
        ├── config.py                 ← 凭证加载（三级优先级）
        └── handlers.py              ← TR 数据处理（含 E071 回退）
```

---

## 人工确认

以下情况需要人工确认：

- 任何发布到**生产（PRD）**的操作
- 任何 `HIGH` 或 `CRITICAL` 级别发现
- 无规格书时的功能对齐评估
- SECURITY / AUTHORIZATION 发现（需安全负责人）
- INTEGRATION_IMPACT 发现（需接口负责人）
- 无测试证据但仍要求发布

---

## 关联技能

| 技能 | 适用场景 |
|---|---|
| `abap-code-review` | 单个 ABAP 程序发布前代码审查（安全、质量，9 个维度，无 TR 级别门禁评估） |
| `sap-integration-wiki` | SAP 集成模式、API 参考、最佳实践 |
| `sap-adt-cli` | SAP ADT REST API 命令行工具 |

---

## 许可证

MIT — 详见 [LICENSE](LICENSE)
