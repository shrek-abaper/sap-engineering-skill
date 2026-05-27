# abap-code-review

> 🇬🇧 [English Version](README.md)

适用于 SAP ABAP 发布前代码审查的 AI Agent Skill。通过 9 个维度对 ABAP 程序进行全面的安全与质量评估，并生成可用于正式签字流转的 Markdown 报告。

---

## 简介

`abap-code-review` 是一个 AI Agent Skill，引导 AI Agent 按照结构化、可重复的工作流对 ABAP 代码进行审查。它的目标是在 Transport 上移到生产系统之前，发现安全漏洞、权限缺失、性能隐患和代码质量问题。

### 为什么使用它？

- **全面覆盖** — 9 个审查维度，任何维度都不会被跳过
- **以证据为基础** — 每个发现都必须附有真实代码片段，不允许推测
- **规则可追溯** — 安全和规范类发现始终关联具体规则（如 `SEC-SQL-1`、`[T-2]`）
- **支持发布决策** — 输出包含结构化报告，带有 GO / CONDITIONAL GO / NO-GO 建议及签字表格

---

## 审查维度

| # | 维度 | 主要检查点 |
|---|------|-----------|
| 1 | **[SEC]** 安全漏洞 | SQL 注入、代码注入、OS 命令注入、文件路径攻击、硬编码凭证 |
| 2 | **[AUTH]** 权限与访问控制 | 缺少 AUTHORITY-CHECK、未检查 SY-SUBRC、权限绕过模式 |
| 3 | **[DATA]** 数据完整性与异常处理 | FM 调用后 SY-SUBRC、写操作前加锁、空 CATCH 块 |
| 4 | **[PERF]** 性能风险 | LOOP 内 SELECT、SELECT *、全表扫描、内表类型选择不当 |
| 5 | **[STD]** ABAP 代码规范 | 废弃语句、硬编码业务值、超长方法、注释掉的代码 |
| 6 | **[INTERFACE]** 接口与集成风险 | RFC FM 中的对话消息、EXCEPTIONS 未完整声明、OData 后端权限检查 |
| 7 | **[CHANGE]** 变更影响评估 | 受影响数据库表、对 SAP 标准对象的修改、共享 INCLUDE、Transport 依赖 |
| 8 | **[COMP]** 合规与审计追踪 | PII 处理、过账双人控制、审计日志覆盖、职责分离路径 |
| 9 | **[FUNC]** 功能完整性（可选） | 业务场景覆盖、边界条件处理、逻辑与需求一致性 |

---

## 使用方法

### 发起审查

```
对程序 [PROGRAM_NAME] 进行安全与质量评估，
Transport [DEVKXXXXXX]，变更说明：[一句话业务目的]。
报告保存至 reports/ 目录。
```

### 包含功能性审查（可选）

如需执行 [FUNC] 维度，请在对话中附上需求文档路径，或直接描述需求内容。

### 输出

Agent 会将 Markdown 报告保存至你指定的 `reports/` 目录：

- 默认文件名：`ABAP_REVIEW_[PROGRAM_NAME]_[YYYYMMDD].md`
- 存在 CRITICAL 发现时：`CRITICAL_ABAP_REVIEW_[PROGRAM_NAME]_[YYYYMMDD].md`

---

## 报告结构

每份生成的报告包含以下章节：

1. **报告头部** — 程序名、Transport、变更说明、评估人、日期、评审范围
2. **执行摘要** — 3–5 句话概述发现结果和发布建议
3. **发布建议** — 🔴 NO-GO / 🟡 CONDITIONAL GO / 🟢 GO，附理由说明
4. **风险摘要** — 按严重级别统计发现数量
5. **详细发现** — 每个问题的代码证据、规则引用、风险说明、修复建议
6. **维度覆盖摘要** — 确认全部 9 个维度均已完成
7. **评审范围限制** — 列出无法读取的对象
8. **修复清单** — CRITICAL 和 HIGH 发现的行动项
9. **签字表格** — 开发者、技术负责人、发布经理、安全负责人签字栏

---

## 严重级别

| 级别 | 标签 | 对发布的影响 |
|------|------|------------|
| 🔴 | CRITICAL | 阻止发布 |
| 🟠 | HIGH | 应阻止发布 |
| 🟡 | MEDIUM | 下次 Sprint 修复 |
| 🟢 | LOW | 建议性意见 |
| ℹ️ | INFO | 无需操作 |

**特殊规则**：[SEC] 或 [AUTH] 维度中任何 HIGH 发现，发布决策等同 CRITICAL（自动 NO-GO）。

---

## 发布决策逻辑

```
存在 CRITICAL 发现                    → NO-GO
[SEC] 或 [AUTH] 中存在 HIGH 发现      → NO-GO（特殊规则）
其他维度存在 HIGH 发现                 → CONDITIONAL GO（需技术负责人签字）
仅 MEDIUM / LOW / INFO 发现           → GO
```

---

## 文件结构

```
abap-code-review/
├── SKILL.md                          ← Agent 指令文件（SKILL 定义；由 Agent 运行时加载）
├── README.md                         ← 英文说明文档
├── README.zh.md                      ← 本文件（中文）
└── references/
    ├── REF_ABAP_SECURITY.md          ← [SEC] 和 [AUTH] 维度的安全规则参考
    ├── REF_CLEAN_ABAP.md             ← [STD] 维度的 Clean ABAP 规则参考
    └── REPORT_TEMPLATE.md            ← Step 5 加载的报告模板
```

---

## 参考来源

| 参考文件 | 来源 |
|---------|------|
| `REF_ABAP_SECURITY.md` | SAP ABAP 关键字文档；SAP CVA 分类；RedRays ABAP Scanner（164 条规则）；CVE-2025-0063、CVE-2025-42957；DSAG ABAP 开发建议 |
| `REF_CLEAN_ABAP.md` | SAP Clean ABAP Style Guide（`github.com/SAP/styleguides`，CC BY 4.0） |

---

## 支持的对象类型

| 类型 | 读取范围 |
|------|---------|
| REPORT | 主程序 + 全部 INCLUDE |
| Global Class | 类定义 + 全部 METHOD 实现 |
| Function Module | 目标 FM + 同函数组其他 FM |
| Enhancement / BAdI | Enhancement Spot 定义 + 全部活跃实现 |

---

## 许可证

引用自 [SAP Clean ABAP Style Guide](https://github.com/SAP/styleguides/blob/main/clean-abap/CleanABAP.md) 的内容依据 [知识共享 署名 4.0 国际许可协议（CC BY 4.0）](https://creativecommons.org/licenses/by/4.0/) 使用。

本仓库其余内容为原创作品。
