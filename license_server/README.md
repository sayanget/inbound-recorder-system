# 许可证服务（单进程 + SQLite / PostgreSQL）

## 安装

```bash
cd license_server
pip install -r requirements.txt
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `LICENSE_DATABASE_URL` | 默认 `sqlite:///license_server.db`（相对当前工作目录）。PostgreSQL 示例：`postgresql+psycopg2://user:pass@host:5432/dbname` |
| `LICENSE_ADMIN_KEY` | 管理接口必填请求头 `X-Admin-Key`，用于创建/吊销许可证 |
| `LICENSE_KEY_PEPPER` | 可选，与主项目一致时才能校验同一批密钥 |
| `LICENSE_BIND_HOST` / `LICENSE_BIND_PORT` | 默认 `0.0.0.0:8088`（主业务常用 8080，许可服务默认错开） |
| `LICENSE_WEB_SECRET` | **强烈建议**固定随机串；不设则用 `LICENSE_ADMIN_KEY` 派生（勿频繁改 ADMIN_KEY，否则全员登出） |
| `LICENSE_SESSION_DAYS` | 管理登录 Cookie 有效期（天），默认 **90**，最长 365 |
| `LICENSE_SESSION_SECURE` | 设为 `1` 时 Cookie 仅 HTTPS（本地 http://127.0.0.1 勿开） |

## 启动

**许可服务与主应用 `single_app` 是两个进程**：主业务占 **8080** 时，许可服务默认监听 **8088**，需**单独启动**。

在项目根目录 `inbound_python_source` 下：

```bash
set LICENSE_ADMIN_KEY=你的长随机串
python -m license_server.app
```

Windows 可双击 **`run_license_server.bat`**。项目根目录的 **`.env`** 会自动加载（含 `LICENSE_ADMIN_KEY`、`LICENSE_BIND_PORT` 等）。

若浏览器仍打不开 8088：

1. 看终端是否报错退出（缺依赖可 `pip install -r license_server/requirements.txt`）。
2. PowerShell：`netstat -an | findstr 8088` 是否出现 `LISTENING`。
3. 防火墙是否放行本机 `python.exe` 或端口 8088。
4. 确认访问 `http://127.0.0.1:8088/health` 应返回 `{"ok":true}`。

浏览器打开 **`http://127.0.0.1:8088/admin`**（端口以 `LICENSE_BIND_PORT` 为准），使用 `LICENSE_ADMIN_KEY` 登录后可：

- 新建许可证（密钥仅成功页显示一次）
- 查看列表、吊销

生产环境请设置 **`LICENSE_WEB_SECRET`**（Flask 会话签名），并仅在内网或 HTTPS 后暴露管理页。

**易掉线**：请始终用同一地址访问（**`127.0.0.1` 与 `localhost` 的 Cookie 不互通**）。已启用滑动续期与最长 90 天会话（见 `LICENSE_SESSION_DAYS`）。

## API

- `GET /health`
- `POST /v1/activate` — `{"license_key","device_fingerprint"}`
- `POST /v1/verify` — `{"device_token"}`
- `GET /v1/admin/licenses` — 头 `X-Admin-Key`，列出许可证（无明文密钥）
- `POST /v1/admin/licenses` — 头 `X-Admin-Key`，体 `{"label","max_activations","expires_in_days"}`
- `POST /v1/admin/licenses/<id>/revoke` — 吊销许可证

## 主应用集成

见项目根目录 `license_client.py`，在 `single_app` 启动或定时任务中调用 `verify_license()`。
