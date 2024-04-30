from warnings import warn
from urllib.parse import urlparse, parse_qs, ParseResult


class URIParseConfig:
    DEFAULT_SCHEME = 'dns'
    DEFAULT_HOSTNAME = 'localhost'
    DEFAULT_PORT = 443
    DEFAULT_AUTHORITY = ''
    ACCEPTED_SCHEMES = ['dns', 'unix', 'unix-abstract', 'vsock', 'http', 'https']


class GrpcEndpoint:
    _scheme: str
    _hostname: str
    _port: int
    _tls: bool
    _authority: str
    _url: str
    _parsed_url: ParseResult  # from urllib.parse
    _endpoint: str

    def __init__(self, url: str):
        self._authority = URIParseConfig.DEFAULT_AUTHORITY
        self._url = url

        self._parsed_url = urlparse(self._preprocess_uri(url))
        self._validate_path_and_query()

        self._set_tls()
        self._set_hostname()
        self._set_scheme()
        self._set_port()
        self._set_endpoint()

    def _set_scheme(self):
        if len(self._parsed_url.scheme) == 0:
            self._scheme = URIParseConfig.DEFAULT_SCHEME
            return

        if self._parsed_url.scheme in ['http', 'https']:
            self._scheme = URIParseConfig.DEFAULT_SCHEME
            warn(
                'http and https schemes are deprecated for grpc, use myhost?tls=false or myhost?tls=true instead'
            )
            return

        if self._parsed_url.scheme not in URIParseConfig.ACCEPTED_SCHEMES:
            raise ValueError(f"invalid scheme '{self._parsed_url.scheme}' in URL '{self._url}'")

        self._scheme = self._parsed_url.scheme

    @property
    def scheme(self) -> str:
        return self._scheme

    def _set_hostname(self):
        if self._parsed_url.hostname is None:
            self._hostname = URIParseConfig.DEFAULT_HOSTNAME
            return

        if self._parsed_url.hostname.count(':') == 7:
            # IPv6 address
            self._hostname = f'[{self._parsed_url.hostname}]'
            return

        self._hostname = self._parsed_url.hostname

    @property
    def hostname(self) -> str:
        return self._hostname

    def _set_port(self):
        if self._parsed_url.scheme in ['unix', 'unix-abstract']:
            self._port = 0
            return

        if self._parsed_url.port is None:
            self._port = URIParseConfig.DEFAULT_PORT
            return

        self._port = self._parsed_url.port

    @property
    def port(self) -> str:
        if self._port == 0:
            return ''

        return str(self._port)

    @property
    def port_as_int(self) -> int:
        return self._port

    def _set_endpoint(self):
        port = '' if not self._port else f':{self.port}'

        if self._scheme == 'unix':
            separator = '://' if self._url.startswith('unix://') else ':'
            self._endpoint = f'{self._scheme}{separator}{self._hostname}'
            return

        if self._scheme == 'vsock':
            self._endpoint = f'{self._scheme}:{self._hostname}:{self.port}'
            return

        if self._scheme == 'unix-abstract':
            self._endpoint = f'{self._scheme}:{self._hostname}{port}'
            return

        if self._scheme == 'dns':
            authority = f'//{self._authority}/' if self._authority else ''
            self._endpoint = f'{self._scheme}:{authority}{self._hostname}{port}'
            return

        self._endpoint = f'{self._scheme}:{self._hostname}{port}'

    @property
    def endpoint(self) -> str:
        return self._endpoint

    # Prepares the uri string in a specific format for parsing by the urlparse function
    def _preprocess_uri(self, url: str) -> str:
        url_list = url.split(':')
        if len(url_list) == 3 and '://' not in url:
            # A URI like dns:mydomain:5000 or vsock:mycid:5000 was used
            url = url.replace(':', '://', 1)
        elif (
            len(url_list) >= 2
            and '://' not in url
            and url_list[0] in URIParseConfig.ACCEPTED_SCHEMES
        ):
            # A URI like dns:mydomain or dns:[2001:db8:1f70::999:de8:7648:6e8]:mydomain was used
            # Possibly a URI like dns:[2001:db8:1f70::999:de8:7648:6e8]:mydomain was used
            url = url.replace(':', '://', 1)
        else:
            url_list = url.split('://')
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
                    raise ValueError(f"invalid scheme '{scheme}' in URL '{url}'")

                # We should do a special check if the scheme is dns, and it uses
                # an authority in the format of dns:[//authority/]host[:port]
                if scheme.lower() == 'dns':
                    # A URI like dns://authority/mydomain was used
                    url_list = url.split('/')
                    if len(url_list) < 4:
                        raise ValueError(f"invalid dns authority '{url_list[2]}' in URL '{url}'")
                    self._authority = url_list[2]
                    url = f'dns://{url_list[3]}'
        return url

    def _set_tls(self):
        query_dict = parse_qs(self._parsed_url.query)
        tls_str = query_dict.get('tls', [''])[0]
        tls = tls_str.lower() == 'true'
        if self._parsed_url.scheme == 'https':
            tls = True

        self._tls = tls

    @property
    def tls(self) -> bool:
        return self._tls

    def _validate_path_and_query(self) -> None:
        if self._parsed_url.path:
            raise ValueError(
                f'paths are not supported for gRPC endpoints:' f" '{self._parsed_url.path}'"
            )
        if self._parsed_url.query:
            query_dict = parse_qs(self._parsed_url.query)
            if 'tls' in query_dict and self._parsed_url.scheme in ['http', 'https']:
                raise ValueError(
                    f'the tls query parameter is not supported for http(s) endpoints: '
                    f"'{self._parsed_url.query}'"
                )
            query_dict.pop('tls', None)
            if query_dict:
                raise ValueError(
                    f'query parameters are not supported for gRPC endpoints:'
                    f" '{self._parsed_url.query}'"
                )
