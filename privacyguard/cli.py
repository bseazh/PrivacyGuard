from __future__ import annotations

import argparse
import asyncio
import json

from .core import PrivacyGuard


def main() -> None:
    parser = argparse.ArgumentParser(prog="privacyguard")
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan")
    scan.add_argument("file")
    redact = commands.add_parser("redact")
    redact.add_argument("file")
    scrub = commands.add_parser("scrub")
    scrub.add_argument("text")
    get = commands.add_parser("get")
    get.add_argument("reference")
    ask = commands.add_parser("ask")
    ask.add_argument("reference")
    ask.add_argument("--task", choices=("risk_summary", "summary"), default="risk_summary")
    args = parser.parse_args()
    core = PrivacyGuard()
    if args.command == "scan":
        result = core.scan_file(args.file)
    elif args.command == "redact":
        result = core.redact_file(args.file)
    elif args.command == "scrub":
        result = core.scrub_text(args.text)
    elif args.command == "ask":
        result = asyncio.run(core.secure_ask(args.reference, args.task))
    else:
        result = core.get_safe_content(args.reference)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
