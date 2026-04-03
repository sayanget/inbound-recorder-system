# Antigravity 迁移工具 - 快速参考

## ✅ 已完成更新

### 1. 备份脚本优化
- **文件**: `backup_antigravity.ps1`
- **变更**: 
  - ❌ 不再备份项目文件和项目 skills
  - ✅ 仅备份全局 skills (38个) 和配置
  - ✅ 支持 `-SkipHistory` 跳过对话历史（节省空间）

### 2. 恢复脚本自动化
- **文件**: `restore_antigravity.ps1`
- **变更**:
  - ✅ 自动解压到系统路径 `c:\Users\<当前用户>\`
  - ✅ 无需手动指定路径
  - ✅ 自动备份现有配置（如果存在）

### 3. 测试结果
- ✅ 备份成功: `antigravity_backup_20260215_214425.zip`
- ✅ 大小: **265 MB** (跳过历史记录)
- ✅ 包含: 38个全局 skills + 配置文件

---

## 🚀 使用方法

### 在当前机器备份

```powershell
# 仅备份 skills 和配置（推荐，文件小）
.\backup_antigravity.ps1 -SkipHistory

# 完整备份（包含所有对话历史，文件大）
.\backup_antigravity.ps1
```

### 在新机器恢复

```powershell
# 自动恢复到系统路径
.\restore_antigravity.ps1 -BackupZipPath "D:\antigravity_backup_20260215_214425.zip"
```

**自动恢复位置**:
- `c:\Users\<新用户名>\.agent\` - 全局 skills
- `c:\Users\<新用户名>\.gemini\` - 配置和历史

---

## 📋 备份内容对比

| 项目 | 包含 | 说明 |
|------|------|------|
| 全局 Skills (38个) | ✅ | frontend-design, shadcn-ui, mcp-builder 等 |
| Workflows | ✅ | 工作流配置 |
| 配置文件 | ✅ | Antigravity 设置 |
| 对话历史 | ⚠️ | 默认包含，可用 `-SkipHistory` 跳过 |
| 项目文件 | ❌ | 不备份，需单独处理 |
| 项目 Skills | ❌ | 不备份，需在新机器重新安装 |

---

## 💡 迁移建议

### 方案 1: 仅迁移 Antigravity（推荐）
1. 运行 `.\backup_antigravity.ps1 -SkipHistory`
2. 复制 zip 文件到新机器
3. 运行 `.\restore_antigravity.ps1 -BackupZipPath "..."`
4. 项目 skills 在新机器上重新安装

**优点**: 文件小（~265 MB），传输快

### 方案 2: 完整迁移（包含历史）
1. 运行 `.\backup_antigravity.ps1`
2. 复制 zip 文件到新机器（可能 8+ GB）
3. 运行 `.\restore_antigravity.ps1 -BackupZipPath "..."`

**优点**: 保留所有对话历史

### 项目 Skills 迁移
项目 skills (baoyu 系列) 需要单独处理：
```powershell
# 手动复制项目 .agent 目录
Copy-Item "d:\project\inbound_python_source\.agent" "新机器项目路径\.agent" -Recurse
```

---

## 📁 文件清单

- ✅ `backup_antigravity.ps1` - 备份脚本
- ✅ `restore_antigravity.ps1` - 恢复脚本
- ✅ `ANTIGRAVITY_MIGRATION_GUIDE.md` - 详细指南
- ✅ `MIGRATION_QUICK_REF.md` - 本文档

---

**生成时间**: 2026-02-15 21:44
