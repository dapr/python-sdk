import os
import ssl
from datetime import datetime, timedelta, timezone

import grpc
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


class Certs:
    server_type = 'grpc'

    @classmethod
    def create_certificates(cls):
        key = rsa.generate_private_key(public_exponent=65537, key_size=4096)

        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Dapr'),
                x509.NameAttribute(NameOID.COMMON_NAME, 'localhost'),
            ]
        )
        now = datetime.now(timezone.utc)
        cert_builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=1))
        )

        if cls.server_type == 'http':
            localhost_san = x509.SubjectAlternativeName([x509.DNSName('localhost')])
            cert_builder = cert_builder.add_extension(localhost_san, critical=False)

        cert = cert_builder.sign(key, hashes.SHA512())

        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        with open(cls.get_cert_path(), 'wb') as f_cert:
            f_cert.write(cert_pem)

        with open(cls.get_pk_path(), 'wb') as f_key:
            f_key.write(key_pem)

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
