from urllib.parse import urlparse, parse_qs
from typing import Optional


class URIParseConfig:
    DEFAULT_SCHEME = "dns"
    DEFAULT_HOSTNAME = "localhost"
    DEFAULT_PORT = 443
    DEFAULT_TLS = False
    ACCEPTED_SCHEMES = ["dns", "unix", "unix-abstract", "vsock", "http", "https", "grpc", "grpcs"]
    VALID_SCHEMES = ["dns", "unix", "unix-abstract", "vsock", "grpc", "grpcs"]


class Endpoint:
    def __init__(self, scheme: str, hostname: str, port: Optional[int], tls: bool):
        self.scheme = scheme or URIParseConfig.DEFAULT_SCHEME
        self.hostname = hostname or URIParseConfig.DEFAULT_HOSTNAME
        self.port = port or URIParseConfig.DEFAULT_PORT
        self.tls = tls or URIParseConfig.DEFAULT_TLS

    def is_secure(self) -> bool:
        return self.tls

    def get_scheme(self) -> str:
        return self.scheme if self.scheme in URIParseConfig.VALID_SCHEMES else URIParseConfig.DEFAULT_SCHEME

    def get_port(self) -> str:
        if self.scheme in ["unix", "unix-abstract", "vsock"]:
            return ""

        return str(self.port)

    def get_hostname(self) -> str:
        hostname = self.hostname
        if self.hostname.count(":") == 7:
            # IPv6 address
            hostname = f"[{hostname}]"
        return hostname

    def get_endpoint(self) -> str:
        scheme = self.get_scheme()
        if scheme in ["unix", "unix-abstract", "vsock"]:
            return f"{scheme}://{self.hostname}"

        return f"{scheme}:{self.get_hostname()}:{self.get_port()}"


def parse_grpc_endpoint(url: str) -> Endpoint:
    url = preprocess_url(url)
    parsed_url = urlparse(url)
    validate_path_and_query(parsed_url.path, parsed_url.query, parsed_url.scheme)
    tls = extract_tls_from_query(parsed_url.query, parsed_url.scheme)

    return Endpoint(parsed_url.scheme, parsed_url.hostname, parsed_url.port, tls)


def preprocess_url(url: str) -> str:
    url_list = url.split(":")
    if len(url_list) == 3 and "://" not in url:
        # A URI like dns:mydomain:5000 was used
        url = url.replace(":", "://", 1)
    elif len(url_list) == 2 and "://" not in url and url_list[0] in URIParseConfig.ACCEPTED_SCHEMES:
        # A URI like dns:mydomain was used
        url = url.replace(":", "://", 1)
    else:
        url_list = url.split("://")
        if len(url_list) == 1:
            # If a scheme was not explicitly specified in the URL
            # we need to add a default scheme,
            # because of how urlparse works
            url = f'{URIParseConfig.DEFAULT_SCHEME}://{url}'
    return url


def validate_path_and_query(path: str, query: str, scheme: str) -> None:
    if path:
        raise ValueError(f"Paths are not supported for gRPC endpoints: '{path}'")
    if query:
        query_dict = parse_qs(query)
        if 'tls' in query_dict and scheme in ["http", "https"]:
            raise ValueError(
                f"The tls query parameter is not supported for http(s) endpoints: '{query}'")
        query_dict.pop('tls', None)
        if query_dict:
            raise ValueError(f"Query parameters are not supported for gRPC endpoints: '{query}'")


def extract_tls_from_query(query: str, scheme: str) -> bool:
    query_dict = parse_qs(query)
    tls = query_dict.get('tls', [None])[0]
    tls = tls and tls.lower() == 'true'
    if scheme == "https":
        tls = True
    return tls
