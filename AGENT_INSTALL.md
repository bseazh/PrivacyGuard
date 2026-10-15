# Agent 自动安装说明

本文件面向能执行终端命令的编码 Agent。目标是安装、验证并启动本仓库，不要上传用户文档或模型缓存。

Agent 安全入口优先使用 Python 3.11：

```bash
chmod +x scripts/*.sh
./scripts/bootstrap_privacyguard.sh
./scripts/start_privacyguard.sh
./scripts/test_privacyguard.sh
```

安装完成后，根据 [config/codex-mcp.toml](config/codex-mcp.toml) 配置宿主，并安装 [skills/privacyguard](skills/privacyguard)。修改用户全局配置前必须取得用户许可。不得先读取待保护文件来“确认内容”；只把路径交给 `privacy_scan_file`。

## 1. 检测平台

```bash
uname -s
uname -m
```

- `Darwin + arm64`：执行 macOS MLX 完整模式。
- `Darwin + x86_64`：执行 macOS 脚本，按规则模式启动。
- Windows：执行 PowerShell 规则模式。

## 2. 安装

macOS：

```bash
chmod +x scripts/*.sh
./scripts/bootstrap_macos.sh
```

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_windows.ps1
```

如果缺少 Homebrew、winget 或系统管理员权限，停止并向用户报告具体缺失项，不要关闭安全策略或 TLS 校验。

## 3. 验证

macOS：

```bash
source .venv-mlx/bin/activate
python -m unittest discover -s tests
npm --prefix app test
npm --prefix app run build
```

Windows：

```powershell
$env:PRIVACYGUARD_NER_BACKEND = "rules"
.\.venv\Scripts\python.exe -m unittest discover -s tests
npm --prefix app test
npm --prefix app run build
```

再启动后端并检查 `http://127.0.0.1:8766/health` 返回 `ok: true`。不要只看到前端页面就判定安装成功。

## 4. 启动

macOS：`./scripts/start_macos.sh`

Windows：`powershell -ExecutionPolicy Bypass -File scripts\start_windows.ps1`

## 5. 验收标准

- TXT/DOCX/有文本层 PDF 可以上传并返回候选实体。
- 前端可完成人工确认、预览和文本导出。
- 有文本层 PDF 可导出假名化 PDF，且原敏感文字无法再被搜索。
- 扫描 PDF 必须明确提示无法精确定位，不得报告脱敏成功。
