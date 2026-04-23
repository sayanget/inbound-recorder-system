# 流向分布工具 — 独立可执行版

把 `/route-distribution` 页面打包成一个双击即用的 Windows `.exe`，分发给调度组同事使用。

支持两种数据源，**在设置页随时切换**：

| 模式 | 数据源 | 适用场景 |
|---|---|---|
| **API** | 出库系统 `http://host:port/api/outbound/records` | 内网有出库后端服务器 |
| **Google Sheet** | `https://docs.google.com/spreadsheets/d/…` 的 CSV 导出 | 直接从日常调度表拉数据，**完全外部数据源** |

---

## 功能

- 双击 `.exe` 启动本地 mini 服务（随机端口 `18080+`），自动打开默认浏览器
- 页面功能与网页版 `/route-distribution` 完全一致
  - 按日期区间拉取出库记录
  - 调度组模板预览（40 列，班次+费用成对）
  - 按日期多选 → 复制到剪贴板（TSV，不含日期列），直接粘贴进 Excel
  - 导出 CSV（完整版，含日期列）
- **两种数据源一键切换**：API 或 Google Sheet，共用同一套前端页面
- **后端 IP 可随时切换**：如果后端机器走 DHCP，IP 变了不用让用户改文件
  - 启动时自动探测数据源可达性，不通就直接打开设置页
  - API 模式可以一键**局域网扫描**找到出库系统
  - 主页顶部的 `⚙ 数据源 [API/Sheet]: ...` 随时点一下就能进设置页，运行中切换无需重启

---

## 打包（开发者一次性操作）

### 🟢 推荐：便携模式（把 Python 虚拟环境一起打包）

**最大优点**：发给别人时**对方电脑什么都不用装**，没有网络也能打包。

**开发者这边一次性操作**（只做一遍）：

```bat
cd standalone\route-distribution
init_portable.bat          # 下载 Python 3.12 embeddable + 装依赖到 portable\
```

