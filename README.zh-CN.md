# sap-engineering-skill

[English](README.md) | [中文](README.zh-CN.md)

> SAP ABAP 工程 AI Agent SKILL 集锦——由一位 SAP 顾问为日常实战工作打造。

---

## 这是什么？

`sap-engineering-skill` 是一个 **AI Agent Skill 的 Monorepo**，涵盖 SAP ABAP 开发核心工作流：读写源代码、上线前代码质量与安全审查、传输请求上线门控评估，以及带生产级精度的 SAP 集成问答。

每个 Skill 遵循标准 `SKILL.md` 规范，兼容任何支持自定义工具/Skill 注入的 AI Agent 框架——[opencode](https://opencode.ai)、[Claude Code](https://docs.anthropic.com/en/docs/claude-code)、Cursor 或其他框架。

三个子树 Skill 同时作为独立公开仓库维护，可单独使用。

---

## Skill 目录

### [`sap-adt-cli`](skills/sap-adt-cli/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-engineering-skill)

通过 [ADT REST API](https://help.sap.com/docs/abap-cloud/abap-development-tools-user-guide/about-abap-development-tools) 对 SAP 系统进行读写操作的命令行工具与 AI Agent Skill。

**支持对象类型**：程序、类、函数模块、函数组、接口、包含程序、CDS 视图、DDIC 表/结构/类型、包、事务码、SQL 查询、where-used 分析、语法检查、传输请求管理。

**核心特性**：
- 默认只读；写入和传输操作需显式开启能力标志，且每次操作需 `[y/N]` 确认
- Windows 一键安装脚本（`setup-opencode-abap-cli.bat`），自动完成 opencode + Skill 全流程配置
- 凭据存储于 `~/.sap-adt-cli/config.json`，支持环境变量覆盖（适用于 CI/CD）

---

### [`abap-code-review`](skills/abap-code-review/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/abap-code-review)

SAP ABAP 上线前代码审查 AI Agent Skill。对 **9 个维度**进行安全与质量全面评估，生成正式的、可供签字的 Markdown 审查报告。

| # | 维度 | 关注点 |
|---|------|--------|
| 1 | **[SEC]** 安全漏洞 | SQL 注入、代码注入、硬编码凭据 |
| 2 | **[AUTH]** 授权与访问控制 | 缺少 AUTHORITY-CHECK、绕过模式 |
| 3 | **[DATA]** 数据完整性 | SY-SUBRC 处理、锁机制、异常处理 |
| 4 | **[PERF]** 性能风险 | LOOP 内 SELECT、SELECT *、全表扫描 |
| 5 | **[STD]** 代码规范 | 废弃语句、超大方法、注释代码残留 |
| 6 | **[INTERFACE]** 接口与集成 | RFC FM 中的对话框消息、缺少 EXCEPTIONS |
| 7 | **[CHANGE]** 变更影响 | 受影响的表、SAP 标准对象修改 |
| 8 | **[COMP]** 合规与审计 | 个人信息处理、审计日志、职责分离路径 |
| 9 | **[FUNC]** 功能完整性 *(可选)* | 业务场景覆盖与需求对齐 |

**输出**：`GO / CONDITIONAL GO / NO-GO` 建议，附带证据引用的发现和签字表格。

---

### [`sap-transport-gate`](skills/sap-transport-gate/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-transport-gate)

对 SAP 传输请求进行结构化、证据驱动上线就绪评估的 AI Agent Skill，产出可审计的 `GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE` 决策。

覆盖 **10 个审查维度**：代码质量、性能、安全、授权、事务一致性、集成影响、传输完整性、功能对齐、上线就绪性、证据缺口。

**三种审查模式**：
- **离线包模式**——从 SAP 导出的结构化审查包 *(推荐)*
- **离线本地模式**——部分材料（仅源文件）
- **在线传输模式**——TR ID + `tr_collector.py` CLI 实时 ADT 采集

**核心原则**：证据优先。AI 不凭借不足的证据编造结论。

---

### [`sap-integration-wiki`](skills/sap-integration-wiki/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-integration-wiki)

将任意 AI 助手变成 SAP 集成专家的可组合知识库 Skill。覆盖 9 个业务领域和 8 种集成技术，告别泛泛而错的通用回答。

**业务领域**：MM（采购、库存）、SD（销售）、FI（总账、AR/AP、资产会计、FSSC）、主数据、PP（生产）

**集成技术**：OData V2/V4、RFC/JCo、SOAP over HTTP RFC、IDoc/PI-PO、BAPI & RAP、认证、BTP Integration Suite、最佳实践

**SAP 版本**：ECC 6.0 · S/4HANA On-Prem 1909–2023+ · S/4HANA Cloud（公有版 & 私有版）

---

## 仓库结构

```
sap-engineering-skill/
├── README.md                         ← 英文版（默认）
├── README.zh-CN.md                   ← 本文件（中文）
├── LICENSE
├── setup-opencode-abap-cli.bat       ← Windows 一键安装脚本
└── skills/
    ├── sap-adt-cli/             ← ADT CLI 工具与 Skill（源码位于本仓库）
    ├── abap-code-review/        ← ABAP 代码审查 Skill  [git subtree]
    ├── sap-transport-gate/      ← 传输请求上线门控 Skill  [git subtree]
    └── sap-integration-wiki/    ← SAP 集成知识库 Skill  [git subtree]
```

三个子树 Skill 通过命名 git remote 进行跟踪：

| Remote | 仓库地址 |
|--------|---------|
| `pub-abap-code-review` | https://github.com/shrek-abaper/abap-code-review |
| `pub-sap-transport-gate` | https://github.com/shrek-abaper/sap-transport-gate |
| `pub-sap-integration-wiki` | https://github.com/shrek-abaper/sap-integration-wiki |

---

## 快速开始

### Windows——sap-adt-cli 一键安装

下载 [`setup-opencode-abap-cli.bat`](setup-opencode-abap-cli.bat) 并双击运行。脚本自动安装 opencode、克隆本仓库并配置 Skill。

### 手动安装（任意操作系统）

```bash
# 克隆仓库
git clone https://github.com/shrek-abaper/sap-engineering-skill
cd sap-engineering-skill

# 将 Skill 链接到 Agent 的 Skill 目录
ln -s "$(pwd)/skills/sap-adt-cli"          ~/.agents/skills/sap-adt-cli
ln -s "$(pwd)/skills/abap-code-review"     ~/.agents/skills/abap-code-review
ln -s "$(pwd)/skills/sap-transport-gate"   ~/.agents/skills/sap-transport-gate
ln -s "$(pwd)/skills/sap-integration-wiki" ~/.agents/skills/sap-integration-wiki

# 配置 sap-adt-cli 的 SAP 凭据
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure
```

### 兼容的 AI Agent

| Agent | 说明 |
|-------|------|
| [opencode](https://opencode.ai) | 免费开源，支持 30+ 模型提供商，附 Windows 安装脚本 |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Anthropic 官方 CLI Agent，原生支持 `SKILL.md` |
| [Cursor](https://cursor.sh) | AI 代码编辑器，通过 MCP Tool Adapter 安装 |

> ⚠️ **数据合规提示**：ABAP 源代码可能包含核心业务逻辑和敏感数据。在将代码发送至云端 AI 服务前，请确认符合组织数据安全策略。

---

## Skill 速查

| Skill | 适用场景 |
|-------|---------|
| `sap-adt-cli` | 通过 ADT API 读写 ABAP 源代码、执行 SQL、管理传输请求 |
| `abap-code-review` | 单个 ABAP 程序上线前安全与质量审查（9 维度） |
| `sap-transport-gate` | 传输请求上线门控评估——基于证据的 GO/NO-GO 决策 |
| `sap-integration-wiki` | SAP 集成模式、API 参考、按场景故障排除 |

---

## 开发范式

本项目采用 AI 原生、规格驱动的开发循环构建：

1. **规格制定** — 通过与 **Claude Sonnet 4.6** 的对话梳理需求，产出结构化 Markdown 提示文件，编码完整规格（变更范围、验收标准、反模式）。
2. **执行** — 提示文件直接交由 **[opencode](https://opencode.ai) + [Oh My OpenAgent](https://github.com/oh-my-opencode/oh-my-openagent)** 在 **GitHub Copilot Pro** 订阅的模型后端上端到端消费——自主完成规划、实现、测试和验证。
3. **审查** — 人类角色仅限于决定*构建什么*、审查最终输出，以及在结果不符时迭代规格。

> 作者是拥有十余年项目经验、无软件开发背景的 SAP 顾问。本项目源于日常实际需求，也成为一次个人实验——探索 AI 原生工作流如何重塑领域专家的能力边界。希望对同路人有所裨益。

---

## 许可证

[MIT](LICENSE)

Skill 包含以下来源的参考内容：
- [SAP Clean ABAP Style Guide](https://github.com/SAP/styleguides/blob/main/clean-abap/CleanABAP.md) — CC BY 4.0（用于 `abap-code-review`）
- [SAP Business Accelerator Hub](https://api.sap.com)、[SAP Help Portal](https://help.sap.com) — SAP 公开文档（用于 `sap-integration-wiki`）

本项目与 SAP SE 无关联，未获 SAP SE 背书或官方支持。
