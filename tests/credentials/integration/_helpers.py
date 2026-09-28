import itertools

import httpx


def rotating_token_transport() -> httpx.MockTransport:
    """A fake RFC 8693 endpoint issuing an already-expired token per call, so every
    ``get()`` fetches a new one."""
    counter = itertools.count(1)

    def handler(request: httpx.Request) -> httpx.Response:
        token = f'token-{next(counter)}'
        return httpx.Response(200, json={'access_token': token, 'expires_in': 0})

    return httpx.MockTransport(handler)
