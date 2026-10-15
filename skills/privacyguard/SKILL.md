---
name: privacyguard
description: Protect privacy before analyzing local contracts, customer materials, evidence materials, legal documents, TXT, Markdown, EML, DOCX, or PDF files. Automatically use when the user mentions a contract, privacy, redaction, anonymization, pseudonymization, customer materials, evidence materials, personal information, identity, phone, email, banking, address, signature, seal, or other sensitive information.
---

# PrivacyGuard

## Required workflow

1. Identify the absolute source path without opening or reading the source file.
2. By default, call only `privacy_process_and_ask` with that path and the fixed task `risk_summary` or `summary`. Do not call `privacy_get_safe_content` and do not bring sanitized document content into the host Agent context.
3. Set `create_safe_copy=false` unless the user explicitly asks to download, export, save, or receive a sanitized copy. For an explicit safe-copy request, call `privacy_process_and_ask` with `create_safe_copy=true`.
4. If the result is not `approved`, stop. Report the reason without reading the source or attempting another parser.
5. Return the approved answer, aggregate entity counts and, only when requested, the approved safe-file path. Never request or expose the internal `safe_reference`.

For text pasted directly by the user, call `privacy_scrub_text`, then pass its approved reference directly to `privacy_secure_ask`. Do not call `privacy_get_safe_content` unless the user explicitly asks to inspect the sanitized text.

An explicitly requested file export is returned by `privacy_process_and_ask` as `safe_file`. Explain that PDF/DOCX copies are reconstructed text-only and do not preserve layout. Never substitute an upstream download or desktop export for a verified safe file.

The default file workflow uses PrivacyGuard's configured LiteLLM path internally. Do not analyze file contents with the host Agent model. For pasted text, `privacy_secure_ask` accepts only an approved reference and a fixed task (`risk_summary` or `summary`). If blocked or not configured, stop. Do not pass raw text, source paths, arbitrary prompts, model names or URLs to an LLM.

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
