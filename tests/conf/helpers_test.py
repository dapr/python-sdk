import unittest

from dapr.conf.helpers import GrpcEndpoint


class DaprClientHelpersTests(unittest.TestCase):
    def test_parse_grpc_endpoint(self):
        testcases = [
            # Port only
            {
                'url': ':5000',
                'error': False,
                'secure': False,
                'scheme': '',
                'host': 'localhost',
                'port': 5000,
                'endpoint': 'dns:localhost:5000',
            },
            {
                'url': ':5000?tls=false',
                'error': False,
                'secure': False,
                'scheme': '',
                'host': 'localhost',
                'port': 5000,
                'endpoint': 'dns:localhost:5000',
            },
            {
                'url': ':5000?tls=true',
                'error': False,
                'secure': True,
                'scheme': '',
                'host': 'localhost',
                'port': 5000,
                'endpoint': 'dns:localhost:5000',
            },
            # Host only
            {
                'url': 'myhost',
                'error': False,
                'secure': False,
                'scheme': '',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns:myhost:443',
            },
            {
                'url': 'myhost?tls=false',
                'error': False,
                'secure': False,
                'scheme': '',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns:myhost:443',
            },
            {
                'url': 'myhost?tls=true',
                'error': False,
                'secure': True,
                'scheme': '',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns:myhost:443',
            },
            # Host and port
            {
                'url': 'myhost:443',
                'error': False,
                'secure': False,
                'scheme': '',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns:myhost:443',
            },
            {
                'url': 'myhost:443?tls=false',
                'error': False,
                'secure': False,
                'scheme': '',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns:myhost:443',
            },
            {
                'url': 'myhost:443?tls=true',
                'error': False,
                'secure': True,
                'scheme': '',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns:myhost:443',
            },
            # Scheme, host and port
            {
                'url': 'http://myhost',
                'error': False,
                'secure': False,
                'scheme': '',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns:myhost:443',
            },
            {'url': 'http://myhost?tls=false', 'error': True},
            # We can't have both http/https and the tls query parameter
            {'url': 'http://myhost?tls=true', 'error': True},
            # We can't have both http/https and the tls query parameter
            {
                'url': 'http://myhost:443',
                'error': False,
                'secure': False,
                'scheme': '',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns:myhost:443',
            },
            {'url': 'http://myhost:443?tls=false', 'error': True},
            # We can't have both http/https and the tls query parameter
            {'url': 'http://myhost:443?tls=true', 'error': True},
            # We can't have both http/https and the tls query parameter
            {
                'url': 'http://myhost:5000',
                'error': False,
                'secure': False,
                'scheme': '',
                'host': 'myhost',
                'port': 5000,
                'endpoint': 'dns:myhost:5000',
            },
            {'url': 'http://myhost:5000?tls=false', 'error': True},
            # We can't have both http/https and the tls query parameter
            {'url': 'http://myhost:5000?tls=true', 'error': True},
            # We can't have both http/https and the tls query parameter
            {
                'url': 'https://myhost:443',
                'error': False,
                'secure': True,
                'scheme': '',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns:myhost:443',
            },
            {'url': 'https://myhost:443?tls=false', 'error': True},
            {'url': 'https://myhost:443?tls=true', 'error': True},
            # Scheme = dns
            {
                'url': 'dns:myhost',
                'error': False,
                'secure': False,
                'scheme': 'dns',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns:myhost:443',
            },
            {
                'url': 'dns:myhost?tls=false',
                'error': False,
                'secure': False,
                'scheme': 'dns',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns:myhost:443',
            },
            {
                'url': 'dns:myhost?tls=true',
                'error': False,
                'secure': True,
                'scheme': 'dns',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns:myhost:443',
            },
            # Scheme = dns with authority
            {
                'url': 'dns://myauthority:53/myhost',
                'error': False,
                'secure': False,
                'scheme': 'dns',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns://myauthority:53/myhost:443',
            },
            {
                'url': 'dns://myauthority:53/myhost?tls=false',
                'error': False,
                'secure': False,
                'scheme': 'dns',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns://myauthority:53/myhost:443',
            },
            {
                'url': 'dns://myauthority:53/myhost?tls=true',
                'error': False,
                'secure': True,
                'scheme': 'dns',
                'host': 'myhost',
                'port': 443,
                'endpoint': 'dns://myauthority:53/myhost:443',
            },
            {'url': 'dns://myhost', 'error': True},
            # Unix sockets
            {
                'url': 'unix:my.sock',
                'error': False,
                'secure': False,
                'scheme': 'unix',
                'host': 'my.sock',
                'port': '',
                'endpoint': 'unix:my.sock',
            },
            {
                'url': 'unix:my.sock?tls=true',
                'error': False,
                'secure': True,
                'scheme': 'unix',
                'host': 'my.sock',
                'port': '',
                'endpoint': 'unix:my.sock',
            },
            # Unix sockets with absolute path
            {
                'url': 'unix://my.sock',
                'error': False,
                'secure': False,
                'scheme': 'unix',
                'host': 'my.sock',
                'port': '',
                'endpoint': 'unix://my.sock',
            },
            {
                'url': 'unix://my.sock?tls=true',
                'error': False,
                'secure': True,
                'scheme': 'unix',
                'host': 'my.sock',
                'port': '',
                'endpoint': 'unix://my.sock',
            },
            # Unix abstract sockets
            {
                'url': 'unix-abstract:my.sock',
                'error': False,
                'secure': False,
                'scheme': 'unix',
                'host': 'my.sock',
                'port': '',
                'endpoint': 'unix-abstract:my.sock',
            },
            {
                'url': 'unix-abstract:my.sock?tls=true',
                'error': False,
                'secure': True,
                'scheme': 'unix',
                'host': 'my.sock',
                'port': '',
                'endpoint': 'unix-abstract:my.sock',
            },
            # Vsock
            {
                'url': 'vsock:mycid',
                'error': False,
                'secure': False,
                'scheme': 'vsock',
                'host': 'mycid',
                'port': '443',
                'endpoint': 'vsock:mycid:443',
            },
            {
                'url': 'vsock:mycid:5000',
                'error': False,
                'secure': False,
                'scheme': 'vsock',
                'host': 'mycid',
                'port': 5000,
                'endpoint': 'vsock:mycid:5000',
            },
            {
                'url': 'vsock:mycid:5000?tls=true',
                'error': False,
                'secure': True,
                'scheme': 'vsock',
                'host': 'mycid',
                'port': 5000,
                'endpoint': 'vsock:mycid:5000',
            },
            # IPv6 addresses with dns scheme
            {
                'url': '[2001:db8:1f70::999:de8:7648:6e8]',
                'error': False,
                'secure': False,
                'scheme': '',
                'host': '[2001:db8:1f70::999:de8:7648:6e8]',
                'port': 443,
                'endpoint': 'dns:[2001:db8:1f70::999:de8:7648:6e8]:443',
            },
            {
                'url': 'dns:[2001:db8:1f70::999:de8:7648:6e8]',
                'error': False,
                'secure': False,
                'scheme': '',
                'host': '[2001:db8:1f70::999:de8:7648:6e8]',
                'port': 443,
                'endpoint': 'dns:[2001:db8:1f70::999:de8:7648:6e8]:443',
            },
            {
                'url': 'dns:[2001:db8:1f70::999:de8:7648:6e8]:5000',
                'error': False,
                'secure': False,
                'scheme': '',
                'host': '[2001:db8:1f70::999:de8:7648:6e8]',
                'port': 5000,
                'endpoint': 'dns:[2001:db8:1f70::999:de8:7648:6e8]:5000',
            },
            {'url': 'dns:[2001:db8:1f70::999:de8:7648:6e8]:5000?abc=[]', 'error': True},
            # IPv6 addresses with dns scheme and authority
            {
                'url': 'dns://myauthority:53/[2001:db8:1f70::999:de8:7648:6e8]',
                'error': False,
                'secure': False,
                'scheme': 'dns',
                'host': '[2001:db8:1f70::999:de8:7648:6e8]',
                'port': 443,
                'endpoint': 'dns://myauthority:53/[2001:db8:1f70::999:de8:7648:6e8]:443',
            },
            # IPv6 addresses with https scheme
            {
                'url': 'https://[2001:db8:1f70::999:de8:7648:6e8]',
                'error': False,
                'secure': True,
                'scheme': '',
                'host': '[2001:db8:1f70::999:de8:7648:6e8]',
                'port': 443,
                'endpoint': 'dns:[2001:db8:1f70::999:de8:7648:6e8]:443',
            },
            {
                'url': 'https://[2001:db8:1f70::999:de8:7648:6e8]:5000',
                'error': False,
                'secure': True,
                'scheme': '',
                'host': '[2001:db8:1f70::999:de8:7648:6e8]',
                'port': 5000,
                'endpoint': 'dns:[2001:db8:1f70::999:de8:7648:6e8]:5000',
            },
            # Invalid addresses (with path and queries)
            {'url': 'host:5000/v1/dapr', 'error': True},  # Paths are not allowed in grpc endpoints
            {'url': 'host:5000/?a=1', 'error': True},  # Query params not allowed in grpc endpoints
            # Invalid scheme
            {'url': 'inv-scheme://myhost', 'error': True},
            {'url': 'inv-scheme:myhost:5000', 'error': True},
        ]

        for testcase in testcases:
            if testcase['error']:
                with self.assertRaises(ValueError):
                    GrpcEndpoint(testcase['url'])
            else:
                url = GrpcEndpoint(testcase['url'])
                assert url.endpoint == testcase['endpoint']
                assert url.tls == testcase['secure']
                assert url.hostname == testcase['host']
                assert url.port == str(testcase['port'])
