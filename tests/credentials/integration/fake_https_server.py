"""A local HTTPS server that records the headers of each request."""

import ssl
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import List


class _RecordingHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - matches BaseHTTPRequestHandler's signature
        pass

    def do_GET(self):  # noqa: N802 - http.server's naming convention
        self.server.received_headers.append(dict(self.headers))  # type: ignore[attr-defined]
        body = b'{}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FakeSecureHttpServer:
    """A real, locally bound HTTPS server."""

    def __init__(self, *, server_certificate_chain_path: str, server_private_key_path: str) -> None:
        self.received_headers: List[dict] = []

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(server_certificate_chain_path, server_private_key_path)

        self._httpd = HTTPServer(('localhost', 0), _RecordingHandler)
        self._httpd.received_headers = self.received_headers  # type: ignore[attr-defined]
        self._httpd.socket = context.wrap_socket(self._httpd.socket, server_side=True)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        host, port = self._httpd.server_address[:2]
        return f'https://{host}:{port}'

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join()
