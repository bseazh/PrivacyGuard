"""Built-in policies: a matcher, validation, direction, action and replacement format."""
import re
from service.redaction_core import PATTERNS, is_valid_china_id
from privacyguard.models import Finding
from privacyguard.rules import merge_findings, replace_with_tokens

VERSION = 'legal-basic-2'
CREDENTIAL_PATTERN = r'-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{12,}'
CREDENTIAL = re.compile(CREDENTIAL_PATTERN, re.I)
PHONE_PATTERN = r'(?<![0-9])(?:\+86[ -]?)?1[3-9][0-9][ -]?[0-9]{4}[ -]?[0-9]{4}(?![0-9])'
BUILTINS = tuple((kind, PHONE_PATTERN if kind == 'PHONE' else pattern, score) for kind, pattern, score in PATTERNS)


def detect_builtin(text):
    findings = []
    for kind, pattern, score in BUILTINS:
        for match in re.finditer(pattern, text, re.I):
            if kind == 'ID_NUMBER' and not is_valid_china_id(match.group()):
                continue
            findings.append(Finding(kind, match.start(), match.end(), score, 'gateway-builtin'))
    return merge_findings(findings)


def catalog():
    validators = {'ID_NUMBER': '18 位格式 + 有效出生日期 + 校验位；不验证行政区代码是否存在，不覆盖 15 位旧证件',
                  'PHONE': '中国大陆手机号格式；可含 +86 和分隔符，不验证号码是否真实存在',
                  'BANK_CARD': '候选格式检测，未做发卡行及 Luhn 验真，可能误报'}
    rows = [{'id': 'credential.block', 'type': 'CREDENTIAL', 'expression': CREDENTIAL_PATTERN,
             'validation': '示例私钥标记与 sk- 凭据；不覆盖所有密钥格式', 'request': 'BLOCK', 'response': 'BLOCK', 'replacement': '无'}]
    for kind, pattern, _ in BUILTINS:
        rows.append({'id': 'builtin.' + kind.lower(), 'type': kind, 'expression': pattern,
                     'validation': validators.get(kind, '格式候选检测'), 'request': 'REDACT',
                     'response': 'BLOCK', 'replacement': f'<{kind}_001>'})
    rows.append({'id': 'semantic.entities', 'type': 'SEMANTIC', 'expression': 'HaS + Presidio + 规则合并（非正则）',
                 'validation': '姓名、机构等依赖语义识别；不确定语义实体阻断并要求复核',
                 'request': 'REDACT', 'response': 'BLOCK', 'replacement': '<PERSON_001> / <ORGANIZATION_001> …'})
    return {'version': VERSION, 'editable': False, 'rules': rows,
            'default_action': '无命中且所有检查成功才 ALLOW；BLOCK 优先；复检残留仍 BLOCK'}


EXAMPLES = (
    ('phone-basic', 'PHONE', '联系：13800138000', True),
    ('phone-separated', 'PHONE', '联系：+86 138-1001-2345', True),
    ('not-mobile-prefix', 'PHONE', '编号：12800138000', False),
    ('not-mobile-boundary', 'PHONE', '编号：9138001380008', False),
    ('id-checksum', 'ID_NUMBER', '教学测试号：11010519491231002X', True),
    ('id-invalid-checksum', 'ID_NUMBER', '教学测试号：110105194912310021', False),
    ('id-invalid-date', 'ID_NUMBER', '教学测试号：11010519490231002X', False),
    ('email', 'EMAIL', '邮箱：alice@example.com', True),
    ('email-incomplete', 'EMAIL', '邮箱：alice@', False),
    ('private-key', 'CREDENTIAL', '-----BEGIN PRIVATE KEY-----', True),
    ('plain-text', 'CREDENTIAL', '请说明履行期限。', False),
)


def run_examples():
    results = []
    for name, kind, sample, expected in EXAMPLES:
        hits = [f for f in detect_builtin(sample) if f.entity_type == kind]
        matched = bool(CREDENTIAL.search(sample)) if kind == 'CREDENTIAL' else bool(hits)
        results.append({'name': name, 'entity_type': kind, 'input': sample,
                        'expected_match': expected, 'actual_match': matched, 'passed': matched == expected,
                        'request_action': ('BLOCK' if kind == 'CREDENTIAL' else 'REDACT') if matched else 'ALLOW',
                        'request_output': None if kind == 'CREDENTIAL' and matched else replace_with_tokens(sample, hits),
                        'response_action': 'BLOCK' if matched else 'ALLOW',
                        'response_output': None if matched else sample})
    return {'version': VERSION, 'fixture_only': True, 'calls_upstream': False,
            'scope': '内置格式规则的逐项单元测试；不是完整 HaS 语义召回率或整条上游链路验收',
            'passed': all(r['passed'] for r in results), 'results': results}
