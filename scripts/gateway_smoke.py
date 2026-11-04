"""Exercise a running gateway using fictional data. Prints no credential or response body."""
import argparse
import json
from pathlib import Path

import httpx
from openai import OpenAI, APIStatusError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-config', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.client_config.read_text())
    if config['base_url'] != 'http://127.0.0.1:8787/v1':
        raise ValueError('Smoke test is restricted to local gateway')
    with httpx.Client(trust_env=False, timeout=240) as transport:
        with OpenAI(api_key=config['api_key'], base_url=config['base_url'],
                    http_client=transport, max_retries=0) as client:
            models = client.models.list()
            assert config['model'] in [item.id for item in models.data]
            print('models: PASS', flush=True)
            for name, content, stream, status in [
                ('private_key_block', '-----BEGIN PRIVATE KEY-----', False, 422),
                ('stream_rejected', '请总结合同。', True, 400),
            ]:
                try:
                    client.chat.completions.create(model=config['model'],
                        messages=[{'role': 'user', 'content': content}], stream=stream)
                    raise AssertionError('Expected rejection')
                except APIStatusError as exc:
                    assert exc.status_code == status
                    print(name + ': PASS', flush=True)
            result = client.chat.completions.create(model=config['model'], stream=False,
                messages=[{'role': 'user', 'content':
                    '请用一句话说明本条款缺少的付款安排，不复述联系方式：合同约定交付后付款，但没有付款期限。'
                    '虚构联系人邮箱 alice@example.com，电话13800138000。'}])
            answer = result.choices[0].message.content
            assert answer and 'alice@example.com' not in answer and '13800138000' not in answer
            metadata = result.model_extra['privacyguard']
            assert metadata['status'] == 'approved' and metadata['entity_count'] >= 2
            print('real_model_roundtrip: PASS; entity_count=' + str(metadata['entity_count']), flush=True)


if __name__ == '__main__':
    main()
