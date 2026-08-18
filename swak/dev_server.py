"""
SWAK — Local Development Server
Excel Add-in requires HTTPS — این سرور certificate موقت می‌سازد

نصب: pip install cryptography
اجرا: python dev_server.py
"""

import http.server
import ssl
import os
import sys
import socket
import threading
import subprocess
from pathlib import Path

HOST = 'localhost'
PORT = 3000
TASKPANE_DIR = Path(__file__).parent / 'taskpane'


def generate_ssl_cert():
    """Generate self-signed SSL certificate for localhost"""
    cert_file = Path('dev_cert.pem')
    key_file  = Path('dev_key.pem')

    if cert_file.exists() and key_file.exists():
        print('[Dev] Using existing SSL certificate')
        return str(cert_file), str(key_file)

    print('[Dev] Generating self-signed SSL certificate...')
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend
        import datetime, ipaddress

        # Generate key
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        # Generate cert
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, 'localhost'),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'SWAK Dev'),
        ])

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName('localhost'),
                    x509.IPAddress(ipaddress.IPv4Address('127.0.0.1')),
                ]),
                critical=False,
            )
            .sign(key, hashes.SHA256(), default_backend())
        )

        # Write files
        cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_file.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()
        ))

        print('[Dev] SSL certificate generated ✓')
        return str(cert_file), str(key_file)

    except ImportError:
        print('[Dev] cryptography not installed.')
        print('      Run: pip install cryptography')
        print('[Dev] Falling back to HTTP (Excel may not load add-in)')
        return None, None


class SWAKHandler(http.server.SimpleHTTPRequestHandler):
    """Serve taskpane files with correct headers for Excel Add-in"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(TASKPANE_DIR), **kwargs)

    def end_headers(self):
        # Required headers for Office Add-in
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        # Map HTML file
        super().end_headers()

    def do_GET(self):
        # Map /taskpane.html → ui_preview_v2.0.0.html
        if self.path == '/' or self.path == '/taskpane.html':
            self.path = '/ui_preview_v2.0.0.html'
        super().do_GET()

    def log_message(self, format, *args):
        # Clean log output
        print(f'  [Dev Server] {args[0]} {args[1]}')


def start_flask_check():
    """Check if Flask backend is running, offer to start it"""
    import urllib.request
    try:
        urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2)
        print('[Dev] Flask backend: ✓ running on :5000')
    except Exception:
        print('[Dev] Flask backend: ✗ not running')
        print('[Dev] Starting Flask backend...')
        # Start Flask in background
        flask_script = Path(__file__).parent / 'server' / 'start.py'
        if flask_script.exists():
            subprocess.Popen(
                [sys.executable, str(flask_script)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print('[Dev] Flask backend started on :5000')
        else:
            print('[Dev] Run manually: python server/start.py')


def main():
    print('=' * 52)
    print('  SWAK Dev Server')
    print(f'  Taskpane: https://{HOST}:{PORT}/taskpane.html')
    print(f'  Backend:  http://127.0.0.1:5000')
    print('=' * 52)

    # Check/start Flask backend
    start_flask_check()

    # Generate SSL certificate
    cert_file, key_file = generate_ssl_cert()

    # Start HTTPS server
    server = http.server.HTTPServer((HOST, PORT), SWAKHandler)

    if cert_file and key_file:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_file, key_file)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        protocol = 'https'
    else:
        protocol = 'http'

    print(f'\n[Dev] Serving on {protocol}://{HOST}:{PORT}')
    print(f'[Dev] Taskpane URL: {protocol}://{HOST}:{PORT}/taskpane.html')
    print('[Dev] Press Ctrl+C to stop\n')

    # Open browser for certificate trust (first time)
    if cert_file:
        print('[Dev] IMPORTANT: First time setup:')
        print(f'      1. Open {protocol}://{HOST}:{PORT}/taskpane.html in browser')
        print('      2. Click "Advanced" → "Proceed to localhost"')
        print('      3. This trusts the certificate for Excel\n')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[Dev] Stopped')


if __name__ == '__main__':
    main()
