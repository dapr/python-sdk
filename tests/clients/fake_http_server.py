import time

from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer


class DaprHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def serve_forever(self):
        while not self.running:
            self.handle_request()

    def do_request(self, verb):
        if self.server.sleep_time is not None:
            time.sleep(self.server.sleep_time)
        self.received_verb = verb
        self.server.request_headers = self.headers
        if 'Content-Length' in self.headers:
            content_length = int(self.headers['Content-Length'])

            self.server.request_body += self.rfile.read(content_length)

        self.send_response(self.server.response_code)
        for key, value in self.server.response_header_list:
            self.send_header(key, value)
        self.send_header('Content-Length', str(len(self.server.response_body)))
        self.end_headers()

        self.server.path = self.path

        self.wfile.write(self.server.response_body)

    def do_GET(self):
        self.do_request('GET')

    def do_POST(self):
        self.do_request('POST')

    def do_PUT(self):
        self.do_request('PUT')

    def do_DELETE(self):
        self.do_request('DELETE')


class FakeHttpServer(Thread):
    def __init__(self):
        super().__init__()
        self.server = HTTPServer(('localhost', 0), DaprHandler)
        self.server.response_body = b''
        self.server.response_code = 200
        self.server.response_header_list = []
        self.server.request_body = b''
        self.server.sleep_time = None

    def get_port(self):
        return self.server.socket.getsockname()[1]

    def reply_header(self, key, value):
        self.server.response_header_list.append((key, value))

    def get_request_headers(self):
        return self.server.request_headers

    def shutdown_server(self):
        self.server.shutdown()
        self.server.socket.close()
        self.join()

    def request_path(self):
        return self.server.path

    def set_response(self, body: bytes, code=200):
        self.server.response_body = body
        self.server.response_code = code

    def get_request_body(self):
        return self.server.request_body

    def set_server_delay(self, delay_seconds):
        self.server.sleep_time = delay_seconds

    def run(self):
        self.server.serve_forever()
