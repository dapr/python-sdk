from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def generate_cert_pair(
    common_name: str = 'client',
    valid_for: timedelta = timedelta(days=1),
    subject_alt_names: Optional[list] = None,
) -> Tuple[bytes, bytes]:
    """Generates a self-signed PEM certificate and matching PKCS8 private key, for tests.

    Args:
        subject_alt_names: SAN entries (``x509.DNSName`` / ``x509.IPAddress``), needed for
            servers a client will connect to by hostname/IP: modern TLS stacks (aiohttp's
            included) verify against SAN only, ignoring the common name.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    cert_builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + valid_for)
    )
    if subject_alt_names:
        cert_builder = cert_builder.add_extension(
            x509.SubjectAlternativeName(subject_alt_names), critical=False
        )
    cert = cert_builder.sign(key, hashes.SHA256())
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem
