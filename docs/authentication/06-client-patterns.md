# 06 客户端通用模式：策略抽象、令牌存储与 fail-closed

本章沉淀与具体认证方式无关的客户端工程模式，供任何 SAP HTTP 客户端（CLI / AI Agent 包装器）复用。库存技能后续落地多认证时应直接套用。

## 1. 可插拔认证策略

### 1.1 目标

- 业务代码只发请求，不关心当前是 Basic / SPNEGO / OIDC；
- 认证方式由配置选择；新增方式时调用方零改动；
- 每种方式可独立做"就绪探测"与身份展示。

### 1.2 策略接口

```python
from abc import ABC, abstractmethod
import requests

class AuthStrategy(ABC):
    name: str

    @abstractmethod
    def configure(self, session: requests.Session) -> None:
        """把认证挂到会话上：session.auth 或默认头。"""

    def probe(self) -> tuple[bool, str]:
        """本地就绪检查（不发业务请求）：依赖是否可导入、票据/令牌是否存在。"""
        return True, "ready"

    def identity(self) -> str | None:
        """doctor 展示的用户标识。"""
        return None
```

### 1.3 三个实现（对应 01/02/04 章）

```python
from requests.auth import HTTPBasicAuth

class BasicStrategy(AuthStrategy):
    name = "basic"
    def __init__(self, user: str, password: str):
        self.user, self.password = user, password
    def configure(self, session):
        session.auth = HTTPBasicAuth(self.user, self.password)
    def identity(self):
        return self.user

class KerberosStrategy(AuthStrategy):
    name = "kerberos"
    def probe(self):
        try:
            import requests_gssapi           # 或 requests_kerberos
        except ImportError:
            return False, "KERBEROS_UNAVAILABLE：未安装 requests-gssapi/requests-kerberos"
        # 进一步检查票据缓存：WSL/Linux 解析 klist；Windows SSPI 视为可用
        return True, "ready"
    def configure(self, session):
        try:
            from requests_gssapi import HTTPSPNEGOAuth, DISABLED
            session.auth = HTTPSPNEGOAuth(mutual_authentication=DISABLED)
        except ImportError:
            from requests_kerberos import HTTPKerberosAuth, DISABLED
            session.auth = HTTPKerberosAuth(mutual_authentication=DISABLED)

class BearerStrategy(AuthStrategy):
    name = "oidc"
    def __init__(self, token_manager):       # 见 §3
        self.tm = token_manager
    def probe(self):
        if not self.tm.has_tokens():
            return False, "OIDC_NOT_LOGGED_IN：先执行 login"
        return True, "ready"
    def configure(self, session):
        session.headers["Authorization"] = f"Bearer {self.tm.access_token()}"
    def identity(self):
        return self.tm.identity()
```

### 1.4 工厂与自动模式

```python
def build_strategy(conn: dict) -> AuthStrategy:
    kind = (conn.get("auth") or {}).get("type", "basic")
    if kind != "auto":
        strategy = {"basic": BasicStrategy, "kerberos": KerberosStrategy,
                    "oidc": BearerStrategy}[kind].from_conn(conn)
        ok, reason = strategy.probe()
        if not ok:
            fail(3, reason)                 # fail-closed：不可用即退出码 3
        return strategy

    for candidate in (KerberosStrategy(...), BearerStrategy(...), BasicStrategy(...)):
        ok, _ = candidate.probe()
        if ok:
            return candidate
    fail(3, "NO_AUTH_METHOD：执行 login 或检查域登录")
```

自动模式探测顺序建议：Kerberos 票据 → OIDC 令牌 → Basic 凭据；`doctor` 必须报告本次实际命中的方式。

## 2. fail-closed 与不静默降级

**【已验证的设计原则】**（库存技能凭据层与 `--keystore` 强制选项均遵循）：

1. 指定方式不可用 / 未登录 / refresh 失效 → **直接报错并给出修复指令**，绝不在方式间自动回落；
2. 不回退共享服务账号；非交互运行中不弹提示、不挂起；
3. 401/403 不自动重试（避免锁号与掩盖配置问题）；CSRF 403 这种**协议规定可重试**的场景除外；
4. 错误要**类型化**：`NO_CREDENTIAL` / `AUTH_REQUIRED` / `KERBEROS_UNAVAILABLE` /
   `OIDC_NOT_LOGGED_IN` / `OIDC_RELOGIN`，调用方（Agent）按码行动而非猜测。

典型退出码协议（权威版本仓库库存技能 `sap_stock.py` 中的实现）：

| 码 | 语义 | 动作 |
|---|---|---|
| 0 | 成功 | 继续 |
| 2 | 报文/参数错误 | 修正后最多重试一次 |
| 3 | 认证/凭据问题 | 引导 login，不重试 |
| 4 | 函数未注册 | 告知网关注册，不改走他路 |
| 5 | 超时/结果过大 | 收窄筛选 |

## 3. 令牌存储

