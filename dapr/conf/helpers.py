from urllib.parse import urlparse, parse_qs


class URIParseConfig:
    DEFAULT_SCHEME = "dns"
    DEFAULT_HOSTNAME = "localhost"
    DEFAULT_PORT = 443
    DEFAULT_TLS = False
    DEFAULT_AUTHORITY = ""
    ACCEPTED_SCHEMES = ["dns", "unix", "unix-abstract", "vsock", "http", "https", "grpc", "grpcs"]
    VALID_SCHEMES = ["dns", "unix", "unix-abstract", "vsock", "grpc", "grpcs"]


class GrpcEndpoint:
    def __init__(self, url: str):
        self.authority = URIParseConfig.DEFAULT_AUTHORITY
        self.url = url

        url = self.preprocess_url(url)
        parsed_url = urlparse(url)
        validate_path_and_query(parsed_url.path, parsed_url.query, parsed_url.scheme)
        tls = extract_tls_from_query(parsed_url.query, parsed_url.scheme)

        self.scheme = parsed_url.scheme or URIParseConfig.DEFAULT_SCHEME
        self.hostname = parsed_url.hostname or URIParseConfig.DEFAULT_HOSTNAME
        self.port = parsed_url.port or URIParseConfig.DEFAULT_PORT
        self.tls = tls or URIParseConfig.DEFAULT_TLS

    def is_secure(self) -> bool:
        return self.tls

    def get_scheme(self) -> str:
        return self.scheme if self.scheme in URIParseConfig.VALID_SCHEMES \
            else URIParseConfig.DEFAULT_SCHEME

    def get_port(self) -> str:
        port = self.get_port_as_int()
        if port == 0:
            return ""

        return str(port)

    def get_port_as_int(self) -> int:
        if self.scheme in ["unix", "unix-abstract"]:
            return 0

        return self.port

    def get_hostname(self) -> str:
        hostname = self.hostname
        if self.hostname.count(":") == 7:
            # IPv6 address
            hostname = f"[{hostname}]"
        return hostname

    def get_endpoint(self) -> str:
        scheme = self.get_scheme()
        port = "" if len(self.get_port()) == 0 else f":{self.port}"

        if scheme == "unix":
            separator = "://" if self.url.startswith("unix://") else ":"
            return f"{scheme}{separator}{self.hostname}"

        if scheme == "vsock":
            port = "" if self.port == 0 else f":{self.port}"
            return f"{scheme}:{self.get_hostname()}{port}"

        if scheme == "unix-abstract":
            return f"{scheme}:{self.get_hostname()}{port}"

        if scheme == "dns":
            authority = f"//{self.authority}/" if self.authority else ""
            return f"{scheme}:{authority}{self.get_hostname()}{port}"

        return f"{scheme}:{self.get_hostname()}{port}"

    def preprocess_url(self, url: str) -> str:
        url_list = url.split(":")
        if len(url_list) == 3 and "://" not in url:
            # A URI like dns:mydomain:5000 or vsock:mycid:5000 was used
            url = url.replace(":", "://", 1)
        elif len(url_list) == 2 and "://" not in url and url_list[
                0] in URIParseConfig.ACCEPTED_SCHEMES:
            # A URI like dns:mydomain was used
            url = url.replace(":", "://", 1)
        else:
            url_list = url.split("://")
            if len(url_list) == 1:
                # If a scheme was not explicitly specified in the URL
                # we need to add a default scheme,
                # because of how urlparse works
                url = f'{URIParseConfig.DEFAULT_SCHEME}://{url}'
            else:
                # If a scheme was explicitly specified in the URL
                # we need to make sure it is a valid scheme
                scheme = url_list[0]
                if scheme not in URIParseConfig.ACCEPTED_SCHEMES:
                    raise ValueError(f"Invalid scheme '{scheme}' in URL '{url}'")

                # We should do a special check if the scheme is dns, and it uses
                # an authority in the format of dns:[//authority/]host[:port]
                if scheme.lower() == "dns":
                    # A URI like dns://authority/mydomain was used
                    url_list = url.split("/")
                    if len(url_list) < 4:
                        raise ValueError(f"Invalid dns authority '{url_list[2]}' in URL '{url}'")
                    self.authority = url_list[2]
                    url = f'dns://{url_list[3]}'
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
    tls_str = query_dict.get('tls', [""])[0]
    tls = tls_str.lower() == 'true'
    if scheme == "https":
        tls = True
    return tls
