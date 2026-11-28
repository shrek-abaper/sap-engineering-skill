# WorkBuddy

通过 WorkBuddy 技能市场安装 Watt Skills，无需手动复制技能目录。
四个 Skills 已发布至 SkillHub，可按需搜索安装；安装 Skill 不会同时安装 CLI，
也不会授予 SAP 系统访问或操作权限。

## 从技能市场安装

1. 在 WorkBuddy 左侧打开 **专家·技能·连接器**，选择 **技能** 页签。
2. 在 **技能市场** 中切换到 **SkillHub** 分类，搜索下表中的技能名称。
3. 通过 [Watt 的 SkillHub 发布空间](https://skillhub.cn/user/user_1478bd29)
   核对技能名称、简介与来源，不要只凭同名结果安装。安装前查看权限与数据使用说明。
4. 点击目标技能卡片右上方的 **+** 安装。
5. 在 **已安装** 中确认该技能已启用，再在对话中描述任务或明确指定技能名称。

界面名称与布局可能随 WorkBuddy 版本变化；具体操作可参考
[WorkBuddy 官方技能说明](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)。

## 选择需要的技能

| 搜索名称 | 主要用途 | 是否需要 CLI 与 SAP 连接 |
|---|---|---|
| `abap-code-review` | 审查你提供的 ABAP 源码，输出有代码与规则依据的发现 | 不需要 |
| `sap-transport-gate` | 核对传输请求的变更风险、需求与测试证据 | 离线材料审查不需要；在线采集才需要 |
| `sap-integration-wiki` | 查询 SAP 与 Java、Python、.NET、Node.js、BTP 等的集成方式 | 不需要 |
| `sap-adt-cli` | 在线开发、诊断、测试、变更与工程证据工作流 | 在线操作需要；解释已有材料不需要 |

不必一次安装全部技能。只想先体验时，安装 `abap-code-review`，
使用一份允许分享的 ABAP 源码即可开始。

## 从离线审查开始

在对话中提供源码，并提出具体请求，例如：

```text
请使用 abap-code-review 审查我提供的 ABAP 源码。
本次只做代码质量与发布风险审查，不连接 SAP。
没有功能规格，请将功能完整性标为 N/A。
每项发现请引用真实代码和相应规则，列出缺失证据。
```

这是示例请求，不是已执行结果。不要提供密码、客户数据或未经授权的专有代码；
使用前了解 WorkBuddy 及其模型的数据处理方式。审查报告提供决策依据，不替代人工审批。

## 需要在线 SAP 操作时

按共享的 [CLI 安装与运行准备指南](../installation/runtime-setup.md)
单独安装并配置 CLI。优先使用兼容的 `sap-watt`，已有兼容 `sap-adt` 时也可继续使用；
一次任务保持同一个命令前缀。

WorkBuddy 执行工具的环境必须能运行该 CLI，并访问目标 SAP 系统。
本机已安装 CLI 不代表 Agent 的执行环境一定可见；遇到找不到命令时先核对执行环境与 PATH，
不要直接重复安装。密码只在本地配置流程中输入，不要粘贴到对话中。

源码写入、传输变更、执行和调试保留独立授权与逐次确认要求。
安装或启用 Skill 不等于批准这些操作；执行和调试即使未开启源码写入，也可能改变业务数据。

## 搜不到或需要手动导入时

先核对搜索名称、市场分类与客户端版本，并通过上方 SkillHub 发布空间确认条目信息。
市场搜索结果不可用时，可从本仓库的 [Releases](https://github.com/shrek-abaper/sap-watt/releases)
取得对应 Skill 的完整技能包，再在 WorkBuddy 中选择
**添加技能 → 上传技能** 导入。

如需从源码安装，按 [通用 Skill 接入说明](generic-skills.md) 获取完整目录，
包含 `references/` 与兼容性文件，不要只复制 `SKILL.md`，也不要混用不同发布版本的文件。
确认客户端支持的导入方式与目录后再操作，不自动安装或升级。

## 更新与兼容

SkillHub 已发布版本与 GitHub 主分支可能存在发布时间差，
不要假定市场安装包会实时同步仓库更新。
使用在线能力前，核对已安装 Skill 附带的 `references/runtime-compatibility.json`、
CLI 版本和所需命令选项；缺少可选功能不应阻止无关的离线任务。

需要更新时先确认来源、变更与兼容要求，再由你决定是否更新。
GitHub 仓库仍是项目源码与工程说明的维护入口。
