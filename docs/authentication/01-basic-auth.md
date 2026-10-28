# 01 HTTP Basic Authentication

最基础、兼容性最好的认证方式，也是库存技能当前使用的方式。理解它的链路、风险与改进点，是评估其他方式的基线。

## 1. 原理与认证流程

**【标准实践】** HTTP Basic Auth（RFC 7617）：客户端将用户名与口令用冒号拼接后做 Base64 编码，每个请求都携带：

```http
POST /sap/bc/rest2rfc?RFC=BAPI_MATERIAL_GETLIST&sap-client=800 HTTP/1.1
Host: <gateway-host>:<port>
Authorization: Basic base64("<user>:<password>")
Content-Type: application/json; charset=utf-8
```

```text
客户端                         SAP ICM/SICF
  │  POST + Authorization: Basic  │
  │ ────────────────────────────▶ │  ICM 解码，ICF 登录模块校验用户/口令
  │                               │  通过 → 以该 SAP 用户上下文执行 handler
  │  ◀────────────────────────── │  失败 → 401（带 WWW-Authenticate: Basic）
```

要点：

- Base64 **不是加密**，只是编码；因此 Basic 必须运行在 HTTPS 之上，或在受保护的内网（后者是风险接受，不是安全）。
- 每个请求都带凭据，服务端通常不维持"登录态"；SAP 客户端号通过 URL 参数 `sap-client` 或 cookie 指定。
- 401/403 是两个不同语义：401 = 未认证/凭据无效；403 = 已认证但授权不足（缺 `S_RFC` 等对象）。

## 2. 前提条件

| 条件 | 说明 |
|---|---|
| SICF 节点启用 | 对应服务节点（如 `/sap/bc/rest2rfc`）在 `SICF` 中已激活，登录过程包含 Basic |
| 用户可登录 | `SU01` 中用户存在、未锁定、口令有效；服务类型用户需设为可通信/按需 |
| 授权对象 | 调用 RFC 的账号需 `S_RFC` 及各功能模块的只读/业务权限 |
| 传输安全 | 推荐 HTTPS；自签名内网证书可在客户端显式关闭校验（风险自担） |

**【已验证】** 权威版本仓库中库存技能环境的当前拓扑：

```text
http://<gateway-host>:<port>/sap/bc/rest2rfc （HTTP 明文，内网）
client=<sap-client>，个人账号 <sap-user>，TLS 校验关闭
```

## 3. SAP 侧落地

对自研网关（REST2RFC 是 Z handler）而言，Basic 不需要任何额外开发，ICF 标准登录栈直接支持。需要检查/调整的只有：

1. **`SICF`**：定位服务节点 → 编辑 → "登录数据"（Logon Data）页确认过程设置；通常保持"标准登录"，Basic 默认在列。
2. **`SU01`**：为每个使用者维护个人账号，授予最小权限；避免多用户共用一个账号。
3. **`SMICM`**：如启用 HTTPS，确认 ICM HTTPS 端口与服务器证书已配置（见 03 章）。
4. 口令策略由实例参数与登录策略控制（`RZ10` / `SU01` 登录策略），定期轮换会直接影响所有客户端。

## 4. 客户端落地

### 4.1 参考实现（已验证）

本仓库的 ADT CLI 在 `src/sap_adt/adt/client.py`（`make_adt_request`，写操作前另含 CSRF fetch）。核心调用形态：

```python
resp = requests.post(
    base,
    params={"RFC": func, "sap-client": conn["client"]},
    auth=HTTPBasicAuth(creds.user, creds.password),
    headers={"Content-Type": "application/json; charset=utf-8",
             "Accept": "application/json"},
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    verify=verify_option(conn),
    timeout=int(conn.get("timeout", 60)),
)
# 401/403 直接失败，不重试
if resp.status_code in (401, 403):
    fail(EXIT_AUTH, "AUTH_REQUIRED",  # 其余参数略
         status=resp.status_code, user=creds.user)
```

非机密连接信息在 `connection.json`（host/path/client/user/TLS）；**口令不进配置文件**。

### 4.2 凭据库体系（已验证）

本仓库 ADT CLI 的 `src/sap_adt/keystore/` 实现可插拔后端，**按能力探测选择，不按操作系统选择**（WSL 报告 Linux 但实际可用后端是 Windows DPAPI）：

```text
env（SAP_ADT_<PROFILE>_PASSWORD） → keyring → dpapi（WSL） → pass → file（scrypt+Fernet）
```

设计纪律：

