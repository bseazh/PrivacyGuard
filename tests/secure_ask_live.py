"""Real MCP -> safe DOCX -> LiteLLM -> configured real model integration."""
import json
import os
import tempfile
from pathlib import Path

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from privacyguard.safe_files import rebuild_safe_file


async def main():
    root = Path(__file__).resolve().parents[1]
    text = "联系人：唐三\n邮箱：alice@example.com\n手机号：13800138000\n合同约定交付后付款，但没有约定付款期限、验收标准和违约责任。"
    with tempfile.TemporaryDirectory(prefix="privacyguard-model-live-") as directory:
        test_root = Path(directory).resolve()
        source = test_root / "fictional.docx"
        source.write_bytes(rebuild_safe_file(text, ".docx"))
        env = {"PRIVACYGUARD_ALLOWED_ROOTS": str(test_root), "PRIVACYGUARD_DATA_DIR": str(test_root / "state")}
        for key in ("PRIVACYGUARD_LLM_MODEL", "PRIVACYGUARD_LLM_BASE_URL", "PRIVACYGUARD_LLM_API_KEY", "PRIVACYGUARD_MLX_PYTHON"):
            if key in os.environ:
                env[key] = os.environ[key]
        params = StdioServerParameters(command=str(root / ".venv/bin/privacyguard-mcp"), cwd=root, env=env)
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                export = (await session.call_tool("privacy_redact_file", {"file_path": str(source)})).structured_content
                if not export or export.get("status") != "approved":
                    raise RuntimeError(f"export failed: {export}")
                result = (await session.call_tool("privacy_secure_ask", {"safe_reference": export["safe_reference"], "task": "risk_summary"})).structured_content
                if not result or result.get("status") != "approved":
                    raise RuntimeError(f"model failed: {result}")
                if any(value in result["answer"] for value in ("唐三", "alice@example.com", "13800138000")):
                    raise RuntimeError("model returned original values")
                invalid = (await session.call_tool("privacy_secure_ask", {"safe_reference": str(source)})).structured_content
                if not invalid or invalid.get("status") != "blocked":
                    raise RuntimeError("raw path accepted")
                print(json.dumps({"mcp_export": True, "mcp_secure_ask": True, "raw_path_blocked": True,
                                  "counts": export["counts"], "answer": result["answer"]}, ensure_ascii=False))


if __name__ == "__main__":
    anyio.run(main)
