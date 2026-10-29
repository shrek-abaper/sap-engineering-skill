# sap-adt-cli

[English](README.md) | [中文](README.zh-CN.md)

通过 [ADT（ABAP 开发工具）REST API](https://help.sap.com/docs/abap-cloud/abap-development-tools-user-guide/about-abap-development-tools) 从 SAP 系统**读取与写入** ABAP 源代码、元数据及传输请求的命令行工具，同时也是一个 AI 智能体技能包（Agent Skill）。

支持程序、类、函数模块、接口、Include、CDS 视图、DDIC 对象、包、事务码、SQL 查询、引用分析、语法检查及传输管理——可在终端直接使用，也可集成到 AI 智能体工作流中。写入与传输操作需要显式开启能力标志并逐次确认。

源码还新增了 **ADT 诊断 Feeds、对象分文件版本历史、版本差异和传输请求对象差异**。
这些能力尚未发布到 npm/PyPI；先用 `sap-adt --help` 和
`sap-adt transport diff --help` 确认当前运行时是否具备对应命令。
新增命令均为只读，不需要开启写入能力。比较基线、证据缺口和真实系统验证范围见
[诊断与变更分析指引](references/diagnostics-history.md)，操作示例见
[references/examples.md](references/examples.md)。
源码也新增了显式的 `sap-adt update` 升级命令，尚未发布；支持检查、逐次确认和
安装渠道识别，不会擅自切换安装方式。详见[升级指引](references/updating.md)。

---

## 环境要求

- 已安装 `sap-adt` CLI（一次性安装，见 [references/setup.md](references/setup.md)）：
  - npm：`npm install -g "sap-adt-cli@^1.5.0"`（提供 `sap-adt` 命令）——Node.js ≥ 18，无需 Python。也可用 npx（`npx "sap-adt-cli@^1.5.0" install`），但不会生成 PATH 命令，后续调用需带前缀
  - PyPI：`pip install "sap-adt-cli>=1.5.0,<2.0.0"` — Python ≥ 3.10
  - Release 页面的 Linux 便携包（无需 Python/Node）
- SAP 系统（本地 ECC / S/4HANA 或 BTP ABAP），需已激活 ADT 服务
- 拥有 `SAP_ADT_BASE` 角色（或等效权限）的 SAP 对话用户

**不存在首次运行自动安装依赖**。核心运行时依赖为 `click`、`requests`、`urllib3`；
密钥库后端可选：桌面系统密钥库需 `keyring` extra，加密文件兜底需 `file` extra
（cryptography；WSL2 两者都不需要——直接使用 Windows DPAPI）。详见[凭据存储（密钥库）](#凭据存储密钥库)。

---

## 与 AI Agent 配合使用

`sap-adt-cli` 是标准的 Agent Skill（`SKILL.md`）目录。先按“环境要求”安装 CLI，
再把 Skill 加载到你的 Agent：

| 智能体 | 使用方式 |
|--------|----------|
| Claude Code | 通过[本仓库](https://github.com/shrek-abaper/sap-engineering-skill)插件安装 |
| Codex | 把完整的 Skill 目录复制到 Codex 扫描的位置 |
| WorkBuddy | 同样复制完整的 Skill 目录 |
| 其他 `SKILL.md` 智能体 | 使用各自的 Skill 目录或导入界面 |

Agent 负责驱动工作流，`sap-adt` CLI 负责执行在线 ADT 调用。
Windows x64 从 CLI 1.5.3 起提供 npm 运行时、便携 ZIP 和未签名的桌面安装器；
已有 Python ≥ 3.10 时也可用 PyPI。Skill 目录仍需单独复制到 Agent 的 Skill 目录。
静默安装的已验证范围，以及 GUI、PATH 和提权安装的限制，见
[Windows 安装指南](https://github.com/shrek-abaper/sap-engineering-skill/blob/main/docs/installation/windows.md)。

> **数据合规提示：** ABAP 源代码可能包含企业核心业务逻辑和敏感数据。
> 将代码发送至公网 AI 服务前，请确认符合企业数据安全政策。
> 对于敏感环境，建议优先使用公司内网部署的模型底座。

---

## 快速开始

```bash
# 1. 一次性安装 CLI（任选一种渠道，详见 references/setup.md）
pip install "sap-adt-cli>=1.5.0,<2.0.0"            # Python ≥ 3.10
# 或: npm install -g "sap-adt-cli@^1.5.0" && sap-adt install   # Node.js ≥ 18，无需 Python
#     （npx：npx "sap-adt-cli@^1.5.0" install，之后 npx "sap-adt-cli@^1.5.0" <命令>）

# 2. 配置凭据（交互式向导 — 密码不回显，并存入操作系统密钥库；
#    之后可用 configure --profile qas / prd 添加更多环境）
sap-adt configure

# 3. 验证连接
sap-adt status

# 4. 开始读取 ABAP 对象
sap-adt get-program SAPMV45A
sap-adt get-class ZCL_MY_CLASS
sap-adt get-function BAPI_SALESORDER_CREATEFROMDAT2 --group BAPI_SD_SALESORDER
```

---

## 配置

凭据查找顺序为：

1. 进程环境变量
2. 由 `SAP_ADT_DOTENV` 声明的 dotenv 文件
3. `~/.sap-adt-cli/config.json` 中选中 profile 的非密字段，口令则从操作系统密钥库读取——见[凭据存储（密钥库）](#凭据存储密钥库)

### 多 SAP 环境（Profile）

每套 SAP 系统以命名 profile 的形式保存在 `~/.sap-adt-cli/config.json` 中
（只存非密字段，口令存入密钥库）。首次运行 `configure` 会创建名为
`default` 的 profile；旧的单连接配置会自动迁移：

```bash


# 添加环境（每次保存的 profile 会成为当前生效环境）
sap-adt configure --profile dev --url "https://sap-dev:8000" --username DEV --client 100
sap-adt credentials set dev                       # 随后以隐藏输入存入口令
SAP_PASSWORD="..." sap-adt configure --profile prd --url "https://sap-prd:8000" --username PRD --client 200
                                               # ^ SAP_PASSWORD 会被转入密钥库，不会留在 config.json

# 列出所有环境，* 为当前生效
sap-adt profile list

# 粘性切换（持久化）
sap-adt profile use dev

# 单次覆盖：全局参数 --profile（放在命令名之前）或 SAP_PROFILE 环境变量
sap-adt --profile prd get-program SAPMV45A
SAP_PROFILE=qas sap-adt status

# 删除环境（当前生效的 profile 不能删）
sap-adt profile remove qas
```

profile 选择优先级：`--profile` > `SAP_PROFILE` > `profile use` 设置的 active profile。
请注意写入/传输能力开关是**全局**的，对所有环境（含 PRD）都生效。

> 当环境变量或由 `SAP_ADT_DOTENV` 声明的 dotenv 文件中同时存在完整的 `SAP_URL/USERNAME/PASSWORD/CLIENT`
> 四个变量时，它们会整体覆盖所有 profile；可运行 `status` 查看实际生效的配置来源。

### Dotenv 文件（显式路径，按环境覆盖）

```bash
# 按 references/setup.md 中的模板创建 ~/.config/sap-adt.env
# 编辑并填写 SAP_URL、SAP_USERNAME、SAP_PASSWORD、SAP_CLIENT
export SAP_ADT_DOTENV="$HOME/.config/sap-adt.env"
sap-adt status
```

CLI 不会扫描当前目录或 Skill 目录中的 `.env`，只读取 `SAP_ADT_DOTENV`
声明的文件。不要提交真实文件。

### 交互式向导

```bash
sap-adt configure
```

非密字段以 profile 形式（向导会询问 profile 名称）保存至 `~/.sap-adt-cli/config.json`（`0600`），口令写入当前选中的密钥库。对已存在的 profile 再次运行向导时，密码留空表示保留原密码。

### 凭据存储（密钥库）

口令只允许经可插拔密钥库后端存取，后端按**实际能力探测**选择（而非按操作系统分支），优先级如下：

| # | 后端 | 适用环境 | 前置准备 | 一次性配置 |
|---|------|----------|----------|------------|
| 1 | `env` | 容器 / CI / 任意 | 无 | `export SAP_ADT_<PROFILE>_PASSWORD=...`（只读） |
| 2 | `keyring` | 原生 Windows、macOS、Linux 桌面 | `pip install keyring`（凭据管理器 / Keychain / Secret Service） | 无 |
| 3 | `dpapi` | **WSL2** | 无（经 `powershell.exe` interop 使用 Windows DPAPI） | 无 |
| 4 | `pass` | 有 GPG 的无图形 Linux | 安装并初始化 [`pass`](https://www.passwordstore.org/)（`pass init`） | 无 |
| 5 | `file` | 兜底，全平台 | `pip install cryptography` | 主口令（交互输入，或 `SAP_ADT_MASTER_PASSPHRASE`） |

刻意不提供 `credentials export` 命令。诊断当前后端：

```bash
sap-adt credentials doctor
# 强制指定后端（不可用时直接报错，不静默回退）
sap-adt --keystore file credentials status
```

口令管理：

```bash

sap-adt credentials set dev          # 隐藏输入并二次确认
sap-adt credentials status           # 逐 profile 显示 已配置/未配置，绝不回显口令
sap-adt credentials forget dev       # 从所有可写后端清除
```

> **密钥库中的口令不可跨机器、跨平台复制。** DPAPI 绑定 Windows 账户、Keychain 绑定 macOS 登录态，拷贝 `secrets.json` 或配置到其他机器/用户无法解密——换机后重新执行 `credentials set` 是预期行为，不是 bug。
>
> **旧版本迁移：** 首次运行时若发现 `config.json` 中仍有明文口令，会自动迁移到当前密钥库、原地删除明文字段（不生成备份文件），并提示由于口令曾经明文落盘，建议在 SAP 侧修改口令。

### 环境变量

适用于 CI/CD 流水线或临时会话。完整连接四件套的优先级高于 `SAP_ADT_DOTENV` 声明的 dotenv 文件和所有 profile。

```bash
export SAP_URL=https://my-sap.example.com:8000
export SAP_USERNAME=MYUSER
export SAP_PASSWORD=secret          # 完整连接覆盖；推荐使用此方式，避免 --password 暴露在命令历史中
export SAP_CLIENT=100
export SAP_PROFILE=dev              # 可选：选择使用的 profile（SAP_URL..SAP_CLIENT 四者齐全时此项被忽略）
export SAP_LANGUAGE=EN              # 可选，默认：EN
export SAP_VERIFY_SSL=0             # 可选：设为 0 以跳过自签名证书验证
export SAP_ALLOW_WRITE=0            # 可选：设为 1 以开启 write-source/activate
export SAP_ALLOW_TRANSPORT=0        # 可选：设为 1 以开启 create/release transport

# env 密钥库的按 profile 口令（profile dev 对应变量 SAP_ADT_DEV_PASSWORD）
export SAP_ADT_DEV_PASSWORD=secret
# file 密钥库非交互运行时的主口令
export SAP_ADT_MASTER_PASSPHRASE=...
```

### 能力标志（默认：关闭）

两个可选标志用于解锁写入和传输能力。**仅在确有需要时开启——它们是全局开关，对所有 profile（含生产环境）都生效。** 执行写操作前建议先运行 `status` 确认当前 profile 和开关状态。

```bash
# 交互式开启（在写入/传输提示处输入 'y'）
sap-adt configure --profile dev

# 非交互式开启
SAP_PASSWORD="secret" sap-adt configure --profile dev \
  --url "https://sap-dev.example.com:44300" \
  --username "DEVELOPER" \
  --client "400" \
  --allow-write \
  --no-allow-transport
```

| 标志 | 配置字段（全局，对所有 profile 生效） | 默认值 | 解锁的命令 |
|------|---------|--------|----------|
| `--allow-write` | `allow_write` | false | `write-source`、`activate` |
| `--allow-transport` | `allow_transport` | false | `create-transport`、`release-transport` |

**确认策略**：即使标志已开启，每次写入/创建/释放操作仍会展示变更预览并要求显式输入 `[y/N]` 确认。确认仅对当次操作有效，完成后立即失效，下次操作需重新确认。

### 非交互式参数（智能体 / 自动化工作流）

```bash
# 通过环境变量传递密码，避免暴露在 Shell 历史记录中。
# configure 会把口令转入密钥库，不会留在 config.json。
SAP_PASSWORD="secret" sap-adt configure --profile dev \
  --url      "https://my-sap.example.com:8000" \
  --username "MYUSER" \
  --client   "100"
```

CI 运行期也可以按 profile 直接提供口令：`SAP_ADT_<PROFILE>_PASSWORD`（只读的
`env` 后端），或配合 `--keystore file` 使用 `SAP_ADT_MASTER_PASSPHRASE`。

---

## 命令参考

| 命令 | 说明 |
|------|------|
| `configure [--profile NAME]` | 保存某套环境 profile 的连接凭据（向导或参数） |
| `profile list` | 列出所有环境（`*` 为当前生效） |
| `profile use <NAME>` | 粘性切换当前生效环境 |
| `profile remove <NAME>` | 删除环境（当前生效的 profile 受保护）并清除其口令 |
| `credentials set <NAME>` | 将 profile 口令存入密钥库（隐藏输入） |
| `credentials forget <NAME>` | 从所有可写密钥库清除 profile 口令 |
| `credentials status` | 逐 profile 显示已配置/未配置（不回显口令） |
| `credentials doctor` | 诊断后端可用性、当前选中后端、文件与条目 |
| `--keystore <env\|keyring\|dpapi\|pass\|file> <命令>` | 全局参数：强制指定凭据后端（不可用时报错，不回退） |
| `-v, --verbose` | 详细日志（敏感信息始终脱敏） |
| `status` | 显示当前生效 profile 及连接配置 |
| `update [--check] [--major] [--yes]` | 显式检查/升级 CLI；默认同主版本稳定版；自动升级限可确认的 npm 全局与 pip/pipx 安装；不连接 SAP |
| `--profile NAME <命令>` | 全局参数：对单条命令临时指定 profile |
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
| `list-feeds` | 诊断 Feed 目录，含 FQL 字段、操作符和查询变体 |
| `query-feed <URI> [--query FQL] [--max-results N] [--page-uri URI]` | 查询系统实际提供的单页 Feed；默认 20 条、最多 500 条；跨页记录可能重叠 |
| `get-versions <TYPE> <NAME> [--group FG] [--max-results N]` | 对象各源码部分的版本历史；每部分默认 100 个版本；历史不完整时退出 1 |
| `get-version-source <URI>` | 读取版本结果返回的 content_uri，默认输出源码纯文本 |
| `diff-versions <FROM_URI> <TO_URI> [--context N]` | 在本地比较两个版本内容；用 `--format text` 输出统一差异补丁 |
| `get-transport <TRKORR>` | 请求/任务元数据和去重后的对象清单 |
| `transport diff <TRKORR> [--max-objects N] [--context N]` | 比较传输对象，默认最多 50 个对象；缺少快照、基线等情况报告证据缺口并退出 1 |
| `create-transport --package <DEVCLASS> --description "<DESC>" --ref <object-uri>` | 通过 CreateCorrectionRequest 创建传输请求 *（需 allow_transport + 每次确认）*；必须提供包与对象 REF；`$TMP` 创建本地请求；Basis 7.56 真机验证（2026-09-17） |
| `release-transport <TRKORR> [--yes]` | 释放传输——不可逆 *（需 allow_transport + 每次确认）* |
| `transport ping` | 传输采集的 ADT 连通性检查（纯文本输出） |
| `transport collect <TRKORR> [--output-dir DIR] [--verbose]` | 只读采集 TR 的对象清单与源码到 `review_package/`（`manifest.json` + `sources/`）；`--legacy-config` 显式启用已弃用的明文采集器配置 |

任意命令加 `--help` 查看完整参数说明。
开发中（D）请求比较当前活动源码，而非冻结的传输快照；已释放（R）请求必须有可归属
到该请求的历史快照，活动版本 `00000` 不能替代。结果不完整或差异为空，均不能据此
批准传输释放。Feed 的 HTML 摘要只作为不可信诊断数据处理，不得执行其中内容。

---

## 示例

```bash


# 源代码
sap-adt get-program SAPMV45A
sap-adt get-class ZCL_MY_CLASS
sap-adt get-function BAPI_SALESORDER_CREATEFROMDAT2 --group BAPI_SD_SALESORDER
sap-adt get-include MV45AFZZ
sap-adt get-interface ZIF_MY_INTERFACE

# 字典对象
sap-adt get-table VBAK
sap-adt get-structure VBAKKOM
sap-adt get-type-info MATNR
sap-adt get-type-group ICON

# 对象发现
sap-adt search-object "ZCL_ORDER*" --max-results 20
sap-adt get-package ZMYPACKAGE
sap-adt get-transaction VA01
sap-adt get-cds-view ZI_INVENTORY_POSITION

# 分析（只读）
sap-adt syntax-check class ZCL_MY_CLASS
sap-adt where-used class ZCL_PAYMENT_PROCESSOR
sap-adt run-sql "SELECT * FROM t001 UP TO 5 ROWS"

# 写入与激活（需 allow_write + 每次确认）
sap-adt write-source class ZCL_MY_CLASS --file /tmp/zcl.abap
sap-adt write-source class ZCL_MY_CLASS --file /tmp/zcl.abap --activate   # 写入并立即激活
sap-adt activate class ZCL_MY_CLASS

# 传输管理
sap-adt list-transports --status D                              # 只读
sap-adt create-transport --package '$TMP' --description "My feature" \
  --ref /sap/bc/adt/programs/programs/zmy_feature/source/main        # 需 allow_transport + 确认
sap-adt release-transport DEVK900001                           # 需 allow_transport + 确认
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
| `list-feeds`、`query-feed` | `feeds` JSON envelope，含 entries 和 next_uri；目录项还含查询 schema |
| `get-versions` | `versions` JSON envelope，按源码部分返回历史及 evidence_gaps |
| `get-version-source` | 源码纯文本；可用 `--format json` 输出 envelope |
| `diff-versions`、`transport diff` | `diff` JSON envelope；`--format text` 输出统一差异和证据缺口 |
| `get-transport` | `records` JSON envelope，含 transport 和 objects |

所有输出写入 **stdout**。错误写入 **stderr**，并返回非零退出码。
历史或传输差异的部分结果会同时返回 `ok:true`、`meta.partial:true`、
`data.evidence_gaps` 和退出码 1；不能只检查 `ok`。聚合历史和计算差异不提供原始 XML。

---

## 错误参考

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `Not configured` | 未保存凭据 | 运行 `configure` |
| `Profile 'x' not found` | `--profile`/`SAP_PROFILE` 指定了不存在的环境 | 运行 `profile list` 查看，或用 `configure --profile x` 创建 |
| 删除时提示 `is currently active` | 当前生效的 profile 不允许删除 | 先 `profile use <其他环境>` 再删除 |
| `HTTP 401` | 用户名或密码错误 | 重新运行 `configure` 或 `credentials set <profile>` |
| `no password ... in the keystore` | profile 没有已存口令 | `credentials set <profile>`（或 `credentials doctor`） |
| `HTTP 403` | 缺少 `SAP_ADT_BASE` 角色 | 联系 Basis 分配权限 |
| `HTTP 404` | 对象名称不存在 | 使用 `search-object` 查找正确名称 |
| `HTTP 503` | `/sap/bc/adt` 未激活 | 联系 Basis 在 `SICF` 中激活服务 |
| SSL 错误 | 自签名证书 | 使用 `SAP_VERIFY_SSL=0` 重新配置 |

---

## 安全注意事项

- **口令绝不以明文存储。** `~/.sap-adt-cli/config.json` 只保留非密字段（URL、用户名、client、语言、TLS 开关）；口令存入操作系统密钥库（WSL 用 DPAPI，另有凭据管理器、Keychain、Secret Service、GPG `pass`、口令派生加密文件兜底）。运行 `credentials doctor` 可查看当前后端。旧的明文配置会在首次运行时自动迁移并清除字段。
- DPAPI/Keychain 中的口令**不能跨机器、跨用户复制**；换机后需重新 `credentials set`。请勿提交 `secrets.json`、`secrets.enc` 或任何 `.env`；配置目录应放在原生文件系统上（WSL 的 `/mnt/c` 上 chmod 无效，`credentials doctor` 会给出警告）。
- 避免通过 `--password` 传口令——会出现在 Shell 历史和 `ps` 中。优先使用 `configure` / `credentials set` 的隐藏输入、`SAP_ADT_<PROFILE>_PASSWORD` 或 `SAP_PASSWORD`。
- 日志（含 `-v/--verbose`）和 HTTP 异常 traceback 都会对 `Authorization` 头和口令字面量脱敏；刻意不提供 `credentials export` 命令。
- 写入与传输命令需要显式开启能力标志（`allow_write`、`allow_transport`）并逐次 `[y/N]` 确认。  
  **切勿在生产系统上开启。**
- 可选依赖保持可选：桌面密钥库 `pip install keyring`，加密文件兜底 `pip install cryptography`（即 `[file]` extra）；CLI 核心保持轻依赖。
- 在共享环境或 CI 环境中，建议使用短期凭据并定期轮换。

---

## 版本历史

### v1.4.0 — 可独立安装的 CLI 与多渠道分发

- **CLI 与 Skill 文档分离分发**：`src/sap_adt` 包、`sap-adt` 入口、npm（`sap-adt-cli`）、PyPI（`sap-adt`）、Linux 便携运行时
- **取消运行时自动安装**：依赖需一次性安装；旧的 Skill 内脚本入口已删除
- **传输采集并入 CLI**：`sap-adt transport collect|ping`（只读）；旧明文采集器配置仅在显式 `--legacy-config` 时读取
- **dotenv 需显式声明**：`SAP_ADT_DOTENV` 指定文件，CLI 不再扫描当前目录或 Skill 目录
- 程序名 `sap-adt-cli` → `sap-adt`；命令语义、18 个错误码、退出层级与安全门保持不变

### v1.3.0 — 密钥库凭据存储

- **口令不再明文落盘**：profile 口令迁入可插拔系统密钥库（`env` → `keyring` → `dpapi` → `pass` → `file`），`config.json` 仅保留非密字段
- **WSL2**：经 `powershell.exe` interop 使用 Windows DPAPI，口令只走 stdin、不进命令行参数
- 首次运行**自动单向迁移**旧明文配置，提示轮换 SAP 口令；迁移幂等、不生成备份文件
- **新增命令**：`credentials set|forget|status|doctor`；新增全局选项 `--keystore`、`-v/--verbose`
- **泄露加固**：凭据/配置对象 repr 掩码、日志脱敏过滤器、HTTP 异常净化（traceback 不含 Authorization 头）、进程内解密缓存
- 拒绝把 `keyrings.alt` 明文后端（含 PlaintextKeyring）与 chainer 作为可用后端

### v1.2.0 — 多环境 Profile 支持

- **一份配置管理多套 SAP 环境**：`~/.sap-adt-cli/config.json` 现支持命名 profile（`dev`、`qas`、`prd` 等）；旧的单连接配置会自动迁移为 `default` profile
- **新增命令**：`configure --profile NAME`、`profile list`、`profile use NAME`（粘性切换）、`profile remove NAME`
- **单次环境覆盖**：全局参数 `--profile NAME`（放在命令名之前）或 `SAP_PROFILE` 环境变量；选择优先级为 `--profile` > `SAP_PROFILE` > 当前 active profile
- **能力开关改为全局**：`allow_write` / `allow_transport` 对所有 profile 生效——执行写操作前请先用 `status` 确认当前环境
- **向导体验**：会询问 profile 名称；编辑已有 profile 时密码留空即保留原密码
- `SAP_ADT_DOTENV` / `SAP_*` 环境变量仍作为单环境覆盖层，优先级高于所有 profile

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

## 许可证

[MIT](https://github.com/shrek-abaper/sap-engineering-skill/blob/main/LICENSE)
