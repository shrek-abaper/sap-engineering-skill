# Contributing to SAP Integration Wiki
# 共建 SAP 集成百科

[English](#english) | [中文](#中文)

---

<a name="english"></a>
## English

Thank you for contributing to SAP Integration Wiki! This project exists because SAP integration knowledge is scattered across thousands of pages of official documentation, community blog posts, and hard-won project experience. Your contributions help make this knowledge accessible to everyone.

### Table of Contents (English)
- [Who Should Contribute](#who-should-contribute)
- [Ways to Contribute](#ways-to-contribute)
- [Setting Up Your Environment](#setting-up-your-environment)
- [Adding a New Scenario File](#adding-a-new-scenario-file)
- [Adding a New Technology Reference](#adding-a-new-technology-reference)
- [Improving Existing Content](#improving-existing-content)
- [Content Standards](#content-standards)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

---

### Who Should Contribute

We welcome contributions from:
- SAP integration developers (ABAP, Java, Python, .NET, etc.)
- SAP Basis / Solution Architects who know the system-side configuration
- Enterprise integration specialists (PI/PO, BTP, MuleSoft, etc.)
- Developers who figured out something the hard way and want to save others the pain

You do **not** need to be an SAP expert to contribute. Some of the most valuable contributions are:
- "I tried X and it didn't work because Y — here's the fix"
- "The docs say A but the actual behavior is B in version 2023"
- Code examples in languages not yet covered (Go, Ruby, .NET, etc.)

---

### Ways to Contribute

| Contribution Type | Effort | Impact |
|---|---|---|
| Fix a typo or broken code snippet | 5 min | High — wrong code wastes hours |
| Add a code example in a new language | 30 min | High — Java examples don't help Python devs |
| Add a "common pitfall" entry | 30 min | High — prevents repeated mistakes |
| Improve an existing scenario file | 1–2 hours | High |
| Add a new scenario file (new SAP module) | Half day | Very high |
| Add a new technology reference file | Half day | Very high |
| Translate a reference file | 1–2 hours | High for non-English speakers |

---

### Setting Up Your Environment

No build process required — all content is Markdown, JSON, XML, JavaScript, and Python.

```bash
# Clone the repository
git clone https://github.com/<org>/sap-integration-wiki.git
cd sap-integration-wiki

# Verify scripts run (optional but recommended before submitting)
node scripts/gen-odata-postman.js --help
python3 scripts/gen-jco-config.py --help
python3 scripts/gen-idoc-template.py --help
```

---

### Adding a New Scenario File

Scenario files are in `references/scenarios/`. Each file covers a business domain (MM, SD, FI, PP, HR, etc.).

**When to add a new scenario file:**
- You are covering a SAP module not yet represented (e.g., WM/EWM, PM, QM, HR/HCM, CS)
- The existing file is becoming too long (>600 lines) and needs to be split

**Template for a new scenario file:**

```markdown
# [Module] — [Description] Integration Scenarios

## Table of Contents
- [Overview](#overview)
- [Sub-scenario 1](#sub-scenario-1)
- [Sub-scenario 2](#sub-scenario-2)
- [Version Matrix](#version-matrix)
- [Common Pitfalls](#common-pitfalls)

---

## Overview

[2–3 sentences: what business process this covers and who needs it]

[Table: sub-scenarios with recommended technology per SAP version]

| Sub-scenario | S/4HANA On-Prem | ECC 6.0 |
|---|---|---|
| ... | OData V2 `API_XYZ_SRV` | JCo `BAPI_XYZ` |

---

## Sub-scenario 1

### OData: `API_XYZ_SRV`
[minimal required fields, realistic curl/Python/Java example]

### JCo: `BAPI_XYZ`
[Java example with RETURN table check and BAPI_TRANSACTION_COMMIT]

---

## Version Matrix

| Scenario | ECC 6.0 | S/4HANA On-Prem | S/4HANA Cloud |
|---|---|---|---|

---

## Common Pitfalls

1. [Specific, actionable pitfall with fix]
2. [Another pitfall]
```

**After adding a new scenario file:**
1. Add a row to the scenario routing table in `SKILL.md`
2. Update the scenario table in both `README.md` and `README.zh.md`

---

### Adding a New Technology Reference

Technology reference files are in `references/tech/`. Each file covers an integration protocol or pattern.

**Template for a new technology file:**

```markdown
# [Technology Name]

## Table of Contents
...

---

## Overview / When to Use

[Decision guide: when to use this technology vs. alternatives]

---

## Setup / Prerequisites

[SAP-side and client-side configuration steps]

---

## Implementation

[Working code examples in at least 2 languages]

---

## Common Pitfalls

[Minimum 3 specific, actionable pitfalls]
```

---

### Improving Existing Content

You don't need to rewrite entire files. Even targeted improvements are valuable:

- **Add a missing language example**: if a section only has Java, add Python or curl
- **Add a pitfall**: noticed something not documented? Add it to the "Common Pitfalls" section
- **Fix outdated information**: SAP releases new API versions regularly; update deprecation notices
- **Add version-specific notes**: if something behaves differently in S/4HANA 2023 vs 2020, document it

---

### Content Standards

These standards ensure the content stays high quality and consistent:

**Mandatory:**
- [ ] No placeholder text — every field must have a realistic example value (`"Plant": "1000"`, not `"Plant": "<plant>"`)
- [ ] All code must be syntactically valid — test it if possible
- [ ] API names must be exact — verify on [SAP Business Accelerator Hub](https://api.sap.com)
- [ ] BAPI names must be exact — verify on your SAP system via SE37 or SAP Help
- [ ] Every write BAPI example must include `BAPI_TRANSACTION_COMMIT` with `WAIT="X"`
- [ ] Every write BAPI example must check the RETURN table for errors before committing
- [ ] IDoc status codes must be accurate (cross-reference with `references/tech/idoc-pi.md`)
- [ ] SAP transaction codes must be real (SU01, SOAUTH2, SICF, STRUST, WE20, SM58, etc.)
- [ ] No hardcoded credentials — use placeholder names like `APIUSER`, `your-password`, or env vars

**Recommended:**
- [ ] Add SAP Note or Help Portal link if available
- [ ] Note which SAP versions a feature applies to
- [ ] Include error messages verbatim (makes them searchable)
- [ ] Mention the corresponding SAP transaction for any feature (e.g., "view in WE02")

**Avoid:**
- Vague statements like "configure appropriately" — be specific
- Using `@ts-ignore`, `as any`, or `verify=False` in production examples
- Outdated ECC-only patterns when an OData V2 alternative exists for S/4HANA

---

### Pull Request Process

1. **Fork** the repository and create a branch: `git checkout -b add-ewm-scenario`
2. **Write your content** following the template and content standards above
3. **Self-review** against the checklist in [Content Standards](#content-standards)
4. **Open a PR** with:
   - A clear title: `Add WM/EWM scenario file for warehouse integration`
   - Description: what you added/changed and why
   - If fixing an error: quote the wrong text and the correct text
5. **Respond to review comments** — maintainers may ask for SAP-version clarifications or additional examples

**PR titles follow this convention:**
- `Add [scenario/tech/troubleshoot] file: [topic]`
- `Fix: [what was wrong] in [filename]`
- `Update: [what changed] in [filename]`
- `Translate: [filename] to [language]`

---

### Reporting Issues

Open a GitHub Issue when:
- A code example produces an error or doesn't work as described
- An API name or BAPI name is incorrect
- Information is outdated (SAP released a new version with different behavior)
- A common integration scenario is not covered

**Good issue template:**
```
**File**: references/scenarios/mm-po.md
**Line**: ~45
**SAP Version**: S/4HANA On-Premise 2023
**Problem**: The CSRF token example uses GET on /$metadata but the token fetch must be on the service root.
**Correct behavior**: Fetch token from /API_PURCHASEORDER_PROCESS_SRV/ not /API_PURCHASEORDER_PROCESS_SRV/$metadata
**Reference**: [link to SAP Note or your own test]
```

---

<a name="中文"></a>
## 中文

感谢你为 SAP 集成百科做出贡献！本项目存在的原因，是 SAP 集成知识分散在数千页官方文档、社区博客和项目实践经验中。你的贡献，让这些知识对所有人都触手可及。

### 目录（中文）
- [谁适合参与共建](#谁适合参与共建)
- [共建方式](#共建方式)
- [添加新场景文件](#添加新场景文件)
- [内容规范](#内容规范)
- [提交 PR 的流程](#提交-pr-的流程)
- [反馈问题](#反馈问题)

---

### 谁适合参与共建

欢迎以下人员参与：
- SAP 集成开发工程师（ABAP、Java、Python、.NET 等）
- SAP Basis / 解决方案架构师（了解系统侧配置）
- 企业集成平台专家（PI/PO、BTP Integration Suite、MuleSoft 等）
- 曾经踩过坑、想帮后人少走弯路的开发者

你**不需要**是 SAP 专家才能参与。以下内容同样非常有价值：
- "我试了 X，失败了，因为 Y——这是解决方案"
- "文档说 A，但在 2023 版本中实际行为是 B"
- 目前尚未覆盖语言的代码示例（Go、Ruby、.NET 等）

---

### 共建方式

| 贡献类型 | 所需时间 | 价值 |
|---|---|---|
| 修复笔误或错误代码 | 5 分钟 | 高——错误代码会浪费他人数小时 |
| 补充新语言的代码示例 | 30 分钟 | 高——Java 示例对 Python 开发者没用 |
| 补充"常见陷阱"条目 | 30 分钟 | 高——防止重复踩坑 |
| 完善现有场景文件 | 1–2 小时 | 高 |
| 新增场景文件（新 SAP 模块） | 半天 | 非常高 |
| 新增技术参考文件 | 半天 | 非常高 |
| 翻译参考文件 | 1–2 小时 | 高（对非英语读者） |

---

### 添加新场景文件

场景文件位于 `references/scenarios/` 目录，每个文件覆盖一个业务模块（MM、SD、FI、PP、HR 等）。

**何时新增场景文件：**
- 覆盖尚未收录的 SAP 模块（例如：WM/EWM、PM、QM、HR/HCM、CS 客户服务）
- 现有文件已超过 600 行，需要拆分

**新增场景文件后的必做事项：**
1. 在 `SKILL.md` 的路由表中添加对应行
2. 在 `README.md` 和 `README.zh.md` 的场景表格中同步更新

---

### 内容规范

**必须遵守：**
- [ ] 不得出现占位符文本——所有字段必须是真实示例值（`"Plant": "1000"`，而非 `"Plant": "<plant>"`）
- [ ] 所有代码必须语法正确——如有条件请自测
- [ ] API 名称必须精确——在 [SAP Business Accelerator Hub](https://api.sap.com) 上核实
- [ ] BAPI 名称必须精确——通过 SE37 或 SAP Help 验证
- [ ] 每个写操作 BAPI 示例都必须包含 `BAPI_TRANSACTION_COMMIT`（`WAIT="X"`）
- [ ] 每个写操作 BAPI 示例都必须在提交前检查 RETURN 表的错误
- [ ] 不得包含硬编码凭据——使用 `APIUSER`、`your-password` 或环境变量占位

**推荐：**
- [ ] 如有对应 SAP Note 或 Help Portal 链接，请附上
- [ ] 注明功能适用的 SAP 版本范围
- [ ] 错误消息原文引用（便于搜索）
- [ ] 提及相关 SAP 事务码（例如"在 WE02 中查看"）

---

### 提交 PR 的流程

1. **Fork** 仓库，创建分支：`git checkout -b add-ewm-scenario`
2. 按照模板和内容规范**编写内容**
3. 对照[内容规范](#内容规范)**自查**
4. **发起 PR**，包含：
   - 清晰的标题：`Add WM/EWM scenario file for warehouse integration`
   - 说明：添加/修改了什么，以及为什么
   - 如果是修复错误：引用原文和正确内容
5. **响应 Review 意见**——维护者可能会要求补充 SAP 版本说明或示例

**PR 标题规范：**
- `Add [scenario/tech/troubleshoot] file: [topic]`（添加新文件）
- `Fix: [problem] in [filename]`（修复错误）
- `Update: [what changed] in [filename]`（更新内容）
- `Translate: [filename] to [language]`（翻译）

---

### 反馈问题

遇到以下情况时，请提交 GitHub Issue：
- 代码示例运行报错或行为与描述不符
- API 名称或 BAPI 名称有误
- 信息已过时（SAP 新版本行为发生变化）
- 某个常见集成场景尚未覆盖

**Issue 模板：**
```
**文件**: references/scenarios/mm-po.md
**行号**: ~45
**SAP 版本**: S/4HANA On-Premise 2023
**问题**: CSRF Token 示例使用了 GET /$metadata，但应该请求服务根路径。
**正确行为**: 从 /API_PURCHASEORDER_PROCESS_SRV/ 获取 Token，而非 /.../$metadata
**参考**: [SAP Note 链接或你的测试截图]
```

---

## Code of Conduct / 行为准则

All contributors are expected to be respectful, constructive, and collaborative. This project follows the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) Code of Conduct.

所有贡献者应保持尊重、建设性的态度和协作精神。本项目遵循 [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) 行为准则。
