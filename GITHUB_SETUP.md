# GitHub 托管指南

本地Git仓库已初始化完成！现在需要在GitHub上创建远程仓库并推送代码。

## 步骤1：在GitHub上创建新仓库

1. 访问 https://github.com/new
2. 填写仓库信息：
   - **Repository name**: `inbound-recorder-system` （或您喜欢的名称）
   - **Description**: `入库记录管理系统 - Inbound Recorder System`
   - **Visibility**: 选择 `Private`（私有）或 `Public`（公开）
   - ⚠️ **不要**勾选 "Add a README file"
   - ⚠️ **不要**勾选 "Add .gitignore"
   - ⚠️ **不要**选择 "Choose a license"
3. 点击 "Create repository"

## 步骤2：连接远程仓库并推送代码

创建仓库后，GitHub会显示一个页面。复制您的仓库URL（类似 `https://github.com/YOUR_USERNAME/inbound-recorder-system.git`）

然后在项目目录下运行以下命令：

### 方式1：使用HTTPS（推荐）

```bash
# 添加远程仓库
git remote add origin https://github.com/YOUR_USERNAME/inbound-recorder-system.git

# 推送代码到GitHub
git push -u origin master
```

### 方式2：使用SSH

```bash
# 添加远程仓库
git remote add origin git@github.com:YOUR_USERNAME/inbound-recorder-system.git

# 推送代码到GitHub
git push -u origin master
```

## 步骤3：验证推送成功

访问您的GitHub仓库页面，应该能看到所有文件已成功上传。

## 快速命令（复制后修改YOUR_USERNAME）

```bash
# 请将 YOUR_USERNAME 替换为您的GitHub用户名
git remote add origin https://github.com/YOUR_USERNAME/inbound-recorder-system.git
git branch -M main
git push -u origin main
```

## 后续更新代码

当您修改代码后，使用以下命令推送更新：

```bash
# 查看修改的文件
git status

# 添加所有修改的文件
git add .

# 提交修改（请修改提交信息）
git commit -m "描述您的修改内容"

# 推送到GitHub
git push
```

## 常用Git命令

```bash
# 查看当前状态
git status

# 查看提交历史
git log --oneline

# 查看远程仓库信息
git remote -v

# 拉取最新代码
git pull

# 创建新分支
git checkout -b feature/new-feature

# 切换分支
git checkout main
```

## 注意事项

✅ **已排除的敏感文件**：
- `email_config.py` - 包含邮箱密码，已在 `.gitignore` 中排除
- `*.db` - 数据库文件，已排除
- 所有测试文件和备份文件

✅ **已包含的示例文件**：
- `email_config.example.py` - 邮件配置模板

⚠️ **重要提醒**：
1. 确保 `email_config.py` 不会被提交到GitHub
2. 如果选择公开仓库，请确保没有敏感信息
3. 定期备份数据库文件

## 需要帮助？

如果遇到问题：
1. 确保已安装Git：`git --version`
2. 确保已登录GitHub账户
3. 如果使用HTTPS，可能需要输入GitHub用户名和密码（或Personal Access Token）
4. 如果使用SSH，需要先配置SSH密钥

## 下一步

推送成功后，您可以：
- 在GitHub上查看代码
- 邀请协作者
- 设置GitHub Actions进行自动化部署
- 使用GitHub Issues跟踪问题
- 创建Wiki文档
