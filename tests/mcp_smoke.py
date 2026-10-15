from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from privacyguard.safe_files import rebuild_safe_file


async def run() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="privacyguard-mcp-") as directory:
        await exercise(root, Path(directory).resolve())


async def exercise(root: Path, test_root: Path) -> None:
    params = StdioServerParameters(
        command=str(root / ".venv/bin/privacyguard-mcp"),
        cwd=root,
        env={"PRIVACYGUARD_ALLOWED_ROOTS": os.pathsep.join((str(root), str(test_root))),
             "PRIVACYGUARD_DATA_DIR": str(test_root / "state")},
    )
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(item.name for item in tools.tools)
            expected = ["privacy_get_safe_content", "privacy_redact_file", "privacy_scan_file", "privacy_scrub_text", "privacy_secure_ask"]
            if names != expected:
                raise RuntimeError(f"unexpected tools: {names}")
            result = await session.call_tool("privacy_scrub_text", {"text": "联系 alice@example.com 或 13800138000"})
            if result.is_error:
                raise RuntimeError(str(result.content))
            payload = result.structured_content
            if not isinstance(payload, dict) or payload.get("status") != "approved":
                raise RuntimeError(f"tool did not approve safe output: {payload}")
            scan = await session.call_tool("privacy_scan_file", {"file_path": str(root / "samples/fictional_contract.txt")})
            scan_payload = scan.structured_content
            if not isinstance(scan_payload, dict) or scan_payload.get("status") != "approved":
                raise RuntimeError(f"file scan failed: {scan_payload}")
            safe = await session.call_tool("privacy_get_safe_content", {"safe_reference": scan_payload["safe_reference"]})
            safe_payload = safe.structured_content
            if not isinstance(safe_payload, dict) or safe_payload.get("status") != "approved":
                raise RuntimeError(f"safe content retrieval failed: {safe_payload}")
            serialized = json.dumps(safe_payload, ensure_ascii=False)
            if "alice@example.com" in serialized or "13800138000" in serialized or "11010519491231002X" in serialized:
                raise RuntimeError("safe MCP output still contains source PII")
            for suffix in (".pdf", ".docx"):
                source = test_root / f"fictional{suffix}"
                source.write_bytes(rebuild_safe_file("联系人：唐三\n邮箱：alice@example.com", suffix))
                exported = await session.call_tool("privacy_redact_file", {"file_path": str(source)})
                payload = exported.structured_content
                if exported.is_error or not isinstance(payload, dict) or payload.get("status") != "approved":
                    raise RuntimeError(f"safe file export failed: {payload}")
                retrieved = await session.call_tool("privacy_get_safe_content", {"safe_reference": payload["safe_reference"]})
                payload = retrieved.structured_content
                if retrieved.is_error or not isinstance(payload, dict) or payload.get("status") != "approved":
                    raise RuntimeError("safe file retrieval failed")
                if payload.get("kind") != "file" or not Path(payload["path"]).is_file():
                    raise RuntimeError("safe file missing")
                if any(value in payload["content"] for value in ("唐三", "alice@example.com")):
                    raise RuntimeError("safe file residual PII")
            print(json.dumps({"tools": names, "scrub_text": True, "scan_and_get": True, "redact_and_get": True}, ensure_ascii=False))


if __name__ == "__main__":
    anyio.run(run)
