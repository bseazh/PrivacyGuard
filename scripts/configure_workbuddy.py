"""Generate or safely merge WorkBuddy stdio MCP configuration. Never print credentials."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


def server_config(root: Path, home: Path) -> dict:
    return {
        "command": str(root / ".venv/bin/privacyguard-mcp"), "args": [],
        "env": {
            "PRIVACYGUARD_ALLOWED_ROOTS": os.pathsep.join(str(home / d) for d in ("Documents", "Desktop", "Downloads")),
            "PRIVACYGUARD_DATA_DIR": str(home / ".privacyguard"),
            "PRIVACYGUARD_REFERENCE_TTL": "900",
            "PRIVACYGUARD_PRESIDIO_URL": "http://127.0.0.1:5002",
            "PRIVACYGUARD_REDACTION_BASE_URL": "http://127.0.0.1:8000",
            "PRIVACYGUARD_REDACTION_OCR_URL": "http://127.0.0.1:8082",
            "PRIVACYGUARD_LLM_MODEL": f"openai/{root}/models/qwen3/Qwen3-1.7B-bf16",
            "PRIVACYGUARD_LLM_BASE_URL": "http://127.0.0.1:8011/v1",
            "PRIVACYGUARD_LLM_API_KEY": "local-only",
        },
    }


def write_private(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".privacyguard.tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        temporary.chmod(0o600)
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Back up and merge into WorkBuddy settings; close WorkBuddy first")
    parser.add_argument("--config", type=Path, default=Path.home() / ".workbuddy/mcp.json")
    parser.add_argument("--output", type=Path, default=root / "local-config/workbuddy-mcp.json")
    args = parser.parse_args()
    entry = server_config(root, Path.home())
    output = args.output.expanduser().resolve()
    write_private(output, {"mcpServers": {"privacyguard": entry}})
    print(f"MCP 配置已生成：{output}")
    if not args.apply:
        print("未修改 WorkBuddy。手动合并 mcpServers.privacyguard，或关闭应用后用 --apply 安全合并。")
        return
    if not Path(entry["command"]).is_file():
        parser.error("请先安装 PrivacyGuard Python 环境")
    target = args.config.expanduser().resolve()
    data = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    if not isinstance(data, dict) or not isinstance(data.get("mcpServers", {}), dict):
        parser.error("现有配置不是有效的 MCP 对象，未覆盖")
    servers = data.setdefault("mcpServers", {})
    if "privacyguard" in servers:
        if servers["privacyguard"] == entry:
            print("已有完全相同的 PrivacyGuard 配置，无需修改。")
            return
        parser.error("已有不同的 privacyguard 配置，未覆盖；请手动核对生成文件")
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = target.with_name(f"{target.name}.privacyguard-backup-{stamp}")
        shutil.copy2(target, backup)
        backup.chmod(0o600)
        print(f"已备份：{backup}")
    servers["privacyguard"] = entry
    write_private(target, data)
    print("已保留其他 MCP 并添加 PrivacyGuard。请重新打开 WorkBuddy，新建对话验证六个工具。")


if __name__ == "__main__":
    main()
