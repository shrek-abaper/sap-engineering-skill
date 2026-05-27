# SAP 集成百科

> 一个标准化 skill，让任何 AI 助手都能成为 SAP 集成专家。
> 专为需要将外部系统与 SAP 对接的开发者设计——无需阅读数千页 SAP 官方文档。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![欢迎共建](https://img.shields.io/badge/共建-欢迎-brightgreen.svg)](CONTRIBUTING.md)
[![SAP 版本](https://img.shields.io/badge/SAP-ECC%20%7C%20S%2F4HANA%20%7C%20Cloud-blue.svg)](references/troubleshoot/version-diff.md)

[English](README.md) | [中文](README.zh-CN.md)

---

## 这是什么？

`sap-integration-wiki` 是一个遵循标准 skill 规范（`SKILL.md`）的**可组合知识库**。安装到你的 AI agent 框架后，任何 AI 助手都能加载对应的参考文档，并基于真实的 SAP API 文档给出精准、可落地的答案。

**没有这个 Skill 时**，AI 助手的回答往往笼统且不准确：
> "你可以使用 SAP RFC API 来创建采购订单。"

**安装后**，AI 给出可直接用于生产的指导：
> "在 S/4HANA On-Premise 上，使用 OData V2 `API_PURCHASEORDER_PROCESS_SRV` 的 Deep Insert POST 请求，一次性创建 PO 抬头和行项目。以下是包含科目分配的完整 Payload 结构，以及必须先实现的 CSRF Token 获取流程……"

---

## 覆盖场景

### 业务场景

| 模块 | 集成场景 |
|---|---|
| **MM — 采购** | 创建采购订单、读取 PO 状态、更新数量/价格、供应商 EDI 回单 |
| **MM — 库存** | 按工厂/库存地点查询库存、过账发料/收货、创建预留 |
| **SD — 销售** | 创建销售订单、跟踪发货状态、读取开票凭证 |
| **FI — 财务** | 过账 GL 凭证、读取财务凭证、科目确定 |
| **FI — 应收/应付** | 应收/应付未清项查询、账期读取、供应商发票创建、AP/AR 过账、预付款、凭证暂存 |
| **FI — 资产会计** | 读取资产台账、过账资产购置/报废/清理/转移，S/4HANA Cloud OData V4 |
| **FI — 财务共享（FSSC）** | 财务共享中心：金蝶↔SAP 集成模式（直连 API / BTP 中台 / Central Finance），API 目录，主数据映射 |
| **主数据** | 物料主数据读取/创建、业务伙伴（客户/供应商）、成本中心 |
| **PP — 生产** | 生产订单、BOM 读取、库存移动（261/101）、订单确认、MRP |

### 集成技术

| 技术 | 覆盖内容 |
|---|---|
| **OData V2 / V4** | CSRF 流程、`$expand`/`$filter`/`$batch`、Deep Insert、错误解析 |
| **RFC / SAP JCo** | 连接池、BAPI 调用模式、RETURN 表解析、负载均衡 |
| **SOAP over HTTP RFC** | 无需 JCo 直接调用任意 RFC 函数模块——Python/Node/curl 示例、CSRF 流程、响应解析 |
| **IDoc / PI-PO** | 控制记录、关键段、状态生命周期、监控事务码 |
| **BAPI & RAP** | 如何选择、各模块关键 BAPI、RAP OData V4 服务 |
| **认证鉴权** | Basic Auth、OAuth2（本地 SOAUTH2 + Cloud）、SSL/TLS、ICF 激活 |
| **BTP 集成套件** | iFlow、Cloud Connector、API Management、Event Mesh、通信安排 |
| **最佳实践** | 幂等性、重试逻辑、连接管理、安全加固、可观测性 |

---

## 安装方法

本 skill 遵循标准 skill 规范，包含 `SKILL.md` 元数据文件。安装步骤因你的 AI agent 框架而异：

### 示例：Claude Code

```bash
# 软链接到 Claude Code 的 skills 目录
ln -s /path/to/sap-integration-wiki ~/.agents/skills/sap-integration-wiki
```

### 示例：OpenAI Custom Instructions / System Prompt

添加到你的 agent 上下文：

```
在回答 SAP 集成问题时，加载知识库：
- /path/to/sap-integration-wiki/SKILL.md（路由逻辑）
- /path/to/sap-integration-wiki/references/scenarios/*.md（业务场景）
- /path/to/sap-integration-wiki/references/tech/*.md（技术指南）
- /path/to/sap-integration-wiki/references/troubleshoot/*.md（错误解决方案）
```

### 示例：LangChain / RAG 集成

```python
from langchain.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader

loader = DirectoryLoader(
    '/path/to/sap-integration-wiki',
    glob='**/*.md',
    loader_cls=UnstructuredMarkdownLoader,
    loader_kwargs={'mode': 'elements'}
)

documents = loader.load()
# 然后构建你的向量存储或检索链
```

### 验证

Skill 会通过 `SKILL.md` 元数据自动加载。更新你的 agent 的 skill 扫描路径以包含此目录。

---

## 快速开始

安装完成后，向你的 AI 助手询问 SAP 集成问题：

**示例提示词（语言无关）：**

```
如何用 Python 在 SAP S/4HANA 中创建采购订单？
```

```
SAP OData 接口一直返回 HTTP 403 CSRF token validation failed，怎么解决？
```

```
ECC 和 S/4HANA 用 BAPI_PO_CREATE1 还是 OData 接口创建 PO，有什么区别？
```

```
如何实时查询 SAP 库存？
```

Skill 会自动：
1. 识别你的 SAP 版本和集成场景
2. **从 references/ 加载相关参考文档（新增）**
3. 提供你所用语言（Java、Python、curl 等）的可运行代码示例
4. 指出针对你当前场景的常见陷阱

---

## 目录结构

```
sap-integration-wiki/
├── SKILL.md                          ← AI 路由逻辑与决策树
├── README.md                         ← 英文文档
├── README.zh-CN.md                   ← 本文件（中文）
├── CONTRIBUTING.md                   ← 共建指南
│
├── references/
│   ├── scenarios/                    ← 做什么（业务视角）
│   │   ├── mm-po.md                  采购订单集成
│   │   ├── mm-stock.md               库存集成
│   │   ├── sd-order.md               销售订单集成
│   │   ├── fi-doc.md                 财务凭证集成（GL 过账）
│   │   ├── fi-ar-ap.md               应收/应付集成（未清项、发票、付款）
│   │   ├── fi-asset.md               固定资产集成（购置、报废、转移）
│   │   ├── fi-fssc.md                财务共享中心（金蝶↔SAP、CFIN）
│   │   ├── master-data.md            物料主数据、业务伙伴
│   │   └── pp-production.md          生产订单、BOM、库存移动、MRP
│   │
│   ├── tech/                         ← 怎么做（技术视角）
│   │   ├── odata.md                  OData V2/V4 协议指南
│   │   ├── rfc-jco.md                RFC/JCo 连接与 BAPI 指南
│   │   ├── soap-rfc-http.md          SOAP over HTTP RFC——无需 JCo
│   │   ├── idoc-pi.md                IDoc 与 SAP PI/PO 指南
│   │   ├── bapi-rap.md               BAPI vs RAP 选型指南
│   │   ├── auth.md                   认证配置指南
│   │   ├── btp-cloud-integration.md  BTP 集成套件指南
│   │   └── best-practices.md         安全、重试、监控、测试最佳实践
│   │
│   └── troubleshoot/                 ← 如何排错
│       ├── odata-errors.md           HTTP 4xx/5xx 错误解决方案
│       ├── auth-errors.md            认证与 CSRF 错误解决方案
│       ├── idoc-errors.md            IDoc 卡住/状态 51 解决方案
│       └── version-diff.md           ECC 与 S/4HANA 行为差异
│
├── scripts/                          ← 可运行工具脚本
│   ├── gen-odata-postman.js          为任意 OData 服务生成 Postman 集合
│   ├── gen-jco-config.py             生成 JCo .jcoDestination 配置文件
│   └── gen-idoc-template.py          生成 IDoc XML 骨架文件
│
└── assets/                           ← 示例 Payload 与配置模板
    ├── payloads/
    │   ├── po-create.json            OData V2 创建 PO 的 POST 请求体
    │   ├── po-update.json            OData V2 更新 PO 行项目的 PATCH 请求体
    │   └── idoc-orders05.xml         ORDERS05 IDoc XML 示例
    └── configs/
        ├── oauth-template.json       S/4HANA On-Premise 的 OAuth2 配置模板
        └── jco-props.template        JCo 连接属性完整参考模板
```

---

## 脚本工具使用

### 生成 Postman 集合

为任意 SAP OData V2 服务生成可直接导入的 Postman 集合文件：

```bash
cd scripts
node gen-odata-postman.js \
  --service API_PURCHASEORDER_PROCESS_SRV \
  --host s4hana.example.com \
  --client 100 \
  --output po-collection.json
```

### 生成 JCo 配置文件

生成包含所有参数说明的 `.jcoDestination` 属性文件：

```bash
python3 gen-jco-config.py \
  --name SAP_PRD \
  --host s4hana.example.com \
  --sysnr 00 \
  --client 100 \
  --user RFC_USER \
  --output SAP_PRD.jcoDestination
```

### 生成 IDoc XML 骨架

为指定消息类型生成 IDoc XML 框架文件：

```bash
python3 gen-idoc-template.py \
  --msgtype ORDERS \
  --idoctype ORDERS05 \
  --sender-partner SAP_PROD \
  --receiver-partner EXT_SUPPLIER_001 \
  --output orders05-skeleton.xml
```

---

## 支持的 SAP 版本

| SAP 版本 | OData | RFC/BAPI | IDoc | BTP |
|---|---|---|---|---|
| ECC 6.0 | 仅自定义 | 完整支持 | 完整支持 | 通过 Cloud Connector |
| S/4HANA On-Prem 1909–2022 | OData V2（标准 API） | 完整支持 | 完整支持 | 通过 Cloud Connector |
| S/4HANA On-Prem 2023+ | OData V2 + V4（部分） | 完整支持 | 完整支持 | 通过 Cloud Connector |
| S/4HANA Cloud 公有云版 | 主要为 OData V4 | 外部不可用 | 受限 | 原生支持 |
| S/4HANA Cloud 私有云版 | OData V2/V4 | RFC 受限 | 通过 BTP | 原生支持 |

---

## 如何共建

我们欢迎来自全球 SAP 集成领域专业人士的贡献。你可以：

- **补充新场景** — 缺少 HR、WM/EWM、PM、QM 等模块的集成说明
- **完善现有内容** — 修正错误、补充示例、优化表述
- **添加代码示例** — 目前主要是 Java/Python，欢迎补充 .NET、Go、Node.js、Ruby 等
- **反馈问题** — API 名称有误、信息过时、示例无法运行
- **翻译内容** — 目前支持中英文，欢迎添加其他语言版本

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 开源协议

MIT 许可证 — 详见 [LICENSE](LICENSE)。

---

## 致谢

本项目内容基于以下公开的 SAP 官方文档及实际项目经验整理：
- [SAP Business Accelerator Hub](https://api.sap.com)
- [SAP Help Portal](https://help.sap.com)
- [SAP Community](https://community.sap.com)
- 真实 SAP 集成项目的一线实践经验

---

## 免责声明

本项目为社区独立项目，与 SAP SE 没有任何关联，未获 SAP SE 官方背书或支持。SAP、S/4HANA、ECC、BTP 等产品名称均为 SAP SE 的商标。在实际使用中，请始终以你所在 SAP 版本和系统配置的官方文档为准。
