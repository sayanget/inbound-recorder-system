# Antigravity 迁移指南

本指南帮助你将 Antigravity 及其所有配置从一台机器迁移到另一台机器。

## 📦 备份内容

### 自动备份包含：
- ✅ **全局 Skills** (38个) - `c:\Users\zhang\.agent\skills\`
- ✅ **Workflows** - `.agent\workflows\`
- ✅ **对话历史** - `c:\Users\zhang\.gemini\antigravity\brain\`
- ✅ **配置文件** - `c:\Users\zhang\.gemini\`

### 不包含：
- ❌ **项目文件** - 项目代码和项目级 skills 不会被备份
- ❌ **项目 Skills** - 需要在新机器上重新安装或手动复制

---

## 🚀 快速开始

### 在旧机器上备份

```powershell
# 完整备份（包含历史记录）
.\backup_antigravity.ps1

# 仅备份 skills 和配置（跳过历史记录，节省空间）
.\backup_antigravity.ps1 -SkipHistory

# 自定义备份路径
.\backup_antigravity.ps1 -BackupPath "E:\my_backup"
```

**输出**: `antigravity_backup_YYYYMMDD_HHMMSS.zip`

**注意**: 
- ✅ 仅备份全局 skills 和配置
- ❌ **不包含项目文件**（项目 skills 需要在新机器上重新安装）

---

### 在新机器上恢复

```powershell
# 自动恢复到系统路径
.\restore_antigravity.ps1 -BackupZipPath "D:\antigravity_backup_20260215_182803.zip"

# 跳过历史记录恢复
.\restore_antigravity.ps1 -BackupZipPath "backup.zip" -SkipHistory
```

**自动解压到**:
- `c:\Users\<当前用户>\.agent\` - 全局 skills
- `c:\Users\<当前用户>\.gemini\` - 配置和历史

---

## 📋 详细步骤

### 步骤 1: 在旧机器上执行备份

1. 打开 PowerShell（管理员权限）
2. 导航到脚本目录：
   ```powershell
   cd d:\project\inbound_python_source
   ```
3. 运行备份脚本：
   ```powershell
   .\backup_antigravity.ps1
   ```
4. 等待备份完成，记录输出的压缩包路径

### 步骤 2: 传输备份文件

将生成的 `.zip` 文件复制到新机器，可以使用：
- USB 驱动器
- 网络共享
- 云存储（OneDrive, Google Drive）
- 邮件（如果文件不大）

### 步骤 3: 在新机器上恢复

1. 将 `restore_antigravity.ps1` 复制到新机器
2. 打开 PowerShell（管理员权限）
3. 运行恢复脚本：
   ```powershell
   .\restore_antigravity.ps1 -BackupZipPath "完整路径\backup.zip"
   ```
4. 按提示输入项目路径（如果需要）
5. 等待恢复完成

### 步骤 4: 验证

```powershell
# 检查全局 skills
Get-ChildItem "c:\Users\$env:USERNAME\.agent\skills" -Directory | Select-Object Name

# 检查配置
Test-Path "c:\Users\$env:USERNAME\.gemini"

# 检查项目 skills（如果适用）
Get-ChildItem "你的项目路径\.agent\skills" -Directory | Select-Object Name
```

---

## ⚙️ 高级选项

### 选择性备份

```powershell
# 仅备份 skills，不备份历史（更小的文件）
.\backup_antigravity.ps1 -SkipHistory

# 自定义备份位置
.\backup_antigravity.ps1 -BackupPath "E:\backups"
```

### 选择性恢复

```powershell
# 仅恢复全局 skills
.\restore_antigravity.ps1 -BackupZipPath "backup.zip" -SkipProjectSkills -SkipHistory

# 恢复到不同的项目路径
.\restore_antigravity.ps1 -BackupZipPath "backup.zip" -ProjectPath "D:\new_location\project"
```

---

## 🔧 手动迁移（备选方案）

如果自动脚本不适用，可以手动复制：

### 必需文件：
```
旧机器                                    新机器
c:\Users\zhang\.agent\          →    c:\Users\<新用户名>\.agent\
c:\Users\zhang\.gemini\         →    c:\Users\<新用户名>\.gemini\
```

### 可选文件（项目级）：
```
d:\project\..\.agent\           →    <新项目路径>\.agent\
```

---

## ⚠️ 注意事项

### 1. 用户名差异
- 旧机器: `c:\Users\zhang\`
- 新机器: `c:\Users\<新用户名>\`
- 脚本会自动处理，无需手动修改

### 2. 项目路径变化
- 如果项目位置改变，恢复时指定新路径：
  ```powershell
  -ProjectPath "新路径"
  ```

### 3. 现有配置保护
- 恢复脚本会自动备份新机器上的现有配置
- 备份位置: `原路径_backup_时间戳`

### 4. 磁盘空间
- 完整备份（含历史）可能较大（几百 MB）
- 使用 `-SkipHistory` 可显著减小文件大小

### 5. 权限要求
- 需要管理员权限运行脚本
- 确保对目标目录有写入权限

---

## 🐛 故障排除

### 问题: "无法找到备份文件"
**解决**: 检查路径是否正确，使用绝对路径

### 问题: "权限被拒绝"
**解决**: 以管理员身份运行 PowerShell

### 问题: "脚本执行被禁止"
**解决**: 
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 问题: "项目 skills 未恢复"
**解决**: 确保指定了正确的 `-ProjectPath` 参数

---

## 📊 备份文件结构

```
antigravity_backup_YYYYMMDD_HHMMSS/
├── .agent/
│   ├── skills/              # 38 个全局 skills
│   └── workflows/           # 工作流文件
├── project_.agent/
│   └── skills/              # 8 个项目 skills
├── .gemini/
│   └── antigravity/
│       └── brain/           # 对话历史
└── BACKUP_MANIFEST.txt      # 备份清单
```

---

## 🎯 最佳实践

1. **定期备份**: 建议每月备份一次
2. **版本控制**: 保留最近 3 个备份版本
3. **云同步**: 考虑将 skills 目录同步到云盘
4. **测试恢复**: 在虚拟机上测试恢复流程
5. **文档更新**: 记录自定义配置和依赖

---

## 📞 需要帮助？

如果遇到问题：
1. 检查 `BACKUP_MANIFEST.txt` 确认备份内容
2. 查看脚本输出的错误信息
3. 验证文件路径和权限
4. 尝试手动迁移方案

---

**生成时间**: 2026-02-15  
**版本**: 1.0
