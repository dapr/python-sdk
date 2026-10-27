import unittest
import warnings

from dapr.conf.helpers import GrpcEndpoint


class DaprClientHelpersTests(unittest.TestCase):
    def test_http_scheme_deprecation_keeps_endpoint_and_points_to_caller(self):
        for scheme, port, secure in [('http', 80, False), ('https', 443, True)]:
            with self.subTest(scheme=scheme):
                with self.assertWarns(DeprecationWarning) as warning:
                    endpoint = GrpcEndpoint(f'{scheme}://host:{port}')
                self.assertIn('helpers_test.py', warning.filename)
                self.assertIn(f'host:{port}?tls={str(secure).lower()}', str(warning.warning))
                self.assertEqual(endpoint.hostname, 'host')
                self.assertEqual(endpoint.port_as_int, port)
                self.assertEqual(endpoint.tls, secure)
                self.assertEqual(endpoint.endpoint, f'dns:host:{port}')

        with self.assertRaises(ValueError):
            GrpcEndpoint('https://host:443?tls=false')

    def test_http_scheme_emits_only_a_deprecation_warning(self):
        for scheme, port in [('http', 80), ('https', 443)]:
            with self.subTest(scheme=scheme):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    GrpcEndpoint(f'{scheme}://host:{port}')
                self.assertEqual([warning.category for warning in caught], [DeprecationWarning])

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
            # gRPC needs an absolute path after unix://, so an authority can never connect
            {'url': 'unix://my.sock', 'error': True},
            {'url': 'unix://my.sock?tls=true', 'error': True},
            {'url': 'unix://relative/dir/x.sock', 'error': True},
            # Relative socket names keep their case
            {
                'url': 'unix:My.sock',
                'error': False,
                'secure': False,
                'scheme': 'unix',
                'host': 'My.sock',
                'port': '',
                'endpoint': 'unix:My.sock',
            },
            {
                'url': 'unix:run/My.sock',
                'error': False,
                'secure': False,
                'scheme': 'unix',
                'host': 'run/My.sock',
                'port': '',
                'endpoint': 'unix:run/My.sock',
            },
            # Unix sockets with a filesystem path, which urlparse puts in the path component
            {
                'url': 'unix:///tmp/dapr.sock',
                'error': False,
                'secure': False,
                'scheme': 'unix',
                'host': '/tmp/dapr.sock',
                'port': '',
                'endpoint': 'unix:///tmp/dapr.sock',
            },
            {
                'url': 'unix:///tmp/dapr.sock?tls=true',
                'error': False,
                'secure': True,
                'scheme': 'unix',
                'host': '/tmp/dapr.sock',
                'port': '',
                'endpoint': 'unix:///tmp/dapr.sock',
            },
            {
                'url': 'unix:/tmp/dapr.sock',
                'error': False,
                'secure': False,
                'scheme': 'unix',
                'host': '/tmp/dapr.sock',
                'port': '',
                'endpoint': 'unix:/tmp/dapr.sock',
            },
            {
                'url': 'unix:///private/tmp/dapr-sockets/Dapr-MyApp-grpc.socket',
                'error': False,
                'secure': False,
                'scheme': 'unix',
                'host': '/private/tmp/dapr-sockets/Dapr-MyApp-grpc.socket',
                'port': '',
                'endpoint': 'unix:///private/tmp/dapr-sockets/Dapr-MyApp-grpc.socket',
            },
            {'url': 'unix:///tmp/dapr.sock?abc=1', 'error': True},
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
