from uuid import uuid4


def anonymize() -> str:
    return f'PA-{uuid4().hex}'


def redact(value):
    sensitive = {'name', 'password', 'token', 'identity', 'id_number', 'face', 'email', 'phone'}
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items() if k.lower() not in sensitive}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value
