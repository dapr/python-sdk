import os

from OpenSSL import crypto

PRIVATE_KEY_PATH = os.path.join(os.path.dirname(__file__), 'private.key')
CERTIFICATE_CHAIN_PATH = os.path.join(os.path.dirname(__file__), 'selfsigned.pem')


def create_certificates():
    # create a key pair
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)

    # create a self-signed cert
    cert = crypto.X509()
    cert.get_subject().organizationName = "Dapr"
    cert.get_subject().commonName = "localhost"
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(24 * 60 * 60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha512')

    f_cert = open(CERTIFICATE_CHAIN_PATH, "wt")
    f_cert.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))
    f_cert.close()

    f_key = open(PRIVATE_KEY_PATH, "wt")
    f_key.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))
    f_key.close()


def delete_certificates():
    if os.path.exists(PRIVATE_KEY_PATH):
        os.remove(PRIVATE_KEY_PATH)

    if os.path.exists(CERTIFICATE_CHAIN_PATH):
        os.remove(CERTIFICATE_CHAIN_PATH)
