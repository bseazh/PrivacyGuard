"""Real MCP -> safe DOCX -> LiteLLM -> configured real model integration."""
import json
import os
import tempfile
from pathlib import Path

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from privacyguard.safe_files import rebuild_safe_file, inspect_source


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
                text_source = test_root / "fictional.txt"
                text_source.write_text(text, encoding="utf-8")
                text_export = (await session.call_tool("privacy_redact_file", {"file_path": str(text_source)})).structured_content
                if not text_export or text_export.get("status") != "approved" or text_export.get("output_kind") != "safe-file":
                    raise RuntimeError(f"text safe-output routing failed: {text_export}")
                text_result = (await session.call_tool("privacy_secure_ask", {
                    "safe_reference": text_export["safe_reference"], "task": "risk_summary",
                })).structured_content
                if not text_result or text_result.get("status") != "approved":
                    raise RuntimeError(f"text model flow failed: {text_result}")
                if any(value in text_result["answer"] for value in ("唐三", "alice@example.com", "13800138000")):
                    raise RuntimeError("text model flow returned original values")
                before_outputs = {p for p in (test_root / "state").rglob("*") if p.suffix in {".txt", ".docx", ".pdf"}}
                unified = (await session.call_tool("privacy_process_and_ask", {
                    "file_path": str(text_source), "task": "risk_summary", "create_safe_copy": False,
                })).structured_content
                if not unified or unified.get("status") != "approved":
                    raise RuntimeError(f"unified agent flow failed: {unified}")
                serialized = json.dumps(unified, ensure_ascii=False)
                if "safe_reference" in unified or "content" in unified:
                    raise RuntimeError("unified agent flow exposed internal content or reference")
                if any(value in serialized for value in ("唐三", "alice@example.com", "13800138000")):
                    raise RuntimeError("unified agent flow returned original values")
                after_outputs = {p for p in (test_root / "state").rglob("*") if p.suffix in {".txt", ".docx", ".pdf"}}
                if unified.get("safe_file") is not None or before_outputs != after_outputs:
                    raise RuntimeError("analysis unexpectedly created an output file")
                downloadable = (await session.call_tool("privacy_process_and_ask", {
                    "file_path": str(source), "task": "summary", "create_safe_copy": True,
                })).structured_content
                if not downloadable or downloadable.get("status") != "approved":
                    raise RuntimeError(f"unified export flow failed: {downloadable}")
                safe_file = Path(downloadable["safe_file"]["path"])
                safe_text = inspect_source(safe_file)
                if any(value in safe_text for value in ("唐三", "alice@example.com", "13800138000")):
                    raise RuntimeError("unified export contains original values")
                invalid = (await session.call_tool("privacy_secure_ask", {"safe_reference": str(source)})).structured_content
                if not invalid or invalid.get("status") != "blocked":
                    raise RuntimeError("raw path accepted")
                print(json.dumps({"mcp_export": True, "text_safe_output": True, "mcp_secure_ask": True,
                                  "privacy_process_and_ask": True, "analysis_no_file": True,
                                  "unified_download": True, "raw_path_blocked": True,
                                  "counts": export["counts"], "answer": result["answer"]}, ensure_ascii=False))


if __name__ == "__main__":
    anyio.run(main)
