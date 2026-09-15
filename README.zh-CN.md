<div align="center">

<h3>把 SAP ABAP 工程经验沉淀为 Agent Skill，而不是又一个通用聊天机器人</h3>

<h4><i>遵循 SKILL.md 规范 · 默认只读 · 证据优先审查 · 框架无关</i></h4>

> 四个 Skill 覆盖 ABAP 开发全链路：通过 ADT REST API 读写源代码、9 维度上线前代码审查、10 维度传输请求上线门控、生产级 SAP 集成知识库。写入操作受能力标志与逐次确认双重管控；审查类 Skill 只引用真实证据，证据不足即显式声明缺口——绝不编造结论。由一线 SAP 顾问为日常实战工作打造。

**ADT REST API · 9 维度代码审查 · 10 维度传输门控 · 集成知识库 · 证据优先 · 框架无关**

**MIT · 自托管 · 无厂商锁定 · ECC 6.0 与 S/4HANA**

<h4>面向 SAP ABAP 上线工作流的 AI Agent Skill 套件</h4>

[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3-3776AB?style=flat-square&logo=python&logoColor=white)](skills/sap-adt-cli/scripts)
[![SAP](https://img.shields.io/badge/SAP-ADT%20REST%20API-0FAAFF?style=flat-square&logo=sap&logoColor=white)](#skill-目录)
[![Skills](https://img.shields.io/badge/skills-4-2EA043?style=flat-square)](#skill-目录)
[![Agents](https://img.shields.io/badge/agents-opencode%20%C2%B7%20Claude%20Code%20%C2%B7%20Cursor-orange?style=flat-square)](#兼容的-ai-agent)

**[English](README.md)** · **中文**

</div>

**[Skill 目录](#skill-目录)** · **[快速开始](#快速开始)** · **[仓库结构](#仓库结构)** · **[兼容的 AI Agent](#兼容的-ai-agent)** · **[许可证](#许可证)**

---

## 这是什么？

`sap-engineering-skill` 是一个 **AI Agent Skill 的 Monorepo**，涵盖 SAP ABAP 开发核心工作流：读写源代码、上线前代码质量与安全审查、传输请求上线门控评估，以及带生产级精度的 SAP 集成问答。

每个 Skill 遵循标准 `SKILL.md` 规范，兼容任何支持自定义工具/Skill 注入的 AI Agent 框架——[opencode](https://opencode.ai)、[Claude Code](https://docs.anthropic.com/en/docs/claude-code)、Cursor 或其他框架。

`abap-code-review`、`sap-transport-gate`、`sap-integration-wiki` 三个 Skill 此前作为独立公开仓库维护。这些独立仓库现已**归档**（只读）--后续所有更新仅在本 Monorepo 中进行。

---

## Skill 目录

### [`sap-adt-cli`](skills/sap-adt-cli/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-engineering-skill/tree/main/skills/sap-adt-cli)

通过 [ADT REST API](https://help.sap.com/docs/abap-cloud/abap-development-tools-user-guide/about-abap-development-tools) 对 SAP 系统进行读写操作的命令行工具与 AI Agent Skill。

**支持对象类型**：程序、类、函数模块（需指定函数组）、函数组、接口、包含程序、CDS 视图、类型组（TYPE POOL）、DDIC 表/结构/域/数据元素、包、事务码、对象搜索（`*` 通配符）、只读 Open SQL 数据预览、where-used 分析、语法检查、传输请求管理（列表/创建/发布）。

**核心特性**：
- 默认只读；写入和传输操作需显式开启能力标志，且每次操作都展示变更预览并要求 `[y/N]` 确认，确认绝不缓存或复用（`--yes` 仅限可信自动化场景）
- 多环境 **Profile**（DEV/QAS/PRD…）保存于 `~/.sap-adt-cli/config.json`（0600 权限）——用 `profile use` 持久切换，或用 `--profile` 单次指定
- 密码仅存于**操作系统密钥库**，绝不落入配置文件；后端优先级为 `env` → `keyring`（凭据管理器 / Keychain / Secret Service）→ `dpapi`（WSL2）→ `pass`（GPG）→ `file`（scrypt + Fernet 兜底）；通过 `credentials set|forget|status|doctor` 管理，旧的明文配置自动迁移，详细日志与 HTTP 异常堆栈全程脱敏
- 支持环境变量或 Skill 本地 `.env` 覆盖 Profile（适用于 CI/CD）
- Windows 一键安装脚本（`setup-opencode-abap-cli.bat`），自动完成 opencode + Skill 全流程配置

---

### [`abap-code-review`](skills/abap-code-review/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-engineering-skill/tree/main/skills/abap-code-review)

SAP ABAP 上线前代码审查 AI Agent Skill。对 **9 个维度**进行安全与质量全面评估，生成正式的、可供签字的 Markdown 审查报告。

| #   | 维度                           | 关注点                                 |
| --- | ------------------------------ | -------------------------------------- |
| 1   | **[SEC]** 安全漏洞             | SQL 注入、代码注入、硬编码凭据         |
| 2   | **[AUTH]** 授权与访问控制      | 缺少 AUTHORITY-CHECK、绕过模式         |
| 3   | **[DATA]** 数据完整性          | SY-SUBRC 处理、锁机制、异常处理        |
| 4   | **[PERF]** 性能风险            | LOOP 内 SELECT、SELECT *、全表扫描     |
| 5   | **[STD]** 代码规范             | 废弃语句、超大方法、注释代码残留       |
| 6   | **[INTERFACE]** 接口与集成     | RFC FM 中的对话框消息、缺少 EXCEPTIONS |
| 7   | **[CHANGE]** 变更影响          | 受影响的表、SAP 标准对象修改           |
| 8   | **[COMP]** 合规与审计          | 个人信息处理、审计日志、职责分离路径   |
| 9   | **[FUNC]** 功能完整性 *(可选)* | 业务场景覆盖与需求对齐                 |

**输出**：`GO / CONDITIONAL GO / NO-GO` 建议，附带证据引用的发现和签字表格。

---

### [`sap-transport-gate`](skills/sap-transport-gate/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-engineering-skill/tree/main/skills/sap-transport-gate)

对 SAP 传输请求进行结构化、证据驱动上线就绪评估的 AI Agent Skill，产出可审计的 `GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE` 决策。

覆盖 **10 个审查维度**：代码质量、性能、安全、授权、事务一致性、集成影响、传输完整性、功能对齐、上线就绪性、证据缺口。

**三种审查模式**：
- **离线包模式**——从 SAP 导出的结构化审查包 *(推荐)*
- **离线本地模式**——部分材料（仅源文件）
- **在线传输模式**——TR ID + `tr_collector.py` CLI 实时 ADT 采集

**核心原则**：证据优先。AI 不凭借不足的证据编造结论。

- **在线模式主动采集**——给出 TR ID 后，Skill 会自行执行 `tr_collector.py collect`，仅在凭据缺失或连接失败时回退到离线本地模式；审查开始前会先确认审查范围（仅代码质量 / 功能 + 代码质量）。

---

### [`sap-integration-wiki`](skills/sap-integration-wiki/) &nbsp;·&nbsp; [GitHub](https://github.com/shrek-abaper/sap-engineering-skill/tree/main/skills/sap-integration-wiki)

将任意 AI 助手变成 SAP 集成专家的可组合知识库 Skill。覆盖 9 个业务领域和 8 种集成技术，告别泛泛而错的通用回答。

**业务领域**：MM（采购、库存）、SD（销售）、FI（总账、AR/AP、资产会计、FSSC——含金蝶/用友对接与 SAP Central Finance/CFIN 凭证复制场景）、主数据、PP（生产）

**集成技术**：OData V2/V4、RFC/JCo、SOAP over HTTP RFC（免 JCo 调用 RFC）、IDoc/PI-PO、BAPI & RAP、认证、BTP Integration Suite（iFlow、Cloud Connector、Event Mesh）、最佳实践

**SAP 版本**：ECC 6.0 · S/4HANA On-Prem 1909–2023+ · S/4HANA Cloud（公有版 & 私有版）

---

## 仓库结构

```
sap-engineering-skill/
├── README.md                         ← 英文版（默认）
├── README.zh-CN.md                   ← 本文件（中文）
├── CONTRIBUTING.md                   ← 测试、CI 矩阵、密钥扫描说明
├── LICENSE
├── setup-opencode-abap-cli.bat       ← Windows 一键安装脚本
├── .github/workflows/tests.yml       ← CI：三平台 unittest 矩阵 + gitleaks
├── .gitleaks.toml                    ← 密钥扫描规则（同时作为 pre-commit hook）
├── tests/                            ← 仓库级 unittest 测试套（密钥库、凭据、安全防护等）
└── skills/
    ├── sap-adt-cli/             ← ADT CLI 工具与 Skill（源码位于本仓库）
    ├── abap-code-review/        ← ABAP 代码审查 Skill
    ├── sap-transport-gate/      ← 传输请求上线门控 Skill（含 evals/ 黄金集）
    └── sap-integration-wiki/    ← SAP 集成知识库 Skill
```

上述三个 Skill 历史上以 git subtree 形式关联独立公开仓库，这些独立仓库现已**归档**（只读），后续所有更新仅在本仓库维护：

| 独立仓库（已归档）                     | 迁移至                                                  |
| -------------------------------------- | ------------------------------------------------------- |
| https://github.com/shrek-abaper/abap-code-review     | [`skills/abap-code-review/`](skills/abap-code-review/)     |
| https://github.com/shrek-abaper/sap-transport-gate   | [`skills/sap-transport-gate/`](skills/sap-transport-gate/) |
| https://github.com/shrek-abaper/sap-integration-wiki | [`skills/sap-integration-wiki/`](skills/sap-integration-wiki/) |

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

# 配置 SAP 连接 Profile（交互式向导；密码进入操作系统密钥库）
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure
# 可用 --profile dev/qas/prd 添加多个环境；检查当前生效的密钥库后端：
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py credentials doctor
```

### 兼容的 AI Agent

| Agent                                                         | 说明                                               |
| ------------------------------------------------------------- | -------------------------------------------------- |
| [opencode](https://opencode.ai)                               | 免费开源，支持 30+ 模型提供商，附 Windows 安装脚本 |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Anthropic 官方 CLI Agent，原生支持 `SKILL.md`      |
| [Cursor](https://cursor.sh)                                   | AI 代码编辑器，通过 MCP Tool Adapter 安装          |

> ⚠️ **数据合规提示**：ABAP 源代码可能包含核心业务逻辑和敏感数据。在将代码发送至云端 AI 服务前，请确认符合组织数据安全策略。

---

## Skill 速查

| Skill                  | 适用场景                                              |
| ---------------------- | ----------------------------------------------------- |
| `sap-adt-cli`          | 通过 ADT API 读写 ABAP 源代码、Open SQL 预览、where-used/语法检查、多环境 Profile、管理传输请求 |
| `abap-code-review`     | 单个 ABAP 程序上线前安全与质量审查（9 维度）          |
| `sap-transport-gate`   | 传输请求上线门控评估——基于证据的 GO/NO-GO 决策        |
| `sap-integration-wiki` | SAP 集成模式、API 参考、按场景故障排除                |

---

## 开发与测试

- **测试**——使用标准库 `unittest`，测试代码位于仓库根目录 `tests/`（覆盖密钥库各后端、明文配置迁移、日志脱敏、写入/DML 拦截——共 148 个测试）：

  ```bash
  python3 -m unittest discover -s tests -v
  ```

  仅依赖 `click` / `requests` / `urllib3`；`keyring` 与 `cryptography` 是原生密钥库后端的可选依赖。
- **CI**——[`.github/workflows/tests.yml`](.github/workflows/tests.yml) 在 Ubuntu / Windows / macOS 三平台与 Python 3.12 上运行同一测试套，并执行 gitleaks 全历史密钥扫描。
- **密钥扫描**——gitleaks 同时作为 pre-commit hook 运行（`.pre-commit-config.yaml`）。占位符规则与 WSL/DPAPI 手动验证清单见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 许可证

[MIT](LICENSE)

Skill 包含以下来源的参考内容：
- [SAP Clean ABAP Style Guide](https://github.com/SAP/styleguides/blob/main/clean-abap/CleanABAP.md) — CC BY 4.0（用于 `abap-code-review`）
- [SAP Business Accelerator Hub](https://api.sap.com)、[SAP Help Portal](https://help.sap.com) — SAP 公开文档（用于 `sap-integration-wiki`）

本项目与 SAP SE 无关联，未获 SAP SE 背书或官方支持。
