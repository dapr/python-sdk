import os
import ssl
import grpc

from OpenSSL import crypto


class Certs:
    server_type = 'grpc'

    @classmethod
    def create_certificates(cls):
        # create a key pair
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 4096)

        # create a self-signed cert
        cert = crypto.X509()
        cert.get_subject().organizationName = 'Dapr'
        cert.get_subject().commonName = 'localhost'
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(24 * 60 * 60)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)

        if cls.server_type == 'http':
            cert.add_extensions([crypto.X509Extension(b'subjectAltName', False, b'DNS:localhost')])

        cert.sign(k, 'sha512')

        with open(cls.get_cert_path(), 'wt') as f_cert:
            f_cert.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode('utf-8'))

        with open(cls.get_pk_path(), 'wt') as f_key:
            f_key.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode('utf-8'))

    @classmethod
    def get_pk_path(cls):
        return os.path.join(os.path.dirname(__file__), '{}_private.key').format(cls.server_type)

    @classmethod
    def get_cert_path(cls):
        return os.path.join(os.path.dirname(__file__), '{}_selfsigned.pem').format(cls.server_type)

    @classmethod
    def delete_certificates(cls):
        pk = cls.get_pk_path()
        if os.path.exists(pk):
            os.remove(pk)

        cert = cls.get_cert_path()
        if os.path.exists(cert):
            os.remove(cert)


class GrpcCerts(Certs):
    server_type = 'grpc'


class HttpCerts(Certs):
    server_type = 'http'


def replacement_get_credentials_func(a):
    """
    Used temporarily, so we can trust self-signed certificates in unit tests
    until they get their own environment variable
    """
    with open(GrpcCerts.get_cert_path(), 'rb') as f:
        creds = grpc.ssl_channel_credentials(f.read())
        return creds


def replacement_get_health_context():
    """
    This method is used (overwritten) from tests
    to return context for self-signed certificates
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    return context
