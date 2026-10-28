<div align="center">

<h3>面向 AI Agent 的 SAP ABAP 工程 Skill 与 ADT CLI</h3>

<h4><i>遵循 SKILL.md 规范 · 证据优先审查 · 默认只读 · Skill 为普通目录</i></h4>

> 四个 Skill 分别处理上线前 ABAP 代码审查、传输请求上线门控、SAP 集成技术参考，以及通过 ADT REST API 读写 ABAP 开发对象。每个 Skill 都是一套带规则和参考资料的 `SKILL.md` 工作流，可在 Claude Code、Codex、WorkBuddy 及其他支持 Agent Skill 的工具中使用。

**ADT REST API · 代码审查 · 传输门控 · 集成知识 · 证据优先**

**MIT · 自托管 · ECC 6.0 与 S/4HANA**

<h4>离线审查无需 SAP · 在线操作需要 CLI 与 SAP 连接</h4>

[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3-3776AB?style=flat-square&logo=python&logoColor=white)](src/sap_adt)
[![SAP](https://img.shields.io/badge/SAP-ADT%20REST%20API-0FAAFF?style=flat-square&logo=sap&logoColor=white)](#能帮你做什么)
[![Skills](https://img.shields.io/badge/skills-4-2EA043?style=flat-square)](#能帮你做什么)
[![Agents](https://img.shields.io/badge/agents-Claude%20Code%20%C2%B7%20Codex%20%C2%B7%20WorkBuddy-orange?style=flat-square)](#支持的-agent)

**[English](README.md)** · **中文**

**[能帮你做什么](#能帮你做什么)** · **[快速开始](#快速开始)** · **[使用示例](#使用示例)** · **[工作方式](#工作方式)** · **[支持范围与安全边界](#支持范围与安全边界)** · **[文档导航](#文档导航)** · **[许可证](#参与贡献与许可证)**

</div>

---

## 能帮你做什么

| 你的任务 | 对应 Skill | 是否需要 SAP 连接 |
|---|---|---|
| 上线前审查 ABAP 代码 | [`abap-code-review`](skills/abap-code-review/) | 不需要，代码由你提供 |
| 上线前评估传输请求 | [`sap-transport-gate`](skills/sap-transport-gate/) | 提供审查包或源文件时不需要；在线采集需要 CLI |
| 查询 SAP 与 Java、Python、.NET、Node.js、BTP 的集成方式 | [`sap-integration-wiki`](skills/sap-integration-wiki/) | 不需要 |
| 在真实系统上读写 ABAP 对象与传输请求 | [`sap-adt-cli`](skills/sap-adt-cli/) | 需要：已安装的 CLI、连接 Profile 与相应权限 |

`abap-code-review` 覆盖 9 个审查维度，`sap-transport-gate` 覆盖 10 个。各维度的检查项、支持的对象类型和报告契约写在对应 Skill 的 README 与 `references/` 中，本页不重复。

两个审查类 Skill 都输出 Markdown 报告，按严重程度列出问题，并给出明确结论：代码审查为 `GO / CONDITIONAL GO / NO-GO`，传输门控为 `GO / CONDITIONAL_GO / NO_GO / NEED_MORE_EVIDENCE`。每条问题都引用它来自的代码或材料；材料缺失会作为证据缺口单独列出，而不是默认安全。

---

## 快速开始

这里有两件相互独立的事：把 Skill 装进你的 Agent；只在需要访问真实 SAP 系统时，安装并配置 CLI。

### 1. 安装 Skill

**Claude Code** 通过本仓库的插件市场安装：

```text
/plugin marketplace add shrek-abaper/sap-engineering-skill
/plugin install sap-engineering-skills@sap-engineering
```

四个 Skill 统一位于 `sap-engineering-skills` 命名空间下（例如 `/sap-engineering-skills:sap-adt-cli`）。更新可在 `/plugin` 面板操作，或执行 `claude plugin update sap-engineering-skills@sap-engineering`。插件只分发 Skill 文档，不会安装 CLI。该插件源要求 Claude Code ≥ 2.1.224。

**其他 Agent** 直接加载 `SKILL.md` 目录：把完整的 Skill 目录（含 `references/`，不能只复制 `SKILL.md`）放入你的 Agent 会扫描的位置。部分工具读取 `~/.agents/skills/`，另一些使用自己的目录或导入界面。具体流程见 [docs/agents/generic-skills.md](docs/agents/generic-skills.md)，以及下方的[支持的 Agent](#支持的-agent)。

### 2. 安装 CLI（仅在需要在线访问 SAP 时）

`sap-adt-cli` 的所有在线操作都需要 CLI；`sap-transport-gate` 的在线采集需要 CLI。`abap-code-review` 与 `sap-integration-wiki` 始终不需要。

已安装 Node.js ≥ 18 时（该渠道不需要 Python）：

```bash
npm install -g "sap-adt-cli@^1.5.0"
sap-adt install
sap-adt --version
```

npm 包安装的是启动器，`sap-adt install` 负责下载、校验并安装对应平台的运行时。之后普通的 `sap-adt` 调用不会再下载或升级任何内容。自包含运行时目前只发布了 Linux x86_64 版本，Windows 安装器与 macOS 运行时尚未构建。

不想全局安装时，npx 不会在 `PATH` 上留下命令：先执行 `npx "sap-adt-cli@^1.5.0" install`，之后每次调用都要保留这个包前缀。

已有 Python ≥ 3.10、没有 Node.js 时：

```bash
pip install "sap-adt-cli>=1.5.0,<2.0.0"
sap-adt --version
```

随后配置连接：

```bash
sap-adt configure            # 交互式向导；密码在本地输入
sap-adt status               # 只显示本地配置状态，不会连接 SAP
sap-adt credentials doctor   # 显示当前使用的密钥库后端，不输出任何密钥
```

不要在命令行传入密码，也不要把密码粘贴给 Agent。需要多个环境时使用 `--profile dev|qas|prd`；CI/CD 可用环境变量，或由 `SAP_ADT_DOTENV` 声明的 dotenv 文件覆盖 Profile。

完整渠道列表、Linux 便携包、凭据优先级与诊断矩阵见 [docs/installation/runtime-setup.md](docs/installation/runtime-setup.md)。

---

## 使用示例

以下是示例请求，不是实际运行记录。

**审查你已有的代码（无需 SAP 连接）：**

```text
请审查我下面粘贴的 ABAP 报表，准备上线。该程序读取 VBAK/VBAP 并输出 ALV 列表。
请检查安全、授权、性能和代码规范问题，并告诉我是否有阻塞上线的问题。

[粘贴报表源码，包含所有 INCLUDE]
```

预期输出：按严重程度分组的问题，每条包含代码片段、位置、引用规则编号与修复建议；`GO / CONDITIONAL GO / NO-GO` 结论与签字表；以及未能读取、未纳入审查的对象或 INCLUDE 清单。

**基于你提供的材料评估传输请求：**

```text
请评估传输请求 DEVK900123 能否导入 QAS。我附上对象清单和源文件；
没有功能说明书，也没有测试证据。
```

预期输出：先询问审查范围（仅代码质量，或功能 + 代码质量）；给出明确的证据等级；把缺失的功能说明与测试证据列为 `EVIDENCE_GAP`；证据不足时结论不会给到 `GO`。报告写入 `reports/DEVK900123_package/`，包含 Markdown 报告和 JSON 摘要。

**咨询集成问题：**

```text
如何用 Python 在 S/4HANA 中创建采购订单？
```

预期输出：结合你的 SAP 版本与场景给出推荐技术、SAP 侧前置配置、带可用代码片段的实施步骤，以及 2–3 个常见坑。

审查输出是上线流程的输入，而不是审批本身。开发、技术负责人或发布经理仍需完成签字、测试与导入。

---

## 工作方式

| 组件 | 说明 |
|---|---|
| **Skill** | 一个包含 `SKILL.md`（工作流步骤、硬性约束）、检查规则与参考资料的目录。由你的 Agent 加载，本身不含可执行代码。 |
| **CLI** | `sap-adt` 命令，一个独立程序，通过 SAP ADT REST API 执行在线读取、写入与传输请求采集。通过 npm 与 PyPI 分发，源码在本仓库。 |
| **Plugin** | Claude Code 从本仓库安装和更新四个 Skill 目录的方式。只包含文档，CLI 始终需要单独安装。 |

本仓库是四个 Skill 与 CLI 源码的统一分发点，但使用其中任何一项都不需要了解仓库的构建布局。同一套 Skill 目录可被其他支持 `SKILL.md` 的 Agent 加载；发现路径各不相同。

---

## 支持范围与安全边界

### 平台支持

| 平台 | 当前可用 |
|---|---|
| Linux x86_64 | npm 运行时、便携包（glibc 2.39 构建已在 Ubuntu 24.04 验证）、PyPI |
| Windows x86_64 | Python ≥ 3.10 时可用 PyPI；把 Skill 目录复制到 Agent 的 Skill 目录；尚无独立的 Windows 运行时安装器 |
| macOS | Python ≥ 3.10 时可用 PyPI；尚无运行时构建 |

Windows 的 Inno Setup 安装器已实现，但尚未在 Windows 主机上构建与验证；macOS 运行时仅在计划中。在出现真实的构建与安装测试之前，不要依赖这两项。

### SAP 前提

目标系统为 ECC 6.0 与 S/4HANA。在线使用要求系统已启用 ADT 服务（ICF 节点 `/sap/bc/adt`）、你的机器能访问该系统，且用户对目标对象和操作具备相应权限。各 ADT 端点随版本不同：`sap-adt discovery` 与 `sap-adt credentials doctor --coverage` 可以报告某个系统实际暴露了哪些资源。本仓库并未验证所有 ECC/S/4HANA 版本与端点的组合。

### 安全默认值

- **默认只读。** 写入、激活与传输请求发布需要在 Profile 中开启能力，并且每次操作都重新确认 `[y/N]`。`--yes` 面向可信自动化，不是一次性总授权。标记为 `environment=prd` 的 Profile 会拒绝所有写类操作，与开关无关。
- **SQL 预览只允许 SELECT。** 非 SELECT 的 DML 在发出请求前即被拒绝。
- **密码不写入配置文件。** 密码通过操作系统密钥库，或显式声明的环境变量/dotenv 层提供，取决于机器上可用的后端；`sap-adt credentials doctor` 可查看当前生效的后端。
- **传输门控不执行传输**，也不索取 SAP 凭据。在线采集是只读操作，由 CLI 完成。
- **安装 CLI 不等于给 Agent 加了沙箱。** 它界定的是 Agent 能通过 `sap-adt` 触达哪些 SAP 操作，并不限制 Agent 在你机器上的其他行为。
- **审查结论是辅助意见。** AI 输出不能替代人工测试、架构评审、安全审批与发布责任。
- **先确认数据合规要求。** ABAP 源码可能包含核心业务逻辑和个人数据。发送到云端 Agent 之前，请确认符合组织的数据安全策略。本地安装 CLI 也不代表数据不会外发：在线调用会访问你的 SAP 系统，而 Agent 可能把上下文发送给它的模型服务商。

### 支持的 Agent

| Agent | 使用方式 |
|---|---|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | 通过本仓库插件安装（见快速开始） |
| Codex | 通用 `SKILL.md` Agent：把完整的 Skill 目录复制到它扫描的位置，流程见 [docs/agents/generic-skills.md](docs/agents/generic-skills.md) |
| WorkBuddy | 与 Codex 相同的通用目录流程：把完整的 Skill 目录复制到它扫描的位置 |
| Amazon Kiro、Cline、Trae 等工具 | 使用各自的 Skill 目录或导入界面；路径因工具而异 |

不同 Agent 的发现路径不同，详见 [docs/agents/](docs/agents/)。

---

## 文档导航

| 文档 | 内容 |
|---|---|
| [docs/installation/](docs/installation/) | CLI 安装渠道（npm、npx、PyPI、便携包、源码）、凭据优先级、就绪检查与诊断矩阵 |
| [docs/agents/](docs/agents/) | Claude Code 插件细节与通用 `SKILL.md` Agent 说明 |
| [docs/authentication/](docs/authentication/) | SAP↔AI 认证手册：Basic、SPNEGO、X.509、OIDC/OAuth2、网关与客户端模式（同步副本，权威版本在 `sap-functional-skill`） |
| [docs/development/](docs/development/) | 架构、构建与发布工具、迁移说明、已归档的重构历史 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 本地测试基线、密钥扫描、WSL/DPAPI 验证清单 |
| [SECURITY.md](SECURITY.md) | 漏洞报告方式 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录 |

每个 Skill 也有自己的 README 与参考资料：[`sap-adt-cli`](skills/sap-adt-cli/)、[`abap-code-review`](skills/abap-code-review/)、[`sap-transport-gate`](skills/sap-transport-gate/)、[`sap-integration-wiki`](skills/sap-integration-wiki/)。

---

## 参与贡献与许可证

欢迎贡献。测试套件基于标准库 `unittest`，在本地运行。本仓库不使用云端 CI——托管 runner 无法连接真实 SAP 系统，有意义的验证需要在能访问系统的机器上完成。请从 [CONTRIBUTING.md](CONTRIBUTING.md) 开始。

[MIT](LICENSE)

Skill 包含以下来源的参考内容：

- [SAP Clean ABAP Style Guide](https://github.com/SAP/styleguides/blob/main/clean-abap/CleanABAP.md) — CC BY 4.0（用于 `abap-code-review`）
- [SAP Business Accelerator Hub](https://api.sap.com)、[SAP Help Portal](https://help.sap.com) — SAP 公开文档（用于 `sap-integration-wiki`）

本项目与 SAP SE 无关联，未获 SAP SE 背书或官方支持。
