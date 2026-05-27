# 商业授权机制设计

## 目标

- **著作权**：见 `app_identity.py` 页脚与 `/api/app_identity`（声明，不替代许可）。
- **商业使用**：须持有有效**许可证**并经在线校验；由独立 `license_server` 签发，业务进程 `single_app` 可选强制拦截。

## 架构

```
┌─────────────────┐     activate/verify      ┌──────────────────┐
│  single_app     │ ────────────────────────► │  license_server  │
│  (8080)         │     LICENSE_DEVICE_TOKEN   │  (8088)          │
│  LICENSE_ENFORCE│ ◄──────────────────────── │  SQLite/PG       │
└─────────────────┘                          └──────────────────┘
        │ admin 激活写入 system_config
        ▼
 license_device_token（与 .env LICENSE_DEVICE_TOKEN 二选一，env 优先）
```

## 角色

| 角色 | 能力 |
|------|------|
| 版权人 (Fan Yang) | 在许可服务 `/admin` 签发密钥、设到期日/设备数、吊销 |
| 部署管理员 | 在业务「管理员后台 → 商业授权」用密钥激活，查看状态 |
| 终端用户 | 受 `LICENSE_ENFORCE=1` 时无有效许可则无法使用业务 |

## 许可证生命周期

1. **签发**：许可服务管理页 → 新建（`INB-…` 密钥仅显示一次）→ 设置 `label`（客户/版本说明）、`max_activations`、`expires_in_days`。
2. **激活**：`POST /v1/activate` 提交 `license_key` + `device_fingerprint` → 返回 `device_token`。
3. **校验**：业务定时/每请求（可缓存）`POST /v1/verify` 提交 `device_token`。
4. **吊销**：许可或设备吊销后 verify 失败。

## 业务侧环境变量

| 变量 | 说明 |
|------|------|
| `LICENSE_SERVER_URL` | 许可服务根 URL |
| `LICENSE_DEVICE_TOKEN` | 激活得到的 token（优先于库内配置） |
| `LICENSE_ENFORCE` | `1` 时无有效许可拦截全站（除白名单） |
| `LICENSE_VERIFY_CACHE_SECONDS` | 校验缓存秒数；`0`=每次请求都联网校验，默认 300 |
| `LICENSE_GRACE_HOURS` | 仅当许可服务**连不上**时的宽限小时，默认 24 |
| `LICENSE_NO_GRACE_ERRORS` | 命中错误码**立即拒绝**、不走宽限，默认见下表 |
| `LICENSE_GRACE_ON_REVOKE` | `1` 时吊销/过期也走宽限（旧行为），默认关闭 |

## 吊销后的策略（业务 `.env`）

吊销在许可服务 **8088/admin** 操作；**主业务**通过下列变量决定「多久锁站、是否宽限」。

### 两层开关

| 层级 | 变量 | 作用 |
|------|------|------|
| 是否拦站 | `LICENSE_ENFORCE` | 未设：吊销后业务仍可用，仅状态变红；`1`：按下面规则拦截 |
| 吊销多快生效 | `LICENSE_VERIFY_CACHE_SECONDS` | 吊销前若缓存了「通过」，在此秒数内仍可能当有效；`0` 最快感知吊销 |
| 吊销是否宽限 | `LICENSE_NO_GRACE_ERRORS` + `LICENSE_GRACE_ON_REVOKE` | 默认 `revoked` 等**立即失败**；仅网络故障才用 `LICENSE_GRACE_HOURS` |

### 推荐预设

**试用 / 不锁站（当前常见）**

```env
LICENSE_SERVER_URL=http://127.0.0.1:8088
# 不设 LICENSE_ENFORCE
```

**生产：吊销后尽快锁站（推荐）**

```env
LICENSE_ENFORCE=1
LICENSE_VERIFY_CACHE_SECONDS=60
LICENSE_GRACE_HOURS=0
# LICENSE_GRACE_ON_REVOKE 不设或 0（默认：吊销不走宽限）
```

**生产：许可服务偶发宕机可宽限，但吊销仍立即失效（默认逻辑）**

```env
LICENSE_ENFORCE=1
LICENSE_VERIFY_CACHE_SECONDS=300
LICENSE_GRACE_HOURS=24
```

**旧行为：吊销后仍可能宽限最多 24 小时（不推荐）**

```env
LICENSE_GRACE_ON_REVOKE=1
LICENSE_GRACE_HOURS=24
```

修改 `.env` 后**重启 single_app（8080）**；许可服务无需重启。

### 查看当前策略

- `GET /api/license_status` → 字段 `policy`（`verify_cache_seconds`、`grace_hours` 等）
- 管理后台 **商业授权** 刷新状态（管理员登录后）

### `LICENSE_NO_GRACE_ERRORS` 默认命中

`revoked` · `device_revoked` · `expired` · `invalid_token`

逗号分隔，可增减，例如只让吊销立即生效、过期仍宽限：

```env
LICENSE_NO_GRACE_ERRORS=revoked,device_revoked
```

## 方案 A：同机双进程（试用推荐）

主业务 `single_app` 与许可服务 `license_server` 在同一台机器（如 `10.9.20.90`）：

| 进程 | 端口 | 说明 |
|------|------|------|
| `single_app` | 8080 | 统计/入库等业务 |
| `license_server` | 8088 | 仅授权 API + `/admin` 签发 |

业务 `.env`（与许可服务共用根目录 `.env` 即可）：

```env
LICENSE_SERVER_URL=http://127.0.0.1:8088
LICENSE_ADMIN_KEY=...          # 许可服务 /admin 登录（你方保管）
# 勿先开 LICENSE_ENFORCE；激活后再考虑强制
```

启动顺序：

1. 窗口 1：`run_license_server.bat` 或 `python -m license_server.app`
2. 浏览器 `http://127.0.0.1:8088/admin` → 新建许可证，复制 `INB-…` 密钥
3. 窗口 2：照常启动主业务（8080）
4. `http://10.9.20.90:8080/admin` → **商业授权** → 粘贴密钥激活
5. 打开 `http://10.9.20.90:8080/api/license_status`，确认 `configured: true`、`ok: true`

防火墙：8088 仅需本机或内网访问，不必对公网开放。

## 上线步骤

1. 部署 `python -m license_server.app`，配置 `LICENSE_ADMIN_KEY`、`LICENSE_WEB_SECRET`。
2. 签发客户许可证，将密钥交给客户部署方。
3. 业务 `.env` 配置 `LICENSE_SERVER_URL`；在管理后台激活或写入 `LICENSE_DEVICE_TOKEN`。
4. `GET /api/license_status` → `ready_for_enforce: true`。
5. 设置 `LICENSE_ENFORCE=1` 并重启业务。

## API（业务）

- `GET /api/license_status` — 任意已登录统计用户可读（不暴露 token）
- `GET /api/admin/license/status` — 管理员详情
- `POST /api/admin/license/activate` — `{ "license_key": "INB-..." }`

## 错误码（verify/activate）

`invalid_license` · `revoked` · `expired` · `activation_limit` · `invalid_token` · `device_revoked`

## 扩展（未实现）

- 按 `label` 区分功能包（标准版/企业版）并在业务内做特性开关
- 许可证与 Neon 多租户绑定
