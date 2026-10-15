---
name: privacyguard
description: Protect privacy in local TXT, Markdown, DOCX, and PDF files before analysis. Use when a user asks to analyze a local contract or document containing personal, legal, customer, identity, phone, email, banking, address, signature, seal, or other sensitive information, or explicitly asks for privacy protection, redaction, anonymization, or pseudonymization.
---

# PrivacyGuard

## Required workflow

1. Identify the absolute source path without opening or reading the source file.
2. For analysis, call MCP tool `privacy_scan_file` with that path. For a downloadable safe PDF/DOCX copy, call `privacy_redact_file` instead.
3. If the result is not `approved`, stop. Report the reason without reading the source.
4. Call `privacy_get_safe_content` using only the returned `safe_reference`.
5. Continue the user's original analysis using the approved safe content.
6. Never substitute a raw path for a safe reference.

For text pasted directly by the user, call `privacy_scrub_text`, then retrieve the approved result with `privacy_get_safe_content` before continuing.

File export returns a safe reference, not a source path. Retrieve the approved output path using `privacy_get_safe_content`. Explain that the copy is reconstructed text-only and does not preserve layout. Never substitute an upstream download or desktop export for a verified safe file reference.

If the user explicitly asks PrivacyGuard to use its configured LLM, call `privacy_secure_ask` using only an approved `safe_reference` and a fixed task (`risk_summary` or `summary`). If blocked or not configured, stop. Do not pass raw text, source paths, or arbitrary prompts to an LLM. Otherwise, analyze only the retrieved safe content as usual.

## Fail-closed rules

- Never fall back to the original content when Presidio, OCR, parsing, validation, or MCP fails.
- Never include detected raw values in chat, logs, or diagnostics.
- Treat `blocked`, expired references, unsupported formats, and incomplete scanned-PDF OCR as terminal for the protected workflow.
- Safe file export blocks unverified images, vector drawings, revisions, fields and complex objects. Do not bypass this restriction by converting to text yourself.
- Tell the user that detection reduces risk but cannot prove that no sensitive information remains.

## Security boundary

This skill instructs a cooperative Agent to use PrivacyGuard first. A Skill or MCP server cannot technically prevent a host Agent from reading a file before invoking the tool. Do not claim complete interception of Codex, WorkBuddy, or their model traffic.

## Explicit use

The user can invoke this skill as `$privacyguard` and provide an absolute local path plus the analysis request.
