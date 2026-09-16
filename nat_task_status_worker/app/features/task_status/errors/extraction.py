import json


def extract_error_message(
    body: str,
    *,
    http_status: int,
    action: str,
) -> str:
    stripped = body.strip()
    if stripped:
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return _truncate(stripped, http_status=http_status, action=action)
        if isinstance(payload, dict):
            for key in ('message', 'error', 'detail', 'description'):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return _truncate(stripped, http_status=http_status, action=action)
    return f'HTTP {http_status} on ACTION={action}'


def _truncate(body: str, *, http_status: int, action: str) -> str:
    text = body.strip()
    if len(text) > 2000:
        return f'{text[:2000]}...'
    if text:
        return text
    return f'HTTP {http_status} on ACTION={action}'