完成后 `portable\` 文件夹里就是一套完整 Python 3.12 + flask + requests +
pyinstaller + Pillow（约 90 MB）。这是一次性的，之后不用再跑。

**打包分发给别人**：

```bat
pack_distribution.bat      # 把整个目录（含 portable\）压缩成 zip（约 24 MB）
```

产物：`..\流向分布工具-便携版-<时间戳>.zip`

**接收方用法**：

1. 解压到任意目录（如 `D:\流向分布工具\`）
2. 双击 **`build.bat`** → 约 30 秒后出 `dist\流向分布工具.exe`
3. （可选）双击 `create_shortcut.bat` 在桌面创建带图标的快捷方式

> 接收方电脑**不需要装 Python、不需要联网、不需要管理员权限**。
> `build.bat` 会自动检测 `portable\python.exe` 并优先使用它。

---

### 🔵 自己有 Python 环境：直接 `build.bat`

如果电脑上已经装了 Python 3.9+ 且在 PATH 里，**不需要** `init_portable.bat`，
直接：

```bat
build.bat
```

`build.bat` 会自动 `pip install -r requirements.txt`。

---

### 🟡 真·零基础（系统安装方式）：`setup.bat`

没装 Python 又不想走便携方案？双击 `setup.bat`——它会：

| 步骤 | 做什么 | 是否联网 |
|---|---|---|
| 检测 Python | 没装就自动装 Python 3.12（优先 winget，失败则从 python.org 下载；**当前用户模式，不需要管理员**） | 是 |
| 测试 pypi | 通就用默认源，不通自动切清华镜像 | 是 |
| 调用 `build.bat` | pip 装依赖 → 生图标 → PyInstaller 打包 | 是 |
| 桌面快捷方式 | Y/N 询问，选 Y 自动创建 | 否 |

**首次跑 3~8 分钟**（主要是下 Python 安装包 30MB 和若干 pip 包）。

**区别**：`setup.bat` 会往系统上装东西，`init_portable.bat`+`pack_distribution.bat`
完全不动系统，只在本目录内建环境。

---

### 故障恢复

| 症状 | 处理 |
|---|---|
| setup.bat 下载 Python 失败 | 去 https://www.python.org/downloads/ 手动装，勾选 "Add to PATH"，重跑 setup.bat |
| "python 不是内部或外部命令"（刚装完） | 关掉当前 cmd 窗口，**重新双击** setup.bat（新窗口才能读到新 PATH） |
| pip 装依赖很慢/超时 | setup.bat 里已经判过 pypi 连通性；如仍慢，手工执行：`pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple` |
| winget 提示"源代理失败" | 忽略，会自动回退到直接下载 |
| 公司域控机器不给装东西 | 用 `python -m venv` 起虚拟环境 + `.venv\Scripts\activate` + `build.bat`，全在用户目录里，不需要系统权限 |

构建脚本会：

1. 从 `..\..\static\route-distribution.html` 拷贝最新页面
2. 如果没有 `icon.ico`，调用 `gen_icon.py` 用 Pillow 生成一个（仅构建时需要 Pillow；exe 运行时无此依赖）
3. 调 PyInstaller 打包成单一 `.exe`（把 HTML + 图标嵌入 exe 内部）
4. 把 `icon.ico` 也拷贝一份到 `dist\`，方便快捷方式直接引用
5. 输出 `dist\流向分布工具.exe`

首次构建需要 30~60 秒；产物约 15~25 MB。

> 想换图标：用任何做图工具导出一个 `.ico`（建议含 16/32/48/256 多分辨率），
> 命名为 `icon.ico` 放在此目录，再跑 `build.bat` 即可。

### 3. 生成桌面快捷方式（可选，自带图标）

```bat
create_shortcut.bat
```

等价于在当前用户桌面生成一个 `流向分布工具.lnk`，图标来自 `dist\icon.ico`（若
不存在则回退到 exe 自带的嵌入图标）。

可选参数：

```bat
create_shortcut.bat                    REM 当前用户桌面（默认）
create_shortcut.bat /public            REM 公共桌面（所有用户可见，需管理员）
create_shortcut.bat "D:\foo\a.exe"     REM 指定 exe 路径（非默认位置时）
```

---

## 分发与使用（给终端用户）

**最少只需一个文件**：`流向分布工具.exe`（图标已内嵌）

1. 双击运行
2. 黑色命令行窗口会显示状态，浏览器自动打开页面
3. 关闭命令行窗口即停止服务
4. 首次运行会在 exe 同目录生成 `config.txt`，里面是后端地址；如需指向别的服务器，编辑这个文件即可

### 想在桌面放一个带图标的快捷方式？

把 `dist\` 整个文件夹（含 `流向分布工具.exe` 和 `icon.ico`）拷到目标机器任意位置，
然后把同目录的 `create_shortcut.bat`（从本仓库复制过去即可）双击一下，桌面就会
多出一个 `流向分布工具` 图标。

也可以手工：右键桌面 → 新建 → 快捷方式 → 选中 `流向分布工具.exe` → 完成；
再右键该快捷方式 → 属性 → 更改图标 → 浏览到 `icon.ico`。

### 改后端地址的四种方式

| 方式 | 操作 | 什么时候用 |
|---|---|---|
| ★ 设置页 UI | 浏览器打开 http://127.0.0.1:1808x/setup | **IP 变了，最省事**，点"开始扫描"自动找 |
| 命令行参数 | `流向分布工具.exe --backend http://host:port` | 给个别用户一次性指定 |
| 环境变量 | `set ROUTE_DIST_BACKEND=http://host:port` | 在登录脚本/IT 批量下发里设 |
| 配置文件 | 编辑 exe 同目录的 `config.txt` | 静态环境，想显式写死 |

> **设置页保存后会自动写入 `config.txt`**，下次启动直接沿用。

默认值（写死在代码里）：`http://192.168.0.250:8080`

### 应对 IP 变动的最佳实践

1. **首选：用主机名**。如果后端机有固定主机名（如 `server01`），让用户把 URL 填成
   `http://server01:8080`。Windows LAN 内多半能 NetBIOS / mDNS 解析，IP 就算变了
   也不影响。
2. **退而求其次：局域网扫描**。真的改用 IP 的话，让用户点设置页里的
   "开始扫描"，工具会扫本机 /24 子网探测 8080/80/5000/8000，自动定位出库系统。
3. **IT 批量下发**：如果你们走域控，用登录脚本设个 `ROUTE_DIST_BACKEND` 环境变量
   即可（优先级高于 config.txt）。

### 常用命令行参数

```bat
流向分布工具.exe                                 REM 默认启动
流向分布工具.exe --backend http://10.0.0.5      REM 指定 API 后端
流向分布工具.exe --backend https://docs.google.com/spreadsheets/d/<ID>/edit   REM Sheet 模式
流向分布工具.exe --port 18088                   REM 指定端口
流向分布工具.exe --no-browser                   REM 不自动开浏览器
流向分布工具.exe --skip-probe                   REM 跳过启动时的后端探测
```

