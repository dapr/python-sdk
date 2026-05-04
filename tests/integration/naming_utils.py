import uuid


def unique_name(*, prefix: str = '', suffix: str = '') -> str:
    return f'{prefix}{uuid.uuid4().hex[:8]}{suffix}'
