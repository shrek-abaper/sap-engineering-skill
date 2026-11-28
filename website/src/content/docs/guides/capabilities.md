---
title: 能力与 Skills
description: Watt 当前支持的 SAP 工程场景、四个 Skills 及对应 CLI 入口。
---

## 一个底座，三类职责

**CLI 让操作可靠，Skills 让经验复用，Agent 让工作协同。**

CLI 提供契约明确、可组合、有边界的工程操作；Skills 承载领域知识、任务流程与质量准则；
Agent 结合上下文进行推理和协调。人员始终保留决策与审批责任。
“原子能力”描述的是可组合的工程边界，并不表示一条命令只发出一个 HTTP 请求。

Watt **面向 SAP 全生命周期演进**，当前以 ADT / ABAP 为基础，不宣称覆盖所有业务模块或全部交付环节。

## 当前能力地图

以下为能力导航，不是完整命令或参数清单。CLI 统一使用 `sap-watt` 前缀，也支持兼容的 `sap-adt`。

| 领域 | 当前能力 | 代表 CLI |
|---|---|---|
| 系统理解 | 搜索对象、源码与 DDIC 查询、静态引用与影响证据 | `search-object`、`get-class`、`get-table`、`where-used` |
| 受控开发 | 候选源码检查、源码写入、对象创建、受控多对象变更 | `check-source`、`write-source`、`create-object`、`apply-change-set` |
| 质量与验证 | 语法、ATC、Unit 回归与 JUnit、质量证据汇总 | `syntax-check`、`run-atc`、`run-unit-test`、`quality-check` |
| 诊断与执行 | Dump 与诊断取证、显式 ABAP/函数执行、实验性调试 | `get-dump`、`diagnose`、`run-abap`、`run-function`、`debug …` |
| 传输与交付 | 材料采集、差异与静态风险分析、跨系统对象比较、交付证据打包 | `transport collect`、`transport diff`、`transport analyze`、`transport compare`、`delivery pack` |
| 数据与集成观察 | SELECT 预览、配置快照与比较、只读 RAP/OData 检查 | `run-sql`、`config-data read`、`config-data compare`、`get-rap`、`odata-read` |

在线能力取决于 CLI 版本、SAP 端点与权限。调试仍为实验性；静态影响分析不证明动态依赖完整，
跨系统对象比较不预测实际导入结果，OData 读取不包含服务发布或业务写入。

## 四个 Skills

| Skill | 适用任务 | 是否需要 SAP 连接 |
|---|---|---|
| [`sap-adt-cli`](https://github.com/shrek-abaper/sap-watt/tree/main/skills/sap-adt-cli) | 在线开发、诊断、测试、变更与工程证据工作流 | 在线操作需要 CLI 与连接；解释已有材料不需要 |
| [`abap-code-review`](https://github.com/shrek-abaper/sap-watt/tree/main/skills/abap-code-review) | 九个维度的 ABAP 代码审查与证据化报告 | 不需要，由你提供源码 |
| [`sap-transport-gate`](https://github.com/shrek-abaper/sap-watt/tree/main/skills/sap-transport-gate) | 十个维度的传输风险评估与证据缺口识别 | 离线材料不需要；在线采集才需要 |
| [`sap-integration-wiki`](https://github.com/shrek-abaper/sap-watt/tree/main/skills/sap-integration-wiki) | SAP 与 Java、Python、.NET、Node.js、BTP 等的集成指导 | 不需要 |

## 场景如何组合

例如“评估一个传输请求是否具备进入下一环境的条件”：

1. CLI 在明确范围内采集对象和变更材料。
2. Skill 引导 Agent 核对源码、依赖、需求与测试证据。
3. Agent 区分已观察事实、风险假设和证据缺口，生成可审阅报告。
4. 人工作出审批决定；风险报告不会自动授权发布。

这是一条工作流示意，不是实际系统运行记录。材料不足时必须明确 `EVIDENCE_GAP`；
低证据水平不能给出通过结论。

## 进一步阅读

- [完整 CLI 清单](/sap-watt/reference/commands/)：来自 CLI Skill 的权威命令索引。
- [输出与错误契约](/sap-watt/reference/contracts/)：结构化输出与退出语义。
- [原子执行器与交付证据](/sap-watt/reference/workflows/executor/)：目标绑定、影响证据和交付包边界。
- [设计理念与工程边界](/sap-watt/principles/)：为什么将能力、流程与推理解耦。
