"""Real local-service integration; never substitutes mocked NER or export results."""
import json
import tempfile
from pathlib import Path

from privacyguard.config import Settings
from privacyguard.core import PrivacyGuard
from privacyguard.safe_files import rebuild_safe_file


def main():
    text = "甲方：史莱克学院\n联系人：唐三\n地址：天斗城史莱克路88号\n电话：13800138000\n邮箱：alice@example.com\n唐三负责交付。"
    with tempfile.TemporaryDirectory(prefix="privacyguard-live-") as directory:
        root = Path(directory).resolve()
        settings = Settings((root,), root / "state", 50 * 1024 * 1024, 3600,
                            "http://127.0.0.1:5002", "http://127.0.0.1:8000", None)
        core = PrivacyGuard(settings)
        results = []
        for suffix in (".docx", ".pdf"):
            path = root / f"fictional{suffix}"
            path.write_bytes(rebuild_safe_file(text, suffix))
            result = core.redact_file(str(path))
            if result["status"] != "approved":
                raise RuntimeError(f"{suffix} live export blocked: {result['reason']}")
            safe = core.get_safe_content(result["safe_reference"])
            for value in ("唐三", "史莱克学院", "天斗城史莱克路88号", "13800138000", "alice@example.com"):
                if value in safe["content"]:
                    raise RuntimeError(f"{suffix} residual PII")
            if not Path(safe["path"]).is_file():
                raise RuntimeError("approved output missing")
            results.append({"format": suffix, "counts": result["counts"], "verified": True})
        print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
