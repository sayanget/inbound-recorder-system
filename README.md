# Inbound Recorder System（入库记录系统）

基于 **Flask** 的仓库入库与分拣数据管理应用：录入车辆到港信息、按车型规则计算装载与件数、统计看板、历史查询与多类导出。默认单机使用 **SQLite**，生产可通过 **`DATABASE_URL`** 连接 **PostgreSQL**（如 Neon）。

**仓库**：<https://github.com/sayanget/inbound-recorder-system>

---

## 主要功能

| 模块 | 说明 |
|------|------|
| **入库录入** | 码头号、车型、车牌、装载量、时间段、备注；支持「不计入统计」装载量（有车牌时）；道口占用时长（非 Car/Van） |
| **批量 CSV 导入** | 页面选择「导入日期」，上传 CSV；支持模板下载；表头识别失败时按列序兜底（第 1～3 列：码头、车型、时间） |
| **车型** | 系统内：`16英尺`、`26英尺`、`53英尺`、`Car`、`Van`、`其他`。导入/接口中可写简写：`16`/`26`/`53`、`van`/`面包车`、`Car`/`car` 等，服务端会规范为正式名称 |
| **分拣 / 托盘 / 耗材等** | 分拣录入、统计页、历史、产能与排程相关页面与 API（见 `single_app.py` 路由） |
| **管理后台** | 用户与权限、系统配置、**商业授权激活**、外包/Gofo 等集成接口（按角色开放） |
| **飞书表格同步** | CNO 各小组每小时产能、窄带按线分时等写入飞书电子表格（可脚本或统计页手动同步） |
| **商业授权** | 独立 `license_server`（默认 **8088**）签发/吊销；主业务可选 `LICENSE_ENFORCE` 在线校验 |
| **实时刷新** | SSE（`/api/sse/updates`）推送统计更新；前端可选 BroadcastChannel |
| **离线录入** | 浏览器端离线队列，恢复在线后同步（见 `static/js/offlineManager.js`） |
| **导出** | 近期记录 Excel、历史/分拣等导出接口 |

---

## 技术栈

- **后端**：Python 3.x、Flask  
- **数据库**：SQLite（默认）或 PostgreSQL（`DATABASE_URL` / `POSTGRES_URL`）  
- **前端**：静态 HTML/CSS/JS、Chart.js；部分 React 仪表在 `static/react-dashboard/`  
- **其他**：openpyxl、pytz、schedule、requests、pandas（与财务同步模块联动）

---

## 环境要求

- Python **3.10+**（建议；与当前依赖一致即可）  
- 使用 PostgreSQL 时安装：`pip install -r requirements-prod.txt`（含 `psycopg2-binary`）

---

## 快速开始

```bash
git clone https://github.com/sayanget/inbound-recorder-system.git
cd inbound-recorder-system

python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

pip install -r requirements.txt
```

### 启动

```bash
python single_app.py
```

- 默认监听 **`0.0.0.0:8080`**（可用环境变量 **`HOST`**、**`PORT`** 修改）  
- 浏览器访问：`http://localhost:8080/`（局域网访问示例：`http://<本机IP>:8080/`）

### 常用环境变量

| 变量 | 说明 |
|------|------|
| `HOST` | 绑定地址，默认 `0.0.0.0` |
| `PORT` | 端口，默认 **8080** |
| `SECRET_KEY` | Flask 会话签名密钥；生产环境**必须**设置为固定随机串 |
| `DATABASE_URL` / `POSTGRES_URL` | 若设置则使用 PostgreSQL，否则使用本地 SQLite |
| `DATABASE_PATH` | 仅 SQLite：数据库文件路径（可选） |
| `INITIAL_ADMIN_PASSWORD` | 首次初始化时管理员 `admin` 的密码；未设置时会在启动日志中打印**一次性随机密码** |
| `LICENSE_SERVER_URL` | 许可服务根 URL，同机试用示例：`http://127.0.0.1:8088` |
| `LICENSE_DEVICE_TOKEN` | 激活后的 device_token（也可在管理后台写入 `system_config`） |
| `LICENSE_ENFORCE` | `1` 时无有效许可拦截业务（除登录、激活等白名单）；试用阶段可不设 |
| `LICENSE_VERIFY_CACHE_SECONDS` | 校验缓存秒数，默认 300；`0` 为每次请求都校验 |
| `LICENSE_GRACE_HOURS` | 许可服务**连不上**时的宽限小时，默认 24 |
| `LICENSE_NO_GRACE_ERRORS` | 命中即不走宽限，默认含 `revoked`、`expired` 等 |
| `LICENSE_GRACE_ON_REVOKE` | `1` 时吊销也走宽限（旧行为，一般不推荐） |

首次启动会初始化数据库与默认管理员账号（用户名一般为 **`admin`**，密码见上表或控制台日志）。**生产环境请务必修改密码并设置 `SECRET_KEY`。**

### 商业授权（方案 A：同机双进程）

