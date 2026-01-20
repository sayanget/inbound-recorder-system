# Zeabur 快速部署指南

## 前提条件

✅ 数据库已部署到 Neon PostgreSQL  
✅ 代码已更新支持双数据库模式

> [!NOTE]
> **依赖文件说明**:
> - `requirements.txt` - 本地开发依赖 (不含 PostgreSQL)
> - `requirements-prod.txt` - 生产部署依赖 (含 PostgreSQL)
> 
> Zeabur 部署会自动使用 `requirements-prod.txt`

## 部署步骤

### 1. 推送代码到 GitHub

```bash
# 初始化 Git (如果还没有)
git init

# 添加所有文件
git add .

# 提交
git commit -m "Add Zeabur deployment support"

# 添加远程仓库并推送
git remote add origin <your-github-repo-url>
git push -u origin main
```

### 2. 在 Zeabur 创建项目

1. 访问 [Zeabur](https://zeabur.com)
2. 点击 "New Project"
3. 选择 "Deploy from GitHub"
4. 选择你的仓库: `sayanget/inbound-recorder-system`
5. Zeabur 会自动检测 Dockerfile 并开始构建

### 3. 配置环境变量

在 Zeabur 项目设置中添加以下环境变量:

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `DATABASE_URL` | `postgresql://neondb_owner:npg_G1pxCJTigOK2@ep-green-meadow-afwsztqi-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require` | Neon 数据库连接串 |
| `SECRET_KEY` | `<生成一个随机密钥>` | Flask session 密钥 |
| `ENVIRONMENT` | `production` | 运行环境 |

**生成 SECRET_KEY**:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. 部署并验证

1. Zeabur 会自动构建和部署
2. 部署完成后,访问 Zeabur 提供的 URL
3. 测试登录功能 (admin/admin123)
4. 验证数据读写正常

## 本地测试 (可选)

### 测试 SQLite (默认)

```bash
# 直接运行,无需配置
python single_app.py
```

### 测试 PostgreSQL

```bash
# 设置环境变量
set DATABASE_URL=postgresql://neondb_owner:npg_G1pxCJTigOK2@ep-green-meadow-afwsztqi-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require

# 运行应用
python single_app.py
```

## 常见问题

### 1. 部署失败: "Module not found"

**解决**: 确保 `requirements.txt` 包含所有依赖:
```bash
pip freeze > requirements.txt
```

### 2. 数据库连接失败

**解决**: 
- 检查 `DATABASE_URL` 环境变量是否正确
- 确认 Neon 数据库正在运行
- 检查网络连接

### 3. Session 丢失

**解决**: 确保设置了 `SECRET_KEY` 环境变量

## 回滚

如果部署出现问题:

1. 在 Zeabur 控制台点击 "Rollback"
2. 选择之前的版本
3. 或者在 GitHub 回退代码后重新部署

## 监控

- **日志**: 在 Zeabur 控制台查看实时日志
- **性能**: 监控响应时间和错误率
- **数据库**: 在 Neon 控制台查看数据库状态

## 下一步优化

- [ ] 配置自定义域名
- [ ] 启用 HTTPS
- [ ] 配置 CDN 加速静态文件
- [ ] 设置自动备份
- [ ] 配置监控告警
