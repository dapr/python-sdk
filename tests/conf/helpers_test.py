import unittest

from dapr.conf.helpers import parse_endpoint, parse_grpc_endpoint


class DaprClientHelpersTests(unittest.TestCase):

    def test_parse_grpc_endpoint(self):
        testcases = [
            # Port only
            # {"url": ":5000", "error": False, "secure": False, "scheme": "", "host": "localhost",
            #  "port": 5000, "endpoint": "dns:localhost:5000"},
            # {"url": ":5000?tls=false", "error": False, "secure": False, "scheme": "",
            #  "host": "localhost", "port": 5000, "endpoint": "dns:localhost:5000"},
            # {"url": ":5000?tls=true", "error": False, "secure": True, "scheme": "",
            #  "host": "localhost", "port": 5000, "endpoint": "dns:localhost:5000"},
            #
            # # Host only
            # {"url": "myhost", "error": False, "secure": False, "scheme": "", "host": "myhost",
            #  "port": 443, "endpoint": "dns:myhost:443"},
            # {"url": "myhost?tls=false", "error": False, "secure": False, "scheme": "",
            #  "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},
            # {"url": "myhost?tls=true", "error": False, "secure": True, "scheme": "",
            #  "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},
            #
            # # Host and port
            # {"url": "myhost:443", "error": False, "secure": False, "scheme": "", "host": "myhost",
            #  "port": 443, "endpoint": "dns:myhost:443"},
            # {"url": "myhost:443?tls=false", "error": False, "secure": False, "scheme": "",
            #  "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},
            # {"url": "myhost:443?tls=true", "error": False, "secure": True, "scheme": "",
            #  "host": "myhost", "port": 443, "endpoint": "dns:myhost:443"},

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

            # IPv6 addresses
            {"url": "[2001:db8:1f70::999:de8:7648:6e8]", "error": False, "secure": False, "scheme": "", "host":"[2001:db8:1f70::999:de8:7648:6e8]", "port": 443, "endpoint": "dns:[2001:db8:1f70::999:de8:7648:6e8]:443"},
            {"url": "dns:[2001:db8:1f70::999:de8:7648:6e8]", "error": False, "secure": False, "scheme": "", "host":"[2001:db8:1f70::999:de8:7648:6e8]", "port": 443, "endpoint": "dns:[2001:db8:1f70::999:de8:7648:6e8]:443"},
            {"url": "https://[2001:db8:1f70::999:de8:7648:6e8]", "error": False, "secure": True, "scheme": "", "host":"[2001:db8:1f70::999:de8:7648:6e8]", "port": 443, "endpoint": "dns:[2001:db8:1f70::999:de8:7648:6e8]:443"},

            {"url": "myhost:5000/v1/dapr", "error": True},
            # Paths are not allowed in grpc endpoints
            {"url": "myhost:5000/?a=1", "error": True},
            # Query parameters are not allowed in grpc endpoints
        ]

        print(f'URL \t endpoint\t  hostname \t port \t secure \t error')
        for testcase in testcases:
            if testcase["error"]:
                with self.assertRaises(ValueError):
                    parse_grpc_endpoint(testcase["url"])
            else:
                endpoint = parse_grpc_endpoint(testcase["url"])
                print(
                    f'{testcase["url"]}\t {endpoint.get_endpoint()} \t{endpoint.get_hostname()}\t{endpoint.get_port()}\t{endpoint.is_secure()}')
                assert testcase["endpoint"] == endpoint.get_endpoint()
                assert testcase["secure"] == endpoint.is_secure()
                assert testcase["host"] == endpoint.get_hostname()
                assert str(testcase["port"]) == endpoint.get_port()