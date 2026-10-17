from __future__ import annotations

import json
import hashlib
import logging
import re
from pathlib import Path

try:
    from mlx_lm import load
    from mlx_lm.generate import stream_generate
    from mlx_lm.sample_utils import greedy_sampler
except ImportError:  # Parser and policy tests also run on non-Apple platforms.
    load = stream_generate = greedy_sampler = None

from .redaction_core import Entity


logger = logging.getLogger("privacyguard.api")


TYPE_NAMES = {
    "PERSON": "姓名",
    "ORGANIZATION": "机构",
    "ADDRESS": "地址",
    "DEPARTMENT": "部门",
    "PROJECT": "项目名",
    "COURT": "法院",
    "LAW_FIRM": "律师事务所",
    "PLAINTIFF": "原告",
    "DEFENDANT": "被告",
    "APPLICANT": "申请人",
    "RESPONDENT": "被申请人",
    "ATTORNEY": "代理人",
    "LEGAL_REPRESENTATIVE": "法定代表人",
}
ROLE_LABELS = {key: value for key, value in TYPE_NAMES.items() if key in {"PLAINTIFF", "DEFENDANT", "APPLICANT", "RESPONDENT", "ATTORNEY", "LEGAL_REPRESENTATIVE"}}
_B_PERSON_EXCLUSIONS = {"本人", "对方", "双方", "甲方", "乙方", "原告", "被告", "申请人", "代理人", "联系人", "员工", "客户", "领导", "同事", "法官", "律师", "男方", "女方"}
_B_PROJECT_EXCLUSIONS = {"原装货", "补充协议", "合作协议", "采购合同", "销售合同", "服务合同", "库存同步异常", "测试", "项目", "合同", "协议", "系统", "产品", "材料", "货物", "问题", "现象"}


def conservative_filter(entities: list[Entity]) -> tuple[list[Entity], int]:
    kept = []
    filtered = 0
    for entity in entities:
        if entity.type == "PERSON" and (entity.value in _B_PERSON_EXCLUSIONS or re.fullmatch(r"(?:男|女)\d+", entity.value) or re.fullmatch(r"[\u4e00-\u9fff]{1,3}(?:总|经理|主任|老师|律师|先生|女士|工|董)", entity.value)):
            filtered += 1
            continue
        if entity.type == "PROJECT" and entity.value in _B_PROJECT_EXCLUSIONS:
            filtered += 1
            continue
        kept.append(entity)
    return kept, filtered


def parse_ner_response(raw: str, text: str, entity_types: list[str]) -> list[Entity]:
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("NER response does not contain a complete JSON object")
    data = json.loads(cleaned[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("NER response root must be a JSON object")
    inverse = {value: key for key, value in TYPE_NAMES.items()}
    entities: list[Entity] = []
    seen: set[tuple[str, str, int, int]] = set()
    for label, values in data.items():
        type_id = inverse.get(label, label)
        if type_id not in entity_types:
            continue
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            continue
        for value in dict.fromkeys(item for item in values if isinstance(item, str) and item):
            offset = 0
            while True:
                found = text.find(value, offset)
                if found < 0:
                    break
                if type_id in ROLE_LABELS:
                    context = text[max(0, found - 12):min(len(text), found + len(value) + 12)]
                    if ROLE_LABELS[type_id] not in context:
                        offset = found + max(1, len(value))
                        continue
                key = (type_id, value, found, found + len(value))
                if key not in seen:
                    seen.add(key)
                    entities.append(Entity(type_id, value, found, found + len(value), 0.9, "ner"))
                offset = found + max(1, len(value))
    return sorted(entities, key=lambda item: (item.start, item.end, item.type))


class Qwen3NerBackend:
    name = "qwen3-1.7b-bf16"

    def __init__(self, model_path: str | Path):
        if load is None:
            raise RuntimeError("MLX runtime 未安装；Apple Silicon 请安装 mlx-lm，其他平台请使用规则或远程 NER")
        self.model, self.tokenizer = load(str(model_path))
        self.last_response_valid = True
        self.last_response_error = None
        self.last_filtered_count = 0

    def recognize(self, text: str, entity_types: list[str], prompt_variant: str = "A") -> list[Entity]:
        requested = [TYPE_NAMES.get(item, item) for item in entity_types]
        variant_rules = ""
        if prompt_variant.upper() == "B":
            variant_rules = ("姓名只能是具体自然人的姓名，不能是男1、女1、周总、王经理、本人、对方等说话人标签、称谓或泛化称呼；这些值不要归入姓名。"
                             "项目名必须是明确的专有项目/系统/产品名称，补充协议、合作协议、原装货、测试、问题、现象等普通业务词不要归入项目名。")
        body = ("你是中文法律文书实体抽取器。请完整识别文本中的实体。每个不同的实体值只返回一次，程序会自动定位它在原文中的所有重复位置。"
                "机构、法院、律师事务所、部门、项目名必须分开。原告/被告/申请人/被申请人/代理人/法定代表人等法律角色的值只返回对应的人名或机构名，不要把角色词混入值。"
                f"{variant_rules}"
                "实体值必须逐字来自原文，不得改写、缩写、合并或猜测。只返回单行 JSON 对象，不要解释、不要思考过程、不要 Markdown。"
                f"JSON 的键只能是这些类型：{json.dumps(requested, ensure_ascii=False)}。"
                "每个键的值必须是字符串数组；没有实体的类型可以省略；完全没有实体时返回 {}。\n"
                f"文本：{text}")
        try:
            prompt = self.tokenizer.apply_chat_template([{"role": "user", "content": body}], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except TypeError:
            prompt = f"<|im_start|>user\n{body}<|im_end|>\n<|im_start|>assistant\n"
        chunks: list[str] = []
        for response in stream_generate(self.model, self.tokenizer, prompt, max_tokens=512, sampler=greedy_sampler):
            chunks.append(response.text)
        raw = "".join(chunks).strip()
        try:
            entities = parse_ner_response(raw, text, entity_types)
            filtered_count = 0
            if prompt_variant.upper() == "B":
                entities, filtered_count = conservative_filter(entities)
            self.last_response_valid = True
            self.last_response_error = None
            self.last_filtered_count = filtered_count
            logger.info("ner_response_parsed response_chars=%d entities=%d conservative_filtered=%d", len(raw), len(entities), filtered_count)
            return entities
        except (json.JSONDecodeError, ValueError) as exc:
            self.last_response_valid = False
            self.last_response_error = str(exc)
            self.last_filtered_count = 0
            digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
            logger.warning("ner_response_invalid response_chars=%d sha256=%s error=%s", len(raw), digest, exc)
            return []


def recognize_chunked(backend: Qwen3NerBackend, text: str, entity_types: list[str], chunk_chars: int = 2400, overlap: int = 300, prompt_variant: str = "B") -> list[Entity]:
    """Run NER over bounded windows and restore document-global offsets."""
    step = max(1, chunk_chars - overlap)
    result: list[Entity] = []
    seen: set[tuple[str, str, int, int]] = set()
    for offset in range(0, len(text), step):
        chunk = text[offset:offset + chunk_chars]
        if chunk.strip():
            for entity in backend.recognize(chunk, entity_types, prompt_variant=prompt_variant):
                item = Entity(entity.type, entity.value, offset + entity.start, offset + entity.end, entity.confidence, entity.source)
                key = (item.type, item.value, item.start, item.end)
                if key not in seen:
                    seen.add(key)
                    result.append(item)
        if offset + chunk_chars >= len(text):
            break
    return sorted(result, key=lambda item: (item.start, item.end))
