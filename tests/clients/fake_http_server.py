import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from ssl import PROTOCOL_TLS_SERVER, SSLContext
from threading import Thread

from dapr.conf import settings
from tests.clients.certs import HttpCerts

LOCALHOST = '127.0.0.1'


class DaprHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def serve_forever(self):
        while not self.running:
            self.handle_request()

    def do_request(self, verb):
        if self.path == '/v1.0/healthz/outbound':
            self.send_response(200)
            self.end_headers()
            return

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


class _TestHTTPServer(HTTPServer):
    # HTTPServer turns on SO_REUSEADDR. On Windows that lets a second socket bind a port
    # another socket is still listening on, so a new test server can end up sharing a
    # port with an abandoned one and connections land on the socket nobody serves. On
    # POSIX the flag only affects TIME_WAIT reuse, which does not matter with port 0.
    allow_reuse_address = False


class FakeHttpServer(Thread):
    secure = False

    def __init__(self, port: int = 0):
        """Bind a local HTTP server. Port 0 (the default) lets the OS pick a free port;
        read it back with get_port()."""
        super().__init__(daemon=True)

        self.server = _TestHTTPServer((LOCALHOST, port), DaprHandler)
        self.port = self.get_port()
        self._closed = False

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
        """Stop serving and close the socket. Safe to call more than once, and safe to
        call when the server thread was never started."""
        if self._closed:
            return
        self._closed = True
        try:
            # shutdown() waits for serve_forever() to return, so only call it when the
            # thread is running. If serve_forever() has not been entered yet it sees the
            # shutdown request and returns straight away.
            if self.is_alive():
                self.server.shutdown()
                self.join()
        finally:
            self.server.server_close()
            if self.secure:
                HttpCerts.delete_certificates()

    def request_path(self):
        return self.server.path

    def set_response(self, body: bytes, code=200):
        self.server.response_body = body
        self.server.response_code = code

    def get_request_body(self):
        return self.server.request_body

    def set_server_delay(self, delay_seconds):
        self.server.sleep_time = delay_seconds

    def start_secure(self):
        self.secure = True

        try:
            HttpCerts.create_certificates()
            ssl_context = SSLContext(PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(HttpCerts.get_cert_path(), HttpCerts.get_pk_path())
            self.server.socket = ssl_context.wrap_socket(self.server.socket, server_side=True)

            self.start()
        except BaseException:
            self.shutdown_server()
            raise

    def run(self):
        self.server.serve_forever()

    def reset(self):
        self.server.response_body = b''
        self.server.response_code = 200
        self.server.response_header_list = []
        self.server.request_body = b''
        self.server.sleep_time = None


def point_settings_at_http_port(cls, port: int, scheme: str = 'http') -> None:
    """Point settings.DAPR_HTTP_PORT and DAPR_HTTP_ENDPOINT at a fake server for the
    duration of a test class, restoring the previous values when the class finishes."""
    saved = (settings.DAPR_HTTP_PORT, settings.DAPR_HTTP_ENDPOINT)

    def restore() -> None:
        settings.DAPR_HTTP_PORT, settings.DAPR_HTTP_ENDPOINT = saved

    cls.addClassCleanup(restore)
    settings.DAPR_HTTP_PORT = port
    settings.DAPR_HTTP_ENDPOINT = f'{scheme}://{LOCALHOST}:{port}'
