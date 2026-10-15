"""Opt-in real-model regression for the fictional chat acceptance fixture.

This checks known regressions, not general factual correctness. It never reads
the source document or retrieves a safe reference into the test client.
"""
import json
import os
from pathlib import Path

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main():
    root = Path(__file__).resolve().parents[1]
    env = {key: value for key, value in os.environ.items() if key.startswith("PRIVACYGUARD_")}
    params = StdioServerParameters(command=str(root / ".venv/bin/privacyguard-mcp"), cwd=root, env=env)
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            result = await session.call_tool("privacy_process_and_ask", {
                "file_path": str(root / "tests/fixtures/chat-acceptance-contract.txt"),
                "task": "risk_summary", "create_safe_copy": False,
            })
            payload = result.structured_content
            if result.is_error or not payload or payload.get("status") != "approved":
                raise AssertionError("Unified analysis did not approve")
            assert "content" not in payload and "safe_reference" not in payload
            assert payload.get("safe_file") is None
            answer = payload["answer"]
            for raw in ("唐三", "alice@example.com", "13800138000"):
                assert raw not in json.dumps(payload, ensure_ascii=False), "Original value leaked"
            for section in ("【材料事实】", "【条款风险】", "【待核查事项】"):
                assert section in answer, "Missing distinction between facts and advice"
            for regression in ("可能默认按合同签订", "可能导致买方无权拒绝验收", "影响合同效力",
                               "未约定付款条件", "可能导致交付不合格品", "付款条件未明确",
                               "未约定付款前提", "联系人信息未提供", "隐含的验收标准"):
                assert regression not in answer, "Known unsupported inference returned"
            assert "未约定" in answer
            print(json.dumps({"known_regressions_passed": True, "manual_quality_review_required": True,
                              "result": payload}, ensure_ascii=False))


if __name__ == "__main__":
    anyio.run(main)