---

## 使用 Google Sheet 作为数据源

### 前置条件

1. Sheet **必须公开**：在 Google Sheets 里点「共享」→ 设为「拥有链接的任何人 → 查看者」。
   工具只用 CSV 导出接口（`…/export?format=csv&gid=0`），无需 Google 账号登录，也不走 API Key。
2. Sheet 结构要有这 4 个必需表头（大小写不敏感，工具会在前 20 行里扫描自动定位）：

    | 列含义 | 表头（任一即可） |
    |---|---|
    | 日期 | `DATE` / `日期` |
    | 流向 | `TO` / `流向` / `目的地` |
    | 费用 | `$` / `Cost` / `Price` / `费用` / `价格` / `金额` |
    | 发车运单号 | `MT#` / `MT` / `发车运单号` / `运单号` |
    | 提货单号 *(可选)* | `Pickup #` / `Pickup#` / `提货单号` / `提货号` |

### 计数规则

- 一行 = 一个班次（`vehicle_count = 1`）。
- **一行只要满足下面任何一个条件，就算已发车**：
  - `MT#` 列以 `MT` 开头（不区分大小写）——旧格式，如 `MT2025080200238`
  - `Pickup #` 列有任何字母或数字 ——新格式，如 `LASCNO042618` / `EWRCNO041501`
    （2026 年 3 月起运营停写 MT#、改用 Pickup#，工具自动兼容）
- TO 列为空的行一律跳过（没写目的地 = 没录入/planning）。
- `费用 ($)` 列自动剥离 `$ ￥ ,` 等符号，非数字视为 0。
- **流向不合并**：`DFW-ATL`、`LAV (往返）drop trailer` 等保留原样；
  仅在「调度组模板预览」那一张表里做了针对模板的局部归一化：
  - `DFW DROP` → `DFW`、`LAV (往返）drop trailer` → `LAV`
  - `ATL.G-ATL` / `ATL.H-ATL` → `ATL`
  页面顶部的「前缀合并」下拉保持 `full` 即不合并。

### 年份推断（针对 MM-DD 格式日期）

很多 Sheet 的 DATE 列只写 `06-12` / `10/19`。工具按这个优先级推断年份：

1. **单元格里已写完整日期**（`2025-10-19` / `10/19/2025` 等）→ 直接用，且作为该行后续的锚点。
2. **从 `MT#` 反推**：`MT2025102000134` 前 8 位 = 发车日期 `20251020`，因此这一行的年份就是 2025。
   MT# 是公司 TMS 分配的，**比 Sheet 的 MM-DD 日期更权威**，工具优先用它。
3. **链式滚动**：上面都拿不到时，从 `year=` 配置或查询区间起始年开始，
   一旦下一行 MM-DD 比上一行倒退超过 180 天就自动 `+1` 年。

> 注：`Pickup #`（如 `LASCNO042618`）里只有月日和序号，**不带年份**，
> 所以完全依赖上面的链式滚动；如果查询区间的起始年填错，结果就会整体偏一年。
> 设置页的「MM-DD 日期默认年份」输入框可以强制锁死。

> 查区间跨越数据首行前的时段时（比如 Sheet 从 2025-07 开始记录、你查 2025-05 的记录），
> 会返回 0 行 —— 因为那段时间 Sheet 里根本没数据。这是预期行为。

### 配置方式

**方案 A：设置页（最常用）**

1. 启动工具 → 浏览器自动打开 `/setup`（或点主页顶部 `⚙ 数据源`）
2. 把 Sheet URL 整个粘到输入框（`/edit#gid=0` 或 `/edit?gid=0` 都行，会自动转成 CSV 导出地址）
3. 勾选「Google Sheet (CSV)」；必要时填 **MM-DD 日期默认年份**（可空）
4. 「测试连接」成功后「保存并启用」，自动跳回主页

**方案 B：`config.txt`**

```text
https://docs.google.com/spreadsheets/d/1sEjOb…/edit#gid=0
year=2025
```

`year` 可省略；加了之后对于 MM-DD-only 的行，从这个年开始做链式滚动推断。

**方案 C：环境变量 / 命令行**

