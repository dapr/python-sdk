from typing import Tuple
from urllib.parse import urlparse, parse_qs

DEFAULT_SCHEME = "grpc"
DEFAULT_HOSTNAME = "localhost"
DEFAULT_PORT = 50001
DEFAULT_PATH = ""
DEFAULT_QUERY = ""
DEFAULT_TLS_PORT = 443
DEFAULT_TLS = False


class Endpoint:
    scheme: str
    hostname: str
    port: int
    path: str
    query: str
    tls: bool

    def __init__(self, scheme: str, hostname: str, port: int, path: str, query: str, tls: bool):
        self.scheme = scheme or DEFAULT_SCHEME
        self.hostname = hostname or DEFAULT_HOSTNAME
        self.port = port or DEFAULT_PORT
        self.path = path or DEFAULT_PATH
        self.query = query or DEFAULT_QUERY
        self.tls = tls or DEFAULT_TLS

    def is_secure(self) -> bool:
        return self.tls

    def to_string(self) -> str:
        return f"{self.scheme}://{self.hostname}:{self.port}"


def parse_grpc_endpoint(url: str) -> Endpoint:
    # If a scheme was not explicitly specified in the URL
    # we need to add a default scheme,
    # because of how urlparse works
    url_list = url.split("://")
    if len(url_list) == 1:
        url = f'{DEFAULT_SCHEME}://{url}'

    parsed_url = urlparse(url)
    scheme = parsed_url.scheme
    hostname = parsed_url.hostname or DEFAULT_HOSTNAME
    port = parsed_url.port
    path = parsed_url.path
    query = parsed_url.query

    if len(path) > 0:
        raise ValueError(f"paths are not supported for gRPC endpoints: '{path}' in '{url}'")

    # Check if the query string contains a tls parameter
    query_dict = parse_qs(query)
    tls = query_dict.get('tls', ["False"])
    tls = True if tls and tls[0].lower() == 'true' else False

    # Special case for backwards compatibility
    if scheme == "https":
        tls = True
        scheme = DEFAULT_SCHEME
        port = port or DEFAULT_TLS_PORT

    query_dict.pop('tls', None)
    if len(query_dict) > 0:
        raise ValueError(
            f"query parameters are not supported for gRPC endpoints: '{query}' in '{url}'")

    return Endpoint(scheme, hostname, port, path, query, tls)
