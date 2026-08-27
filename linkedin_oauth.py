import asyncio
import html
import os
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from src.linkedin_mcp.oauth import (
    OAuthConfig,
    OAuthFlowError,
    build_authorization_url,
    complete_oauth_callback,
    generate_state,
)


DEFAULT_REDIRECT_URI = "http://localhost:8000/callback"


class OAuthCallbackServer(HTTPServer):
    oauth_complete: bool = False
    oauth_result: dict[str, Any] | None = None
    oauth_error: OAuthFlowError | None = None


class CallbackHandler(BaseHTTPRequestHandler):
    """Local-development callback handler.

    Request logging is intentionally disabled because the callback request line
    contains the short-lived LinkedIn authorization code.
    """

    config: OAuthConfig
    expected_state: str
    callback_path: str

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_html(self, status_code: int, title: str, message: str) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        page = f"""
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8">
            <title>{html.escape(title)}</title>
          </head>
          <body>
            <h1>{html.escape(title)}</h1>
            <p>{html.escape(message)}</p>
          </body>
        </html>
        """
        self.wfile.write(page.encode("utf-8"))

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != self.callback_path:
            self._send_html(404, "Not found", "Unknown OAuth callback path.")
            return

        params = urllib.parse.parse_qs(parsed.query)
        server = self.server
        if not isinstance(server, OAuthCallbackServer):
            self._send_html(500, "OAuth error", "OAuth callback server is misconfigured.")
            return

        try:
            token_data = asyncio.run(
                complete_oauth_callback(
                    self.config,
                    params,
                    self.expected_state,
                )
            )
        except OAuthFlowError as exc:
            server.oauth_error = exc
            server.oauth_complete = True
            self._send_html(400, "LinkedIn authorization failed", exc.message)
            return

        server.oauth_result = token_data
        server.oauth_complete = True
        self._send_html(
            200,
            "LinkedIn authorization successful",
            "The authorization code was exchanged successfully. You can close this window.",
        )


def load_config() -> OAuthConfig:
    client_id = os.getenv("LINKEDIN_CLIENT_ID", "").strip()
    client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI", DEFAULT_REDIRECT_URI).strip()

    config = OAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )
    config.validate()
    return config


def local_server_address(redirect_uri: str) -> tuple[str, int, str]:
    parsed = urllib.parse.urlparse(redirect_uri)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise RuntimeError(
            "linkedin_oauth.py supports only a local loopback HTTP callback. "
            "Use the application OAuth layer for production HTTPS callbacks."
        )
    if not parsed.path:
        raise RuntimeError("LINKEDIN_REDIRECT_URI must include a callback path.")

    port = parsed.port or 80
    return parsed.hostname, port, parsed.path


def main() -> None:
    config = load_config()
    host, port, callback_path = local_server_address(config.redirect_uri)
    state = generate_state()
    authorization_url = build_authorization_url(config, state)

    CallbackHandler.config = config
    CallbackHandler.expected_state = state
    CallbackHandler.callback_path = callback_path

    server = OAuthCallbackServer((host, port), CallbackHandler)

    print("LinkedIn OAuth authorization started.")
    print(f"Waiting for the registered local callback at {config.redirect_uri}")
    print("Authorization codes, OAuth state, tokens, and client secrets are not logged.")

    opened = webbrowser.open(authorization_url)
    if not opened:
        server.server_close()
        raise RuntimeError("Could not open the LinkedIn authorization page in a browser.")

    try:
        while not server.oauth_complete:
            server.handle_request()
    finally:
        server.server_close()

    if server.oauth_error is not None:
        raise RuntimeError(
            f"LinkedIn OAuth failed ({server.oauth_error.code}): "
            f"{server.oauth_error.message}"
        )

    if server.oauth_result is None:
        raise RuntimeError("LinkedIn OAuth finished without token data.")

    expires_in = server.oauth_result.get("expires_in")
    if expires_in is None:
        print("LinkedIn OAuth token exchange completed successfully.")
    else:
        print(f"LinkedIn OAuth token exchange completed successfully (expires_in={expires_in}).")
    print("Access and refresh tokens were not printed. Credential persistence is handled separately.")


if __name__ == "__main__":
    main()
