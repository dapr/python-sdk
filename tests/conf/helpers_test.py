import unittest

from dapr.conf.helpers import parse_endpoint


class DaprClientHelpersTests(unittest.TestCase):

    def test_parse_endpoint(self):
        testcases = [{"endpoint": ":5000", "scheme": "http", "host": "localhost", "port": 5000},
                     {"endpoint": ":5000/v1/dapr", "scheme": "http", "host": "localhost",
                      "port": 5000},

                     {"endpoint": "localhost", "scheme": "http", "host": "localhost", "port": 80},
                     {"endpoint": "localhost/v1/dapr", "scheme": "http", "host": "localhost",
                      "port": 80},
                     {"endpoint": "localhost:5000", "scheme": "http", "host": "localhost",
                      "port": 5000},
                     {"endpoint": "localhost:5000/v1/dapr", "scheme": "http", "host": "localhost",
                      "port": 5000},

                     {"endpoint": "http://localhost", "scheme": "http", "host": "localhost",
                      "port": 80},
                     {"endpoint": "http://localhost/v1/dapr", "scheme": "http", "host": "localhost",
                      "port": 80},
                     {"endpoint": "http://localhost:5000", "scheme": "http", "host": "localhost",
                      "port": 5000}, {"endpoint": "http://localhost:5000/v1/dapr", "scheme": "http",
                                      "host": "localhost", "port": 5000},

                     {"endpoint": "https://localhost", "scheme": "https", "host": "localhost",
                      "port": 443}, {"endpoint": "https://localhost/v1/dapr", "scheme": "https",
                                     "host": "localhost", "port": 443},
                     {"endpoint": "https://localhost:5000", "scheme": "https", "host": "localhost",
                      "port": 5000},
                     {"endpoint": "https://localhost:5000/v1/dapr", "scheme": "https",
                      "host": "localhost", "port": 5000},

                     {"endpoint": "127.0.0.1", "scheme": "http", "host": "127.0.0.1", "port": 80},
                     {"endpoint": "127.0.0.1/v1/dapr", "scheme": "http", "host": "127.0.0.1",
                      "port": 80},
                     {"endpoint": "127.0.0.1:5000", "scheme": "http", "host": "127.0.0.1",
                      "port": 5000},
                     {"endpoint": "127.0.0.1:5000/v1/dapr", "scheme": "http", "host": "127.0.0.1",
                      "port": 5000},

                     {"endpoint": "http://127.0.0.1", "scheme": "http", "host": "127.0.0.1",
                      "port": 80},
                     {"endpoint": "http://127.0.0.1/v1/dapr", "scheme": "http", "host": "127.0.0.1",
                      "port": 80},
                     {"endpoint": "http://127.0.0.1:5000", "scheme": "http", "host": "127.0.0.1",
                      "port": 5000}, {"endpoint": "http://127.0.0.1:5000/v1/dapr", "scheme": "http",
                                      "host": "127.0.0.1", "port": 5000},

                     {"endpoint": "https://127.0.0.1", "scheme": "https", "host": "127.0.0.1",
                      "port": 443}, {"endpoint": "https://127.0.0.1/v1/dapr", "scheme": "https",
                                     "host": "127.0.0.1", "port": 443},
                     {"endpoint": "https://127.0.0.1:5000", "scheme": "https", "host": "127.0.0.1",
                      "port": 5000},
                     {"endpoint": "https://127.0.0.1:5000/v1/dapr", "scheme": "https",
                      "host": "127.0.0.1", "port": 5000},

                     {"endpoint": "[2001:db8:1f70::999:de8:7648:6e8]", "scheme": "http",
                      "host": "2001:db8:1f70::999:de8:7648:6e8", "port": 80},
                     {"endpoint": "[2001:db8:1f70::999:de8:7648:6e8]/v1/dapr", "scheme": "http",
                      "host": "2001:db8:1f70::999:de8:7648:6e8", "port": 80},
                     {"endpoint": "[2001:db8:1f70::999:de8:7648:6e8]:5000", "scheme": "http",
                      "host": "2001:db8:1f70::999:de8:7648:6e8", "port": 5000},
                     {"endpoint": "[2001:db8:1f70::999:de8:7648:6e8]:5000/v1/dapr",
                      "scheme": "http", "host": "2001:db8:1f70::999:de8:7648:6e8", "port": 5000},

                     {"endpoint": "http://[2001:db8:1f70::999:de8:7648:6e8]", "scheme": "http",
                      "host": "2001:db8:1f70::999:de8:7648:6e8", "port": 80},
                     {"endpoint": "http://[2001:db8:1f70::999:de8:7648:6e8]/v1/dapr",
                      "scheme": "http", "host": "2001:db8:1f70::999:de8:7648:6e8", "port": 80},
                     {"endpoint": "http://[2001:db8:1f70::999:de8:7648:6e8]:5000", "scheme": "http",
                      "host": "2001:db8:1f70::999:de8:7648:6e8", "port": 5000},
                     {"endpoint": "http://[2001:db8:1f70::999:de8:7648:6e8]:5000/v1/dapr",
                      "scheme": "http", "host": "2001:db8:1f70::999:de8:7648:6e8", "port": 5000},

                     {"endpoint": "https://[2001:db8:1f70::999:de8:7648:6e8]", "scheme": "https",
                      "host": "2001:db8:1f70::999:de8:7648:6e8", "port": 443},
                     {"endpoint": "https://[2001:db8:1f70::999:de8:7648:6e8]/v1/dapr",
                      "scheme": "https", "host": "2001:db8:1f70::999:de8:7648:6e8", "port": 443},
                     {"endpoint": "https://[2001:db8:1f70::999:de8:7648:6e8]:5000",
                      "scheme": "https", "host": "2001:db8:1f70::999:de8:7648:6e8", "port": 5000},
                     {"endpoint": "https://[2001:db8:1f70::999:de8:7648:6e8]:5000/v1/dapr",
                      "scheme": "https", "host": "2001:db8:1f70::999:de8:7648:6e8", "port": 5000},

                     {"endpoint": "domain.com", "scheme": "http", "host": "domain.com", "port": 80},
                     {"endpoint": "domain.com/v1/grpc", "scheme": "http", "host": "domain.com",
                      "port": 80},
                     {"endpoint": "domain.com:5000", "scheme": "http", "host": "domain.com",
                      "port": 5000},
                     {"endpoint": "domain.com:5000/v1/dapr", "scheme": "http", "host": "domain.com",
                      "port": 5000},

                     {"endpoint": "http://domain.com", "scheme": "http", "host": "domain.com",
                      "port": 80}, {"endpoint": "http://domain.com/v1/dapr", "scheme": "http",
                                    "host": "domain.com", "port": 80},
                     {"endpoint": "http://domain.com:5000", "scheme": "http", "host": "domain.com",
                      "port": 5000},
                     {"endpoint": "http://domain.com:5000/v1/dapr", "scheme": "http",
                      "host": "domain.com", "port": 5000},

                     {"endpoint": "https://domain.com", "scheme": "https", "host": "domain.com",
                      "port": 443}, {"endpoint": "https://domain.com/v1/dapr", "scheme": "https",
                                     "host": "domain.com", "port": 443},
                     {"endpoint": "https://domain.com:5000", "scheme": "https",
                      "host": "domain.com", "port": 5000},
                     {"endpoint": "https://domain.com:5000/v1/dapr", "scheme": "https",
                      "host": "domain.com", "port": 5000},

                     {"endpoint": "abc.domain.com", "scheme": "http", "host": "abc.domain.com",
                      "port": 80}, {"endpoint": "abc.domain.com/v1/grpc", "scheme": "http",
                                    "host": "abc.domain.com", "port": 80},
                     {"endpoint": "abc.domain.com:5000", "scheme": "http", "host": "abc.domain.com",
                      "port": 5000}, {"endpoint": "abc.domain.com:5000/v1/dapr", "scheme": "http",
                                      "host": "abc.domain.com", "port": 5000},

                     {"endpoint": "http://abc.domain.com/v1/dapr", "scheme": "http",
                      "host": "abc.domain.com", "port": 80},
                     {"endpoint": "http://abc.domain.com/v1/dapr", "scheme": "http",
                      "host": "abc.domain.com", "port": 80},
                     {"endpoint": "http://abc.domain.com:5000/v1/dapr", "scheme": "http",
                      "host": "abc.domain.com", "port": 5000},
                     {"endpoint": "http://abc.domain.com:5000/v1/dapr/v1/dapr", "scheme": "http",
                      "host": "abc.domain.com", "port": 5000},

                     {"endpoint": "https://abc.domain.com/v1/dapr", "scheme": "https",
                      "host": "abc.domain.com", "port": 443},
                     {"endpoint": "https://abc.domain.com/v1/dapr", "scheme": "https",
                      "host": "abc.domain.com", "port": 443},
                     {"endpoint": "https://abc.domain.com:5000/v1/dapr", "scheme": "https",
                      "host": "abc.domain.com", "port": 5000},
                     {"endpoint": "https://abc.domain.com:5000/v1/dapr/v1/dapr", "scheme": "https",
                      "host": "abc.domain.com", "port": 5000},

                     ]

        for testcase in testcases:
            o = parse_endpoint(testcase["endpoint"])

            self.assertEqual(testcase["scheme"], o[0])
            self.assertEqual(testcase["host"], o[1])
            self.assertEqual(testcase["port"], o[2])
