# Watt: name, purpose and engineering principles

**Power your SAP Engineering.**

Watt is an engineering CLI for SAP lifecycle work. Its audience is not limited
to a job title: implementation, functional consulting, development, testing,
delivery and operations all need dependable technical facts and controlled
actions. People can invoke it directly; AI agents can call the same contract.

## An independent name

Watt takes its name from the unit of power, named in honor of James Watt.
Power is the rate of doing work. Steady, sustained and controllable engineering
work is our design goal, not a performance guarantee implied by the unit.
The name stands on its own; no relationship with another AI product is implied.
Watt is an independent community project, not an official SAP product.

## Principles

1. **Evidence first.** Distinguish observed facts, hypotheses and missing evidence.
   An accepted request is not a verified outcome. Unknown results do not authorize
   replay, and incomplete evidence never becomes an approval.
2. **Explicit authority.** Read-only by default; source writes, transports,
   execution and debugging retain their distinct capability and confirmation
   rules. Authorized execution can change business data even when generic
   source writes are disabled. Human approvals remain human responsibilities.
3. **A reliable tool boundary.** The CLI provides bounded operations, structured
   output, stable errors and traceable outcomes. Skills provide workflows and
   domain references; agents provide reasoning and orchestration. The CLI
   does not embed an LLM or pretend to be a universal assistant.
4. **Lifecycle direction, incremental delivery.** ADT/ABAP is the current
   foundation, not the long-term product boundary. Expand through verified
   SAP work scenarios, not a claim of complete functional coverage.
5. **Compatibility is part of reliability.** `sap-watt` and `sap-adt` share one
   implementation. Preserve configuration, credential identifiers and scripts;
   never require migration merely to refresh a brand.

## Current scope and naming

Current primitives cover ADT/ABAP source and metadata, diagnosis evidence,
governed changes, testing and execution. Companion Skills add code review,
transport risk assessment and integration guidance. System support and live
verification remain specific to the endpoint, platform and release.

The preferred package/command is `sap-watt`; `sap-adt-cli` / `sap-adt` remain
compatible. Internal modules, native assets and Skill IDs keep their existing
names during this transition. Functional Skill names remain explicit; there is
no additional electrical-unit naming hierarchy and no default `watt` command.
Terminal output stays functional: no unsolicited brand banner in JSON or pipes.

---

## 中文定位

**Watt：面向 SAP 全生命周期工作的工程 CLI。**

名称取自功率单位瓦特，寄托稳定、持续、可控的工程动力这一设计追求。
服务范围不以开发者身份为界，也不局限于诊断或变更治理：面向实施、顾问、
开发、测试、交付与运维中的工程工作，可由人直接使用，也可供 AI Agent 调用。

当前以 ADT 与 ABAP 能力为起点，不代表已覆盖全部 SAP 工作。CLI 提供确定、
受控的操作与证据；Skill 提供工作流程和领域参考，Agent 负责理解与编排。
默认只读；写入、执行和调试受各自权限及确认机制约束，执行可能影响业务数据。
证据不足就明示缺口，不替代人工审批，不自动将未知结果重试为成功。

Watt 是独立社区项目，非 SAP 官方产品。品牌不依附其他 AI 产品；可靠性来自
明确的能力边界、真实验证与兼容承诺，而不是名称或物理意象。