```bat
set ROUTE_DIST_BACKEND=https://docs.google.com/spreadsheets/d/<ID>/edit
流向分布工具.exe
```

或：

```bat
流向分布工具.exe --backend "https://docs.google.com/spreadsheets/d/<ID>/edit#gid=0"
```

### 性能与缓存

- CSV 导出每次约 1~4 MB；第一次打开某个区间有 1~2 秒的网络抓取；
- 60 秒内相同 `(url, start_date, end_date, year)` 组合会复用缓存；
- `POST /api/refresh` 可强制清缓存（从设置页保存数据源时自动清一次）。

---

## 疑难排查

### 🔴 "无法连接到后端服务" / 502 (API 模式)

- 后端服务器是否在运行（浏览器打开 `http://192.168.0.250:8080/` 看）
- 本机是否在同一内网
- Windows 防火墙是否拦截

### 🔴 "拉取 Google Sheet 失败" / "疑似未公开：返回的是登录页" (Sheet 模式)

- 在 Google Sheets 里点「共享」→「常规访问」→「拥有链接的任何人」→ 权限选「查看者」
- 测试：把 URL 替换成 `…/export?format=csv&gid=0` 直接浏览器访问，若能下载 CSV 文件就是已公开
- 确认 URL 里的 `gid=` 是正确的那个工作表（左下角 tab 切换时地址栏的 `gid` 会变）

### 🔴 Sheet 模式数据数量不对

- 首先检查 Sheet 里所有 `MT#` 列以 `MT` 开头的行数是否与预期一致（其他一律不计）
- 查询区间跨年时，单元格若仅 MM-DD，年份会按 MT# 推断；若某行没 MT# 又没完整年份，
  可能被链式滚动放到相邻年。在 `config.txt` 设 `year=<Sheet 起始年>` 可消除歧义
- 点主页顶部 `⚙ 数据源` → 重新「保存并启用」会清缓存并重新抓取

### 🔴 Windows Defender / 杀软误报

PyInstaller 打包的 `.exe` 有时会被误报。对策：
- 加入白名单
- 用 `--onedir` 模式（改 `build.bat` 里的 `--onefile` 为 `--onedir`）生成一个文件夹，降低误报

### 🔴 双击后黑窗口一闪而过

多半是 Python 异常且用户没看到。用命令行启动：

```bat
cd 流向分布工具.exe 所在目录
流向分布工具.exe
```

就能看到完整错误信息。

### 🔴 端口被占用

工具会自动在 `18080-18199` 范围内找空闲端口；若想指定：
```bat
流向分布工具.exe --port 18088
```

---

## 文件结构

```
standalone/route-distribution/
├── init_portable.bat            # ★ 下载 Python embeddable + 装依赖到 portable\
├── pack_distribution.bat        # ★ 把目录打成便携 zip 分发
├── pack_distribution.ps1        #     （配套 ps 脚本，需 UTF-8 BOM）
├── build.bat                    # 打包脚本（自动优先用 portable\python.exe）
├── setup.bat                    # 系统安装模式（不推荐，走便携更省事）
├── create_shortcut.bat          # 在桌面生成带图标的快捷方式
├── app.py                       # 主脚本（Flask + 代理 + 设置页）
├── gen_icon.py                  # 用 Pillow 生成 icon.ico（仅构建时用）
├── icon.ico                     # 图标（多分辨率，16/24/32/48/64/128/256）
├── requirements.txt             # Python 依赖清单
├── README.md                    # 本文档
├── route-distribution.html      # 页面（由 build.bat 自动从 static/ 同步）
├── portable/                    # ★ init_portable.bat 生成，自带 Python 3.12 + 所有包
│   ├── python.exe
│   ├── python312._pth           # 已启用 import site
│   ├── Lib/site-packages/       # flask / requests / pyinstaller / Pillow …
│   ├── Scripts/                 # pip.exe, pyinstaller.exe …
│   └── .ready                   # 标志文件；build.bat 识别它跳过重复 pip
├── build/                       # PyInstaller 中间产物（临时）
└── dist/
    ├── 流向分布工具.exe          # ★ 最终产物（已内嵌图标）
    └── icon.ico                  # 供快捷方式引用的图标副本
```

---

## 升级页面内容

每次 `static/route-distribution.html` 改动后，重新跑一次 `build.bat`
即可生成带最新页面的 `.exe`，**终端用户只需替换 `.exe` 文件**（config.txt 保留）。