1. **窗口 1** — 许可服务：`run_license_server.bat` 或 `python -m license_server.app`（默认 **8088**）  
2. **窗口 2** — 主业务：`python single_app.py`（默认 **8080**）  
3. `.env` 配置 `LICENSE_SERVER_URL=http://127.0.0.1:8088` 与 `LICENSE_ADMIN_KEY`（许可服务 `/admin` 登录）  
4. 在 **8088/admin** 签发 `INB-…` 密钥 → 用主系统 **admin** 登录 **8080/admin** → **商业授权** 激活  
5. 确认 `GET /api/license_status` 中 `ready_for_enforce: true` 后，再设 `LICENSE_ENFORCE=1`  

详细设计与吊销策略见 **`docs/commercial-license.md`**；许可服务说明见 **`license_server/README.md`**。复制环境变量模板见 **`.env.example`**。

---

## 批量导入 CSV（入库）

1. 在首页选择 **导入日期**（写入每条记录的日期部分）。  
2. 下载模板或自备 CSV：  
   - **表头**至少能识别：**码头号、车辆类型、第三列时间**（可写「时间」「录入时间」或 `entry_time` 等）。  
   - 编码建议 **UTF-8**；Excel 另存为「CSV UTF-8」或系统中文 CSV；服务端会尝试 GBK 等编码。  
3. **列顺序兜底**：若表头无法识别，会按 **第 1 列=码头、第 2 列=车型、第 3 列=时刻** 解析（首行可为标题行或数据行，自动判断）。  
4. **接口**：`GET /api/inbound_import_template`，`POST /api/inbound_import`（`multipart/form-data`：`file`、`import_date=YYYY-MM-DD`）。

---

## 数据库说明

- **开发**：默认在项目目录生成 `inbound.db`（或打包 exe 同目录）。  
- **生产**：设置 `DATABASE_URL`，使用 `database.py` 中的抽象层与占位符转换（`?` → `%s`）。  
- 详细备份说明见 **`README_DB_BACKUP.md`**。

---

## 项目结构（节选）

```
├── single_app.py          # 主应用：路由、业务与定时任务
├── license_client.py      # 业务侧许可校验/激活客户端
├── license_server/        # 独立许可服务（默认 8088）
├── feishu_auth.py         # 飞书表格 API
├── database.py            # SQLite / PostgreSQL 连接与 SQL 适配
├── docs/commercial-license.md
├── scripts/               # 飞书同步、GitHub 全量推送等
├── run_license_server.bat
├── requirements.txt       # 本地默认依赖
├── requirements-prod.txt  # 生产（含 psycopg2、gunicorn 等）
├── docker-compose.yml
├── static/
│   ├── index.html         # 入库首页（含批量导入）
│   ├── sorting.html, statistics.html, admin.html, ...
│   └── js/                # nav 版权页脚、offlineManager 等
├── DEPLOYMENT.md
└── DEPLOYMENT_FULL.md
```

更完整的部署说明见 **`DEPLOYMENT.md`**、**`DEPLOYMENT_FULL.md`**。邮件相关见 **`README_EMAIL.md`**。

---

## 开发与调试

- 直接运行 `single_app.py` 时默认 **Flask debug**（仅用于开发）。  
- 生产建议使用 **gunicorn** 等 WSGI 服务器，并关闭 debug、配置 HTTPS 与反向代理。  
- CORS：对 **`/api/*`** 提供了浏览器跨域常用头；同域部署一般不受影响。

---

## 安全说明

- 勿在公网暴露未改默认口令的服务。  
- 设置 **`SECRET_KEY`**、**`INITIAL_ADMIN_PASSWORD`**，并限制管理接口访问范围。  
- **`LICENSE_ADMIN_KEY`** 仅用于许可服务管理页，勿与主系统登录密码混用。  
- 本项目按**内部使用**场景维护；对外部署时请自行审计依赖与配置。

---

## 著作权与商业使用

- 应用版权与页脚声明见 **`app_identity.py`**、`GET /api/app_identity`。  
- **商业使用**须按上文配置有效许可证；著作权声明不替代商业许可。  
- 吊销与锁站策略通过 `.env` 中 `LICENSE_ENFORCE`、`LICENSE_VERIFY_CACHE_SECONDS`、`LICENSE_GRACE_*` 等配置，见 **`docs/commercial-license.md`**。

---

## 许可证与贡献

内部/团队使用为主；商业授权由 `license_server` 管理。若需开源许可证或贡献指南，请在仓库中补充 `LICENSE` 与 `CONTRIBUTING.md`。

---

## 更新摘要（近期）

- **商业授权**：`license_server` + 管理后台激活、`LICENSE_ENFORCE` 与吊销策略可配置。  
- **飞书同步**：CNO 小组每小时产能、窄带按线分时矩阵；统计页「同步到飞书」与后台脚本。  
- 全站版权页脚、入库 **CSV 批量导入**、**PostgreSQL** 可选部署。  
- 默认 HTTP 端口：主业务 **8080**，许可服务 **8088**（以环境变量为准）。

如有问题请联系系统管理员或提交 Issue。
