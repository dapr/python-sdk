import os
import ssl

from OpenSSL import crypto

import grpc

PRIVATE_KEY_PATH = os.path.join(os.path.dirname(__file__), 'private.key')
CERTIFICATE_CHAIN_PATH = os.path.join(os.path.dirname(__file__), 'selfsigned.pem')


def create_certificates(server_type='grpc'):
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

    if server_type == 'http':
        cert.add_extensions([crypto.X509Extension(b'subjectAltName', False, b'DNS:localhost')])

    cert.sign(k, 'sha512')

    f_cert = open(CERTIFICATE_CHAIN_PATH, 'wt')
    f_cert.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode('utf-8'))
    f_cert.close()

    f_key = open(PRIVATE_KEY_PATH, 'wt')
    f_key.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode('utf-8'))
    f_key.close()


def delete_certificates():
    if os.path.exists(PRIVATE_KEY_PATH):
        os.remove(PRIVATE_KEY_PATH)

    if os.path.exists(CERTIFICATE_CHAIN_PATH):
        os.remove(CERTIFICATE_CHAIN_PATH)


def replacement_get_credentials_func(a):
    """
    Used temporarily, so we can trust self-signed certificates in unit tests
    until they get their own environment variable
    """
    f = open(os.path.join(os.path.dirname(__file__), 'selfsigned.pem'), 'rb')
    creds = grpc.ssl_channel_credentials(f.read())
    f.close()

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
