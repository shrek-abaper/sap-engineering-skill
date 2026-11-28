# Watt: engineering principles and boundaries

The [homepage](../README.md#meet-watt) introduces Watt's name, audience and
purpose. This document explains the mechanisms and constraints behind its
principles.

## Principles

1. **Evidence first.** Distinguish observed facts, hypotheses and missing evidence.
   An accepted request is not a verified outcome. Unknown results do not authorize
   replay, and incomplete evidence never becomes an approval.
   HTTP 2xx is acceptance evidence; source writes need readback and activation
   needs an active-version check. Stage results distinguish `accepted`,
   `verified`, `failed` and `unknown`.
2. **Explicit authority.** Read-only by default; source writes, transports,
   execution and debugging retain their distinct capability and confirmation
   rules. Authorized execution can change business data even when generic
   source writes are disabled. Human approvals remain human responsibilities.
   Writes bind the reviewed system, client, user, object, transport, baseline
   and content hash; drift prevents the write. Automation skips the interactive
   prompt, not those checks. Production restrictions and credential handling
   remain in force.
3. **A reliable tool boundary.** The CLI provides bounded operations, structured
   output, stable errors and traceable outcomes. Skills provide workflows and
   domain references; agents provide reasoning and orchestration. The CLI
   does not embed an LLM or pretend to be a universal assistant.
   JSON envelopes, a closed error-code set and tiered exit codes form the
   command contract. Portable `SKILL.md` folders carry orchestration rather than
   binding it to one agent vendor.
4. **Lifecycle direction, incremental delivery.** ADT/ABAP is the current
   foundation, not the long-term product boundary. Expand through verified
   SAP work scenarios, not a claim of complete functional coverage.
   Offline fixtures, native platform checks and live SAP verification are
   different evidence. Record the endpoint, platform and release actually
   verified; a synthetic test does not certify live behavior.
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

<a id="中文定位"></a>

## 中文工程约束

名称、受众与定位见[首页](../README.zh-CN.md#认识-watt)。本页只展开工程机制与约束：

1. **证据语义。** HTTP 2xx 只代表受理；源码写入需要回读，激活需要核对激活版本。
   阶段结果区分 `accepted`、`verified`、`failed` 和 `unknown`。缺口不冒充通过，
   未知执行结果不自动重放。
2. **意图与授权。** 写入绑定已审阅的系统、Client、用户、对象、传输请求、基线与内容
   hash，发生漂移就停止。自动化只省去交互，不跳过校验；写入、传输、执行、调试
   各自保留权限及确认机制。关闭源码写开关不代表执行不会影响业务数据。
3. **职责与契约。** CLI 提供限界操作、JSON 信封、封闭错误码与分级退出码；
   Skill 承载流程和领域参考，Agent 负责理解与编排。不内嵌大模型，不代替人工审批。
4. **验证范围。** 离线样本、原生平台检查和真实 SAP 验证是不同证据。明确端点、
   平台和版本，不把合成测试说成真机认证，不把拓展方向说成已覆盖能力。
5. **兼容约束。** `sap-watt` 与 `sap-adt` 共享实现；保留既有配置、凭据标识和脚本
   契约。过渡期不改内部模块、原生资产、Skill ID 或插件 ID；不默认安装裸命令 `watt`。
