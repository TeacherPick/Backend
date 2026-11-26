import os
import queue
import re
import socketserver
import ssl
import threading
from email import policy
from email.parser import BytesParser

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import PASSWORD


class MailHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b"220 localhost ESMTP\r\n")
        for line in self.rfile:
            command = line.split(maxsplit=1)[0].upper()
            if command == b"DATA":
                self.wfile.write(b"354 Send mail\r\n")
                chunks = []
                for chunk in self.rfile:
                    if chunk == b".\r\n":
                        break
                    chunks.append(chunk[1:] if chunk.startswith(b"..") else chunk)
                self.server.inbox.put(b"".join(chunks))
            elif command == b"QUIT":
                self.wfile.write(b"221 Bye\r\n")
                return
            self.wfile.write(b"250 OK\r\n")


def test_password_reset_delivers_through_tls_smtp(mysql_settings, user, monkeypatch):
    certificate = os.environ.get("TEACHERPICK_SMTP_TEST_CERT")
    private_key = os.environ.get("TEACHERPICK_SMTP_TEST_KEY")
    if not certificate or not private_key:
        pytest.skip("Provide a local SMTP test certificate and its private key.")

    monkeypatch.setenv("SSL_CERT_FILE", certificate)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(certificate, private_key)
    with socketserver.TCPServer(("127.0.0.1", 0), MailHandler) as mail:
        mail.socket = tls.wrap_socket(mail.socket, server_side=True)
        mail.inbox = queue.Queue()
        server = threading.Thread(target=mail.serve_forever, daemon=True)
        server.start()
        try:
            account, headers = user()
            settings = mysql_settings.model_copy(update={
                "smtp_host": "127.0.0.1", "smtp_port": mail.server_address[1], "smtp_security": "implicit",
                "smtp_username": None, "smtp_sender": "teacherpick@example.com",
            })
            with TestClient(create_app(settings)) as client:
                endpoint = "/api/v1/auth/password-reset"
                email = account["email"]
                assert client.post(f"{endpoint}/request", json={"email": email}).status_code == 202
                message = BytesParser(policy=policy.default).parsebytes(mail.inbox.get(timeout=3))
                assert message["To"] == email
                code = re.search(r"(?<![0-9])[0-9]{6}(?![0-9])", message.get_content()).group()
                verified = client.post(f"{endpoint}/verify", json={"email": email, "code": code})
                assert verified.status_code == 200
                new_password = "new " + PASSWORD
                reset = client.post(f"{endpoint}/confirm", json={
                    "email": email, "ticket": verified.json()["ticket"], "password": new_password,
                    "password_confirmation": new_password,
                })
                assert reset.status_code == 204
                assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
                assert client.post("/api/v1/auth/login", json={
                    "username": account["username"], "password": new_password,
                }).status_code == 200
        finally:
            mail.shutdown()
            server.join()
