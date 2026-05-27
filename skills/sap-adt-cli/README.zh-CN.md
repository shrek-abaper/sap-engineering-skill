# sap-adt-cli

[English](README.md) | [中文](README.zh-CN.md)

通过 [ADT（ABAP 开发工具）REST API](https://help.sap.com/docs/abap-cloud/abap-development-tools-user-guide/about-abap-development-tools) 从 SAP 系统**读取与写入** ABAP 源代码、元数据及传输请求的命令行工具，同时也是一个 AI 智能体技能包（Agent Skill）。

支持程序、类、函数模块、接口、Include、CDS 视图、DDIC 对象、包、事务码、SQL 查询、引用分析、语法检查及传输管理——可在终端直接使用，也可集成到 AI 智能体工作流中。写入与传输操作需要显式开启能力标志并逐次确认。

---

## 环境要求

- Python 3.8+
- SAP 系统（本地 ECC / S/4HANA 或 BTP ABAP），需已激活 ADT 服务
- 拥有 `SAP_ADT_BASE` 角色（或等效权限）的 SAP 对话用户

依赖包（`click`、`requests`、`urllib3`）在首次运行时自动安装。

---

## Windows 一键安装 — AI 智能体快速上手

> **示例：[opencode](https://opencode.ai)** — 免费开源的 AI 智能体 — 作为本文的参考配置。  
> `sap-adt-cli` 以标准 Agent Skill 形式（`SKILL.md`）打包，可与任何支持自定义工具/技能的智能体框架配合使用。

`setup-opencode-abap-cli.bat` 是专为 Windows 用户设计的一键安装脚本，全自动完成 opencode 与本技能包的配置。

### 脚本执行内容

| 步骤 | 操作 |
|------|------|
| 1 | 检测 Node.js ≥ v18、Python 3、Git 是否已安装（缺失时打印下载指引） |
| 2 | 将 Node.js 可执行目录和 npm 全局包路径添加到用户级 `PATH` |
| 3 | 通过 `npm install -g opencode-ai` 全局安装 opencode |
| 4 | 将本仓库克隆到 `%USERPROFILE%\.agents\sap-engineering-skill`，并在 `%USERPROFILE%\.agents\skills\sap-adt-cli` 创建目录联接（Junction），指向仓库内的 `skills\sap-adt-cli` 子目录 |
| 5 | 安装 Python 依赖：`click`、`requests`、`urllib3` |

### 前置软件

运行脚本前，请先安装：

- **[Node.js v18 LTS 或更高版本](https://nodejs.org)** — 使用默认安装选项（默认已勾选添加 PATH）
- **[Python 3.8+](https://www.python.org/downloads)** — 安装时务必勾选 **"Add Python to PATH"**
- **[Git for Windows](https://git-scm.com/download/win)** — 使用默认安装选项

### 运行安装脚本

下载 [`setup-opencode-abap-cli.bat`](../../setup-opencode-abap-cli.bat)，**双击运行**即可。  
脚本将以彩色状态信息引导安装过程；如有前置软件缺失，会自动停止并给出安装提示。

### 使用 opencode 分析 SAP 代码

安装完成后：

```cmd
REM 打开 CMD：按 Win+R，输入 cmd，回车
opencode
```

进入 opencode 后，配置 AI 模型提供商：

```
/connect
```

然后即可用自然语言直接查询 SAP 系统：

```
分析 ZCL_PAYMENT_PROCESSOR 类是否存在安全漏洞
```

```
读取程序 ZREPORT_UPLOAD，检查 SQL 注入风险、缺失的权限检查和硬编码凭据
```

```
扫描包 ZMYPAYMENT 下的所有对象，列出潜在的安全风险
```

opencode 会自动调用 `sap-adt-cli` 通过 ADT 接口从 SAP 系统获取 ABAP 源代码，再交给 AI 模型分析——无需手动复制粘贴。

### SAP 凭据配置（首次使用）

首次执行 ABAP 查询时，opencode 会提示输入 SAP 连接信息：

```
SAP 系统 URL    — 例如 https://my-sap.example.com:8000（含端口号）
SAP 用户名      — 对话用户，例如 DEVELOPER
SAP 密码        — SAP 登录密码
SAP 集团        — 3 位集团编号，例如 100
跳过 SSL 验证？  — 内网或自签名证书环境选 yes
```

凭据保存至 `~\.sap-adt-cli\config.json`，后续会话自动复用。

### 支持的 AI 智能体

opencode 仅作为示例。`sap-adt-cli` 实现了标准 Agent Skill 接口（`SKILL.md`），可与任何支持自定义工具或技能的智能体框架集成：

| 智能体 | 说明 |
|--------|------|
| [opencode](https://opencode.ai) | 免费开源，本文示例，支持 30+ 模型提供商 |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Anthropic 官方 CLI 智能体，原生支持 SKILL.md |
| [Cursor](https://cursor.sh) | AI 代码编辑器，可通过 MCP 工具适配器集成 |
| 其他智能体 | SKILL.md 为 opencode 和 Claude Code 的原生格式；其他框架可能需要适配 |

> ⚠️ **数据合规提示：** ABAP 源代码可能包含企业核心业务逻辑和敏感数据。  
> 将代码发送至公网 AI 服务前，请确认符合企业数据安全政策。  
> 对于敏感环境，建议优先使用公司内网部署的模型底座。

---

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/shrek-abaper/sap-engineering-skill
cd sap-engineering-skill

# 2. 配置凭据（交互式向导 — 密码不回显）
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure

# 3. 验证连接
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py status

# 4. 开始读取 ABAP 对象
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py get-program SAPMV45A
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py get-class ZCL_MY_CLASS
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py get-function BAPI_SALESORDER_CREATEFROMDAT2 --group BAPI_SD_SALESORDER
```

---

## 配置

### 交互式向导（推荐）

```bash
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure
```

凭据保存至 `~/.sap-adt-cli/config.json`，文件权限为 `0600`。

> **安全提示：** 配置文件以明文存储凭据。  
> 请勿将其提交到版本控制系统，并限制文件访问权限。

### 环境变量

适用于 CI/CD 流水线或临时会话。环境变量优先级高于配置文件。

```bash
export SAP_URL=https://my-sap.example.com:8000
export SAP_USERNAME=MYUSER
export SAP_PASSWORD=secret          # 推荐使用此方式，避免 --password 参数暴露在命令历史中
export SAP_CLIENT=100
export SAP_LANGUAGE=EN              # 可选，默认：EN
export SAP_VERIFY_SSL=0             # 可选：设为 0 以跳过自签名证书验证
```

### 能力标志（默认：关闭）

两个可选标志用于解锁写入和传输能力。**仅在开发系统上开启。**

```bash
# 交互式开启
python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure
# → 在写入/传输提示处输入 'y'

# 非交互式开启
SAP_PASSWORD="secret" python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure \
  --url "https://sap-dev.example.com:44300" \
  --username "DEVELOPER" \
  --client "400" \
  --allow-write \
  --no-allow-transport
```

| 标志 | 配置字段 | 默认值 | 解锁的命令 |
|------|---------|--------|----------|
| `--allow-write` | `allow_write` | false | `write-source`、`activate` |
| `--allow-transport` | `allow_transport` | false | `create-transport`、`release-transport` |

**确认策略**：即使标志已开启，每次写入/创建/释放操作仍会展示变更预览并要求显式输入 `[y/N]` 确认。确认仅对当次操作有效，完成后立即失效，下次操作需重新确认。

### 非交互式参数（智能体 / 自动化工作流）

```bash
# 通过环境变量传递密码，避免暴露在 Shell 历史记录中
SAP_PASSWORD="secret" python3 skills/sap-adt-cli/scripts/sap_adt_cli.py configure \
  --url      "https://my-sap.example.com:8000" \
  --username "MYUSER" \
  --client   "100"
```

---

## 命令参考

| 命令 | 说明 |
|------|------|
| `configure` | 保存连接凭据 |
| `status` | 显示当前连接配置 |
| `get-program <NAME>` | ABAP 程序 / 报表源代码 |
| `get-class <NAME>` | ABAP 类源代码 |
| `get-function-group <NAME>` | 函数组顶层 Include 源代码 |
| `get-function <NAME> --group <FG>` | 函数模块源代码 |
| `get-include <NAME>` | ABAP Include 源代码 |
| `get-interface <NAME>` | ABAP 接口源代码 |
| `get-table <NAME>` | DDIC 表字段定义（XML） |
| `get-structure <NAME>` | DDIC 结构定义（XML） |
| `get-type-info <NAME>` | 域或数据元素信息（XML） |
| `get-type-group <NAME>` | ABAP 类型组（TYPE POOL）源代码 |
| `get-cds-view <NAME>` | CDS 视图 DDL 源代码 |
| `get-package <NAME>` | 包对象列表（JSON） |
| `get-transaction <NAME>` | 事务码属性 / 包信息（XML） |
| `search-object <QUERY> [--max-results N]` | 对象名称搜索，支持 `*` 通配符 |
| `syntax-check <TYPE> <NAME> [--group <FG>]` | 语法检查——只读，无需确认；TYPE 为 `function` 时需指定 `--group` |
| `where-used <TYPE> <NAME> [--max-results N] [--group <FG>]` | 引用查询（JSON）；TYPE 为 `function` 时需指定 `--group` |
| `run-sql "<SQL>" [--max-rows N]` | Open SQL SELECT → JSON *（DML 语句被拦截）*；默认返回 100 行，最多 10 000 行 |
| `write-source <TYPE> <NAME> --file <PATH> [--activate] [--group <FG>] [--transport <TRKORR>]` | 写入源代码 *（需 allow_write + 每次确认）*；`--activate` 可在写入后立即激活；TYPE 为 `function` 时需指定 `--group`；`--transport` 指定传输请求编号 |
| `activate <TYPE> <NAME> [--group <FG>]` | 激活 ABAP 对象 *（需 allow_write + 每次确认）*；TYPE 为 `function` 时需指定 `--group` |
| `list-transports [--user U] [--status D\|R]` | 列出传输请求（JSON，只读）；`--status` 默认为 `D`（开发中） |
| `create-transport --description "<DESC>" [--category Workbench\|Customizing]` | 创建传输请求 *（需 allow_transport + 每次确认）*；默认类别：`Workbench` |
| `release-transport <TRKORR> [--yes]` | 释放传输——不可逆 *（需 allow_transport + 每次确认）* |

任意命令加 `--help` 查看完整参数说明。

---

## 示例

```bash
CLI="skills/sap-adt-cli/scripts/sap_adt_cli.py"

# 源代码
python3 $CLI get-program SAPMV45A
python3 $CLI get-class ZCL_MY_CLASS
python3 $CLI get-function BAPI_SALESORDER_CREATEFROMDAT2 --group BAPI_SD_SALESORDER
python3 $CLI get-include MV45AFZZ
python3 $CLI get-interface ZIF_MY_INTERFACE

# 字典对象
python3 $CLI get-table VBAK
python3 $CLI get-structure VBAKKOM
python3 $CLI get-type-info MATNR
python3 $CLI get-type-group ICON

# 对象发现
python3 $CLI search-object "ZCL_ORDER*" --max-results 20
python3 $CLI get-package ZMYPACKAGE
python3 $CLI get-transaction VA01
python3 $CLI get-cds-view ZI_INVENTORY_POSITION

# 分析（只读）
python3 $CLI syntax-check class ZCL_MY_CLASS
python3 $CLI where-used class ZCL_PAYMENT_PROCESSOR
python3 $CLI run-sql "SELECT * FROM t001 UP TO 5 ROWS"

# 写入与激活（需 allow_write + 每次确认）
python3 $CLI write-source class ZCL_MY_CLASS --file /tmp/zcl.abap
python3 $CLI write-source class ZCL_MY_CLASS --file /tmp/zcl.abap --activate   # 写入并立即激活
python3 $CLI activate class ZCL_MY_CLASS

# 传输管理
python3 $CLI list-transports --status D                              # 只读
python3 $CLI create-transport --description "My feature"            # 需 allow_transport + 确认
python3 $CLI release-transport DEVK900001                           # 需 allow_transport + 确认
```

---

## SAP 前置条件

### 1. 激活 ADT 服务

在事务码 `SICF` 中，激活以下服务路径：

| 服务路径 | 适用命令 |
|---|---|
| `/sap/bc/adt` | 所有命令 |
| `/sap/bc/adt/datapreview` | `run-sql`（Open SQL 数据预览） |

### 2. 分配用户权限

| 操作类型 | 所需权限 |
|---|---|
| 所有只读命令 | 角色 `SAP_ADT_BASE`——或手动授予：`S_ADT_RES`（ADT 资源访问）+ `S_RFC`（ADT 函数组） |
| `write-source`、`activate` | `S_DEVELOP`（`ACTVT=02`，对应对象类型） |
| `create-transport`、`release-transport` | `S_CTS_ADMI` 或等效传输权限 |
| `list-transports` | `SAP_ADT_BASE` 已覆盖，无需额外权限 |

---

## 输出格式

| 命令 | 输出格式 |
|------|----------|
| 源代码类命令（`get-program`、`get-class`、`get-function-group`、`get-function`、`get-include`、`get-interface`、`get-cds-view`、`get-type-group`） | ABAP 源代码纯文本 |
| `get-table`、`get-structure`、`get-type-info`、`get-transaction`、`search-object` | ADT 原始 XML |
| `get-package`、`where-used`、`list-transports`、`run-sql` | JSON 数组 |
| `syntax-check` | 纯文本消息（以 `[ERROR]`、`[WARNING]`、`[INFO]` 为前缀）；语法无误时输出 `"Syntax OK — no issues found."` |
| `status` | 纯文本键值对 |

所有输出写入 **stdout**。错误写入 **stderr**，并返回非零退出码。

---

## 错误参考

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `Not configured` | 未保存凭据 | 运行 `configure` |
| `HTTP 401` | 用户名或密码错误 | 重新运行 `configure` |
| `HTTP 403` | 缺少 `SAP_ADT_BASE` 角色 | 联系 Basis 分配权限 |
| `HTTP 404` | 对象名称不存在 | 使用 `search-object` 查找正确名称 |
| `HTTP 503` | `/sap/bc/adt` 未激活 | 联系 Basis 在 `SICF` 中激活服务 |
| SSL 错误 | 自签名证书 | 使用 `SAP_VERIFY_SSL=0` 重新配置 |

---

## 安全注意事项

- 凭据以**明文**存储在 `~/.sap-adt-cli/config.json` 中（权限 `0600`）。  
  这与常见 CLI 工具（AWS CLI、Azure CLI）的做法一致。请限制文件访问权限。
- 避免通过 `--password` 参数传递密码——它会出现在 Shell 历史记录和 `ps` 输出中。  
  推荐使用交互式 `configure` 向导或 `SAP_PASSWORD` 环境变量。
- 写入与传输命令需要显式开启能力标志（`allow_write`、`allow_transport`）并逐次 `[y/N]` 确认。  
  **切勿在生产系统上开启。**
- 在共享环境或 CI 环境中，建议使用短期凭据并定期轮换。

---

## 版本历史

### v1.1.1 — `run-sql` 兼容性与解析修复

- **GET → POST 降级重试**：`run-sql` 现在优先使用 `GET` 请求；若服务器返回 HTTP 405（Method Not Allowed），自动改用 `POST`，将 SQL 放入请求体重试——提升对 S/4HANA 系统（Data Preview 端点要求 `POST`）的兼容性
- **正确的 XML 解析**：`_parse_sql_result` 现在按照 ADT 标准列结构（`<columns>/<metadata name="...">/<dataSet>/<data>`）解析查询结果，不再依赖子元素名称猜测；旧的启发式逻辑作为兜底保留，兼容较旧的 SAP 版本
- **精确的 `Accept` 请求头**：请求时协商 `application/vnd.sap.adt.datapreview.table.v1+xml`，提升响应内容处理的可靠性

### v1.1.0 — 能力扩展与重命名

- **新增 10 个命令**：`syntax-check`、`get-cds-view`、`get-type-group`、`write-source`、`activate`、`where-used`、`run-sql`、`list-transports`、`create-transport`、`release-transport`
- **双重写入保护**：配置中需开启能力标志（`allow_write` / `allow_transport`），且每次破坏性操作均需在运行时显式输入 `[y/N]` 确认
- **DML 安全 SQL**：`run-sql` 仅接受 `SELECT` 语句；`INSERT`、`UPDATE`、`DELETE`、`MERGE`、`MODIFY`、`TRUNCATE` 在 CLI 层被拦截，与系统权限无关
- **工具重命名**：从 `sap-abap-cli` 更名为 `sap-adt-cli`，更准确地反映 ADT API 的覆盖范围
- **配置目录迁移**：从 `~/.sap-abap-cli/` 迁移至 `~/.sap-adt-cli/`；首次运行时若检测到旧目录则自动迁移

### v1.0.0 — 初始版本

- 只读 ADT 技能：程序、类、函数模块、函数组、接口、Include、DDIC 表/结构/类型、包、事务码、对象搜索

---

## 开发范式

本项目采用 AI 原生的规格驱动开发循环：

1. **规格撰写** — 通过与 **Claude Sonnet 4.6** 的对话梳理需求和实现细节，输出结构化的 Markdown 提示词文件，完整编码变更范围、验收标准和反模式约束。
2. **自主执行** — 将提示词文件直接交给智能体编码栈——**[opencode](https://opencode.ai) + [Oh My OpenAgent](https://github.com/oh-my-opencode/oh-my-openagent)**（以 **GitHub Copilot Pro 订阅**作为模型底座）——由其自主完成规划、实现、测试和验证。
3. **人工审查** — 人的职责仅限于决定构建什么、审查最终输出，以及在结果不符合预期时迭代规格。

这套工作流的本质：自然语言意图经由 **Claude Sonnet 4.6** 提炼为可执行的规格文件，规格文件再由以 GitHub Copilot Pro 订阅为底座的智能体栈端到端消费——从想法到可运行代码，全程无需手工介入。

> 作者是一名从事 SAP 行业十余年的业务顾问，没有软件自研背景。这个项目源于日常工作中的真实需求，也是一次借助 AI 原生工具链重塑工作范式的亲身探索——希望能给同样想要动手构建专属工具的领域从业者一些参考与启发。

---

## 许可证

[MIT](../../LICENSE)