### 3.1 两种方案对比

| 方案 | 优点 | 缺点 |
|---|---|---|
| 全部存 OS 凭据库 | 机密强度一致 | 每次刷新都重写库；WSL DPAPI 每次拉起 `powershell.exe`（约数百 ms）；只读 env 后端不可用 |
| **refresh 进凭据库，access 进 600 文件（推荐）** | 刷新快、实现简单；长期秘密仍受库保护 | access 落盘（短期、且每次调用本来就要在线出示） |

### 3.2 推荐布局

```text
~/.sap-stock/
├── oidc.json        # 600：access_token、id_token、exp（短寿命，明文但短期）
└── <keystore>       # refresh_token 存入第一个可用的可写后端
```

### 3.3 最小令牌管理器

```python
import base64, json, os, time
from pathlib import Path

class TokenManager:
    def __init__(self, token_file: Path, store, store_key: str):
        self.file, self.store, self.key = token_file, store, store_key
        self._load()

    def _load(self):
        self.access = self.exp = None
        if self.file.exists():
            blob = json.loads(self.file.read_text())
            self.access, self.exp = blob.get("access_token"), blob.get("exp")

    def has_tokens(self) -> bool:
        return self.access is not None or self.store.get(self.key) is not None

    def access_token(self) -> str:
        if self.access and self.exp - 60 > time.time():
            return self.access
        refreshed = self._refresh()         # 用 refresh token 换新
        self._save_access(refreshed)
        return refreshed["access_token"]

    def _refresh(self):
        refresh_token = self.store.get(self.key)
        if not refresh_token:
            raise RuntimeError("OIDC_NOT_LOGGED_IN")
        tokens = refresh_at_idp(refresh_token)     # 04 章 §4.4
        if "refresh_token" in tokens:
            self.store.set(self.key, tokens["refresh_token"])
        return tokens

    def identity(self) -> str | None:
        if not (self.file.exists()):
            return None
        idt = json.loads(self.file.read_text()).get("id_token", "")
        return _jwt_claim(idt, "preferred_username")
```

### 3.4 JWT 本地解码的边界

```python
def _jwt_claim(jwt_text: str, name: str):
    _h, payload, _sig = jwt_text.split(".")
    padded = payload + "=" * (-len(payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(padded))
    return claims.get(name)
```

**本地不验签**：解码只用于读 `exp`（决定何时刷新）和显示身份。篡改本地文件最多影响刷新时机与显示，**骗不过网关**；不得把本地解码结果当作授权依据。

## 4. 机密泄漏防护（日志/traceback）

**【已验证】** 两个真实泄漏路径及对策：

1. **traceback 打印凭据对象**：`Credentials`/配置对象必须在 `__repr__`/`__str__` 掩码口令（本仓库 ADT CLI：`src/sap_adt/credentials.py` 与 `src/sap_adt/config.py` 的 `SapConfig.__repr__`）。
2. **requests 的 `PreparedRequest` repr 带 Authorization 头**：异常链中若保留原始 `RequestException`，链上对象会暴露头部。捕获后重写异常并丢弃原链（`raise ... from None`），并用实时口令做日志正文脱敏（`src/sap_adt/adt/client.py` 的 `raise ... from None` 是参考实现）。

其他纪律：

- 秘密走 stdin / 环境，不进 argv（`ps` 可见）；临时文件用完即删；
- 错误消息中过滤含 `token/password/secret` 的查询参数，正文截断长度；
- 不提供 export 动作。

## 5. CI / 非交互路径

| 场景 | 方式 | 身份性质 |
|---|---|---|
| CI 调只读/写接口 | 技术账号口令由密钥系统注入环境变量（如 `REST2RFC_PASSWORD`） | 技术账号（单独授权、禁对话登录） |
| 企业支持工作负载联邦 | OIDC 平台签发短期联邦令牌（GitHub Actions 等 OIDC 与企业 IdP 交换） | 工作负载身份，按需映射 |
| 无人值守定时任务 | 同上；或服务账号 + 凭据库 | 技术身份 |
| WSL 开发者日常 | `kinit`（SPNEGO）或设备码/浏览器登录一次（OIDC） | 个人 |

注意：

- 设备码流需要人输码，**不适合 CI**；
- `client_credentials` 得到的令牌代表应用而非人，SAP 侧应映射到技术用户、单独审计，不能冒充个人；
- 所有非交互路径仍遵守 fail-closed：凭据缺失即失败，不在 CI 里挂起。

## 6. 可选依赖的运行时探测

**【已验证】** 库存技能对 `keyring`/`cryptography` 及 WSL DPAPI 均采用能力探测，不按 `platform.system()` 分支。同样适用于：

```python
def import_optional(module: str):
    try:
        return __import__(module)
    except ImportError:
        return None

# 注意"假可用"：keyring 能导入但后端是 fail.Keyring；powershell 在 PATH 但调用失败。
# 必须做真实握手/试调用，不能只判断导入成功或操作系统类型。
```