- **fail-closed**：取不到凭据直接退出码 3，绝不回退共享账号、不在非交互运行中卡住；
- `Credentials` 对象在 `__repr__`/`__str__` 中掩码口令（traceback 是 CLI 最常见的口令泄漏途径）；
- DPAPI 后端通过 stdin 向 `powershell.exe` 传递秘密，避免 argv 被 `ps` 看到；
- 没有 export 动作，口令永远不被打印。

### 4.3 最小代码骨架（供新项目复制）

```python
import requests
from requests.auth import HTTPBasicAuth

resp = requests.post(
    "https://<gateway-host>:<port>/sap/bc/<service>",
    params={"sap-client": "800"},
    auth=HTTPBasicAuth("<user>", "<password-from-secret-store>"),
    headers={"Content-Type": "application/json", "Accept": "application/json"},
    data=json.dumps(payload),
    verify="/path/to/ca-bundle.pem",  # 生产环境必须开启校验
    timeout=60,
)
resp.raise_for_status()
```

依赖：`requests>=2.28`。

### 4.4 用户配置动作（当前形态）

```bash
sap-adt credentials set <profile>  # getpass 无回显
sap-adt credentials doctor         # 后端诊断
sap-adt configure                  # 向导式建档
```

## 5. 用户映射与授权

Basic 的"映射"就是 SAP 用户名本身，不存在额外映射层。需要关注：

- 一人一号；授权按角色分配（库存技能要求 `S_RFC` + 各只读权限对象）；
- 服务类型技术账号用于 CI 时，应锁定对话登录、仅授 RFC 所需最小权限；
- 审计日志（`SM20` Security Audit Log）记录的是真实个人账号，这是 Basic 相对共享账号方案的核心优点。

## 6. 优点 / 缺点

**优点**

- 零开发、协议简单，任何语言/平台都支持；
- 按人认证，SAP 侧权限检查与审计完整；
- 对开发者、CI、临时脚本足够友好；可与其他方式并存兜底。

**缺点（按视角）**

- *业务用户*：首次使用要理解"OS 凭据库/keystore"概念并手工配置，部署支持成本高；
- *安全*：口令长期有效、以可逆形态存于每台客户端；明文 HTTP 下可被窃听；口令轮换后所有客户端需重新配置；
- *管理员*：每增加一个终端环境就要存一次口令；账号锁定/过期问题分散在用户机器上，难排查。

## 7. 适用与不适用场景

适用：开发者工具（如 `sap-adt-cli`）、CI/定时任务（技术账号 + 环境变量注入）、过渡期快速打通、内网临时集成。

不适用（应升级方案）：大规模业务用户推广、外网传输、合规要求 MFA/短期凭证、无法接受口令落客户端的场景。

## 8. 故障排查

| 现象 | 可能原因 | 处理 |
|---|---|---|
| 401 `AUTH_REQUIRED` | 口令错/过期/被锁 | 重新 `credentials set`；`SU01` 检查锁定状态 |
| 403 | 凭据有效但权限不足 | `SU01`/角色对比，检查 `S_RFC` 及业务对象 |
| `NO_CREDENTIAL` | 凭据库无记录 | 执行 `credentials set`；先 `doctor` 看后端 |
| `NO_KEYSTORE` | 无任何可用后端 | headless 环境装 `cryptography` 用文件后端，或注入环境变量 |
| TLS 错误 | 自签名/CA 不被信任 | 配置 `ca_bundle`；仅内网可临时 `verify=false` |
| 频繁锁定 | 多处存了旧口令反复登录 | 清理各机器旧凭据，统一重设 |

## 9. 安全注意事项

1. **生产/外网必须 HTTPS**：Basic over HTTP 等同口令明文传输。
2. **口令不得写入配置文件、git、命令行参数、日志**；CLI 必须对凭据对象做 repr 掩码。
3. 技术账号最小授权、禁止对话登录；CI 用密钥管理系统注入，不落盘。
4. 保留 Basic 作为多认证架构的兜底时，应在 `doctor` 输出中明确当前生效方式，便于审计。
5. 用户若把口令直接粘贴进对话：提示该消息已泄露、应在 SAP 侧改密，改用凭据库录入，且不要复述该口令。

## 过渡改进（不改后端即可做）

将"理解 keystore"降级为"登录"这一所有人都理解的动作：新增 `login` 子命令，交互式输入一次口令后自动写入当前可用后端；`doctor` 给出下一步指令。这是后续多认证架构的天然入口（见 [06 客户端通用模式](06-client-patterns.md)）。
