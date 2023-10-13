import unittest

from dapr.conf.helpers import parse_grpc_endpoint


class DaprClientHelpersTests(unittest.TestCase):

    def test_parse_grpc_endpoint(self):
        testcases = [
            # Port only
            {"url": ":5000", "error": False, "secure": False, "scheme": "", "host": "localhost",
             "port": 5000, "endpoint": "dns:localhost:5000"},
            {"url": ":5000?tls=false", "error": False, "secure": False, "scheme": "",
             "host": "localhost", "port": 5000, "endpoint": "dns:localhost:5000"},
            {"url": ":5000?tls=true", "error": False, "secure": True, "scheme": "",
             "host": "localhost", "port": 5000, "endpoint": "dns:localhost:5000"},

            # Host only
            {"url": "myhost", "error": False, "secure": False, "scheme": "", "host": "myhost",
             "port": 443, "endpoint": "dns:myhost:443"},
            {"url": "myhost?tls=false", "error": False, "secure": False, "scheme": "",
             "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},
            {"url": "myhost?tls=true", "error": False, "secure": True, "scheme": "",
             "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},

            # Host and port
            {"url": "myhost:443", "error": False, "secure": False, "scheme": "", "host": "myhost",
             "port": 443, "endpoint": "dns:myhost:443"},
            {"url": "myhost:443?tls=false", "error": False, "secure": False, "scheme": "",
             "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},
            {"url": "myhost:443?tls=true", "error": False, "secure": True, "scheme": "",
             "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},

            # Scheme, host and port
            {"url": "http://myhost", "error": False, "secure": False, "scheme": "",
             "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},
            {"url": "http://myhost?tls=false", "error": True},
            # We can't have both http/https and the tls query parameter
            {"url": "http://myhost?tls=true", "error": True},
            # We can't have both http/https and the tls query parameter

            {"url": "http://myhost:443", "error": False, "secure": False, "scheme": "",
             "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},
            {"url": "http://myhost:443?tls=false", "error": True},
            # We can't have both http/https and the tls query parameter
            {"url": "http://myhost:443?tls=true", "error": True},
            # We can't have both http/https and the tls query parameter

            {"url": "http://myhost:5000", "error": False, "secure": False, "scheme": "",
             "host": "myhost", "port": 5000, "endpoint": "dns:myhost:5000"},
            {"url": "http://myhost:5000?tls=false", "error": True},
            # We can't have both http/https and the tls query parameter
            {"url": "http://myhost:5000?tls=true", "error": True},
            # We can't have both http/https and the tls query parameter

            {"url": "https://myhost:443", "error": False, "secure": True, "scheme": "",
             "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},
            {"url": "https://myhost:443?tls=false", "error": True},
            {"url": "https://myhost:443?tls=true", "error": True},

            # Scheme = dns
            {"url": "dns:myhost", "error": False, "secure": False, "scheme": "dns",
             "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},
            {"url": "dns:myhost?tls=false", "error": False, "secure": False, "scheme": "dns",
             "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},
            {"url": "dns:myhost?tls=true", "error": False, "secure": True, "scheme": "dns",
             "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},

            {"url": "dns://myhost", "error": False, "secure": False, "scheme": "dns",
             "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},
            {"url": "dns://myhost?tls=false", "error": False, "secure": False, "scheme": "dns",
             "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},
            {"url": "dns://myhost?tls=true", "error": False, "secure": True, "scheme": "dns",
             "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},

            # Unix sockets
            {"url": "unix://my.sock", "error": False, "secure": False, "scheme": "unix",
             "host": "my.sock", "port": "", "endpoint": "unix://my.sock"},
            {"url": "unix://my.sock?tls=true", "error": False, "secure": True, "scheme": "unix",
             "host": "my.sock", "port": "", "endpoint": "unix://my.sock"},


            # IPv6 addresses
            {"url": "[2001:db8:1f70::999:de8:7648:6e8]", "error": False, "secure": False, "scheme": "", "host":"[2001:db8:1f70::999:de8:7648:6e8]", "port": 443, "endpoint": "dns:[2001:db8:1f70::999:de8:7648:6e8]:443"},
            {"url": "dns:[2001:db8:1f70::999:de8:7648:6e8]", "error": False, "secure": False, "scheme": "", "host":"[2001:db8:1f70::999:de8:7648:6e8]", "port": 443, "endpoint": "dns:[2001:db8:1f70::999:de8:7648:6e8]:443"},
            {"url": "https://[2001:db8:1f70::999:de8:7648:6e8]", "error": False, "secure": True, "scheme": "", "host":"[2001:db8:1f70::999:de8:7648:6e8]", "port": 443, "endpoint": "dns:[2001:db8:1f70::999:de8:7648:6e8]:443"},

            # Invalid addresses (with path and queries)
            {"url": "host:5000/v1/dapr", "error": True},  # Paths are not allowed in grpc endpoints
            {"url": "host:5000/?a=1", "error": True},  # Query params not allowed in grpc endpoints
        ]

        for testcase in testcases:
            try:
                endpoint = parse_grpc_endpoint(testcase["url"])
                print(f'{testcase["url"]}\t {endpoint.get_endpoint()} \t{endpoint.get_hostname()}\t{endpoint.get_port()}\t{endpoint.is_secure()}')
                assert endpoint.get_endpoint() == testcase["endpoint"]
                assert endpoint.is_secure() == testcase["secure"]
                assert endpoint.get_hostname() == testcase["host"]
                assert endpoint.get_port() == str(testcase["port"])
            except ValueError as error:
                print(f'{testcase["url"]}\t {error}')

            if testcase["error"]:
                with self.assertRaises(ValueError):
                    parse_grpc_endpoint(testcase["url"])
            else:
                endpoint = parse_grpc_endpoint(testcase["url"])
                print(
                    f'{testcase["url"]}\t {endpoint.get_endpoint()} \t{endpoint.get_hostname()}\t{endpoint.get_port()}\t{endpoint.is_secure()}')
                assert endpoint.get_endpoint() == testcase["endpoint"]
                assert endpoint.is_secure() == testcase["secure"]
                assert endpoint.get_hostname() == testcase["host"]
                assert endpoint.get_port() == str(testcase["port"])