requirements 中把可选依赖写成注释，由用户按环境启用，保持核心零重依赖。

## 7. 与应用层会话的关系

CSRF token、stateful 会话（sap-adt-cli 场景）与认证策略**正交**：

- 认证策略负责"我是谁"（session.auth / Bearer 头）；
- CSRF/cookie 负责"写操作与会话连续性"，在认证建立后获取；
- 因此切换认证方式时，CSRF 获取、cookie jar、stateful 流程逻辑不需要改动，只需让它们经由已配置的 session 发出。

## 8. AI 工具（MCP / CLI）集成约束

MCP server、Agent 包装 CLI 等 AI 工具可以使用本手册的**任何**认证方式，但有一条决定性约束：

> **交互式登录必须在带外（out-of-band）一次性完成，AI 工具进程在请求链路中始终非交互。**

### 8.1 为什么 stdio 形态决定一切

本地 MCP 最常用 stdio 传输，进程拓扑为：

```text
MCP Client（Claude Desktop / Claude Code 等）
   │ spawn：command + env（来自 .mcp.json 等配置）
   ▼
MCP Server 进程
   stdin  ── JSON-RPC 请求（协议通道，不是 TTY）
   stdout ── JSON-RPC 响应（协议通道）
   stderr ── 唯一可写日志的通道
   │ shell out
   ▼
<cli>.py call ...     # 如 sap-adt 或业务技能自带 CLI
```

三条硬限制：

1. 处理工具调用时**禁止 `getpass`/读 stdin**——stdin 是 JSON-RPC，读一个字节协议即损坏；
2. **禁止往 stdout 写提示**——非 JSON-RPC 内容会导致客户端解析失败，提示只能写 stderr；
3. 工具由配置启动，**请求路径内不能假设"人在终端前"**——设备码"打印 URI 等人输码"也不得发生在调用中。

因此 MCP server 应按**无人值守进程**设计（与 §5 的 CI 路径同构）：`login` 是与 server 分离的运维动作，用户在普通终端执行一次；登录产物（keystore 条目、600 令牌文件）因同一 OS 用户而对 server 进程可见。

### 8.2 各方式在 MCP 下的形态

| 方式 | 请求路径内行为 | 首次配置 | 评级 |
|---|---|---|---|
| Basic（口令在 keystore） | 非交互取密 | 终端跑一次独立 `login`/`credentials set` | 适用 |
| SPNEGO | 票据自动协商，零提示 | 域登录即完成 | **最顺** |
| X.509 软件证书 | 非交互 | IT 签发/自动注册后无感 | 适用 |
| X.509 智能卡（PIN） | PIN 弹窗在 stdio 下可能无出口 | 按客户端栈专门验证 | 有条件 |
| OIDC（PKCE/设备码） | 仅按 `exp` 静默刷新 | 登录由独立 CLI 子命令完成，server 只读令牌 | 适用 |
| OIDC refresh 失效 | 不发起登录，返回类型化错误 | Agent 引导用户到终端重跑 `login` | 需错误协议 |

### 8.3 四个必做的工程处理

1. **认证错误工具化，而非挂起/提示**：返回结构化结果（如
   `{"ok": false, "error": "OIDC_RELOGIN", "hint": "在终端执行 <cli>.py login"}`），Agent 据此引导用户；退出码协议沿用 §2。
2. **长驻进程的刷新加锁**：stdio server 长期运行，access token 在内存按 `exp` 静默刷新；多个工具调用并发时刷新逻辑必须互斥，避免重复换令牌。
3. **Remote MCP（HTTP/SSE）区分两层认证**：

   ```text
   MCP Client ──① MCP 协议认证（OAuth 2.1 / MCP 授权规范）──▶ MCP Server
   MCP Server ──② SAP 认证（本手册各方式）─────────────────▶ SAP
   ```

   ① 决定"谁能调用 server"，② 决定"server 以什么身份调 SAP"；默认两者独立，② 走服务账号或按人映射。把①的令牌向下游传递（令牌交换/委派，见 [05 章](05-edge-patterns.md)）是额外设计，不是默认行为。
4. **启动环境差异交给能力探测**：MCP host 从 Windows Claude Desktop 拉起 WSL python、还是原生 WSL Claude Code，会命中不同 keystore 后端——正是 §6"按能力探测不看平台"要解决的，不要为 MCP 特判平台分支。

## 9. 实施顺序建议

1. 引入策略层，Basic 为唯一实现——行为与现状完全一致；
2. 加 KerberosStrategy（配合 SAP SPNEGO，见 [02 章](02-spnego.md)）；
3. 加 TokenManager 与 `login/logout`（配合网关验签，见 [04 章](04-oidc-oauth2.md)）；
4. 最后视需要开放 `auth.type=auto` 作为业务用户模板默认值。

每步独立验证：无网络单测全绿 + `doctor` 输出正确 + 负向用例返回预期退出码。
