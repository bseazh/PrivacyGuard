from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .core import PrivacyGuard


mcp = MCPServer("PrivacyGuard", instructions="Scan local files before an Agent reads their contents. Fail closed on every error. MCP clients should consume structuredContent and use text content only as a compatibility fallback; never log safe_reference values.")


@mcp.tool(structured_output=True)
def privacy_scan_file(file_path: str, policy: str = "default") -> dict[str, object]:
    """Scan a local TXT, Markdown, DOCX, or PDF and return only a safe reference.

    Use this before reading a user file when privacy protection is requested. Never
    read the original file yourself first. A blocked result must stop the workflow.
    """
    if policy != "default":
        return {"status": "blocked", "reason": "未知策略", "counts": {}, "safe_reference": None}
    return PrivacyGuard().scan_file(file_path)


@mcp.tool(structured_output=True)
def privacy_get_safe_content(safe_reference: str) -> dict[str, object]:
    """Read content only through an approved, unexpired PrivacyGuard reference."""
    return PrivacyGuard().get_safe_content(safe_reference)


@mcp.tool(structured_output=True)
def privacy_scrub_text(text: str) -> dict[str, object]:
    """Remove PII from text and return a safe reference; fail closed if Presidio fails."""
    return PrivacyGuard().scrub_text(text)


@mcp.tool(structured_output=True)
def privacy_redact_file(file_path: str) -> dict[str, object]:
    """Create an approved safe output for TXT/Markdown/EML/PDF/DOCX.

    Text formats return a sanitized text reference. PDF/DOCX return a verified,
    reconstructed file copy. Retrieve either only via privacy_get_safe_content.
    """
    return PrivacyGuard().redact_file(file_path)


@mcp.tool(structured_output=True)
async def privacy_secure_ask(safe_reference: str, task: str = "risk_summary") -> dict[str, object]:
    """Analyze only approved references via LiteLLM with mandatory pre-send Presidio.

    task is risk_summary or summary. No raw prompts, paths, URLs or model settings.
    This does not intercept the host Agent's own model traffic.
    """
    return await PrivacyGuard().secure_ask(safe_reference, task)


@mcp.tool(structured_output=True)
async def privacy_process_and_ask(
    file_path: str,
    task: str = "risk_summary",
    create_safe_copy: bool = False,
) -> dict[str, object]:
    """Privately process a local file and return only a controlled model answer.

    This is the default Agent entry point for contracts, customer materials and
    evidence. It performs scanning, redaction, reference isolation, LiteLLM
    pre-send guardrails and answer rechecking internally. It never returns source
    text or the bearer safe_reference. Set create_safe_copy only when the user
    explicitly asks for a downloadable sanitized file.
    """
    return await PrivacyGuard().process_and_ask(file_path, task, create_safe_copy)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
