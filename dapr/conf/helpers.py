from urllib.parse import urlparse, parse_qs

DEFAULT_SCHEME = "dns"
DEFAULT_HOSTNAME = "localhost"
DEFAULT_PORT = 443
DEFAULT_PATH = ""
DEFAULT_QUERY = ""
DEFAULT_TLS_PORT = 443
DEFAULT_TLS = False
ACCEPTED_SCHEMES = ["dns", "unix", "unix-abstract", "vsock", "http", "https", "grpc", "grpcs"]
VALID_SCHEMES = ["dns", "unix", "unix-abstract", "vsock", "grpc", "grpcs"]


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

    def get_scheme(self) -> str:
        return self.scheme if self.scheme in VALID_SCHEMES else DEFAULT_SCHEME

    def get_port(self) -> str:
        return str(self.port)

    def get_hostname(self) -> str:
        hostname = self.hostname
        hostname_list = hostname.split(":")
        if len(hostname_list) == 8:
            # IPv6 address
            hostname = f"[{hostname}]"
        return hostname

    def get_endpoint(self) -> str:
        return f"{self.get_scheme()}:{self.get_hostname()}:{self.get_port()}"


def parse_grpc_endpoint(url: str) -> Endpoint:
    url_list = url.split(":")
    if len(url_list) == 3 and "://" not in url:
        # A URI like dns:mydomain:5000 was used
        url = url.replace(":", "://", 1)
    elif len(url_list) == 2 and "://" not in url and url_list[0] in ACCEPTED_SCHEMES:
        # A URI like dns:mydomain was used
        url = url.replace(":", "://", 1)
    else:
        url_list = url.split("://")
        if len(url_list) == 1:
            # If a scheme was not explicitly specified in the URL
            # we need to add a default scheme,
            # because of how urlparse works
            url = f'{DEFAULT_SCHEME}://{url}'

    parsed_url = urlparse(url)
    scheme = parsed_url.scheme
    hostname = parsed_url.hostname or DEFAULT_HOSTNAME
    port = parsed_url.port
    path = parsed_url.path
    query = parsed_url.query

    if len(path) > 0:
        raise ValueError(f"paths are not supported for gRPC endpoints: '{path}' in '{url}'")

    query_dict = parse_qs(query)

    # Check if the query string contains a tls parameter
    tls = False
    if 'tls' in query_dict and scheme in ["http", "https"]:
        raise ValueError(
            f"the tls query parameter is not supported for http(s) endpoints: '{query}' in '{url}'")
    if 'tls' in query_dict:
        tls = query_dict.get('tls')[0].lower() == "true"

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