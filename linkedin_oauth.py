import os
import secrets
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

CLIENT_ID = os.environ["LINKEDIN_CLIENT_ID"]

REDIRECT_URI = "http://localhost:8000/callback"

SCOPE = "w_member_social"

STATE = secrets.token_urlsafe(32)


class CallbackHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        parsed = urllib.parse.urlparse(self.path)

        print("\n" + "=" * 60)
        print("CALLBACK RECEIVED")
        print("=" * 60)
        print("Path:", self.path)
        print("Query:", parsed.query)

        # فقط /callback را قبول می‌کنیم
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        # پارامترهای URL
        params = urllib.parse.parse_qs(parsed.query)

        print("Params:", params)

        print("=" * 60)

        # -------------------------------------------------
        # LinkedIn Error
        # -------------------------------------------------

        if "error" in params:

            error = params.get(
                "error",
                ["unknown"]
            )[0]

            description = params.get(
                "error_description",
                [""]
            )[0]

            print("\nLINKEDIN ERROR")
            print("Error:", error)
            print("Description:", description)

            self.send_response(400)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )
            self.end_headers()

            html = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <title>LinkedIn OAuth Error</title>
            </head>
            <body>
                <h2>LinkedIn Authorization Failed</h2>
                <p><strong>Error:</strong> {error}</p>
                <p><strong>Description:</strong> {description}</p>
            </body>
            </html>
            """

            self.wfile.write(html.encode("utf-8"))

            return

        # -------------------------------------------------
        # State validation
        # -------------------------------------------------

        received_state = params.get(
            "state",
            [None]
        )[0]

        print("\nSTATE CHECK")
        print("Expected:", STATE)
        print("Received:", received_state)

        if received_state != STATE:

            print("\nERROR: INVALID STATE")

            self.send_response(400)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )
            self.end_headers()

            html = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <title>Invalid State</title>
            </head>
            <body>
                <h2>Invalid OAuth State</h2>
                <p>The OAuth state returned by LinkedIn does not match.</p>

                <p>
                    This usually means the callback URL was opened
                    manually or an old OAuth request was used.
                </p>

                <p>Please close this window and start the script again.</p>
            </body>
            </html>
            """

            self.wfile.write(html.encode("utf-8"))

            return

        # -------------------------------------------------
        # Authorization Code
        # -------------------------------------------------

        code = params.get(
            "code",
            [None]
        )[0]

        if not code:

            print("\nERROR: NO AUTHORIZATION CODE")

            self.send_response(400)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )
            self.end_headers()

            self.wfile.write(
                b"""
                <html>
                <body>
                    <h2>No authorization code received.</h2>
                </body>
                </html>
                """
            )

            return

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        print("\n" + "=" * 60)
        print("SUCCESS")
        print("=" * 60)

        print("Authorization code received successfully.")

        # برای امنیت، Code را کامل چاپ نمی‌کنیم
        print(
            "Code:",
            code[:10] + "..." if len(code) > 10 else "***"
        )

        print("=" * 60)

        # -------------------------------------------------
        # Browser response
        # -------------------------------------------------

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8"
        )

        self.end_headers()

        html = """
        <!DOCTYPE html>

        <html>
        <head>
            <meta charset="utf-8">

            <title>
                LinkedIn OAuth
            </title>
        </head>

        <body>

            <h1>
                LinkedIn Authorization Successful
            </h1>

            <p>
                Authorization code received successfully.
            </p>

            <p>
                You can close this browser window
                and return to the terminal.
            </p>

        </body>

        </html>
        """

        self.wfile.write(
            html.encode("utf-8")
        )

        # سرور را متوقف می‌کنیم
        raise SystemExit


def main():

    # -------------------------------------------------
    # Check Client ID
    # -------------------------------------------------

    if not CLIENT_ID:

        raise RuntimeError(
            "LINKEDIN_CLIENT_ID is not set."
        )

    # -------------------------------------------------
    # OAuth parameters
    # -------------------------------------------------

    params = {

        "response_type": "code",

        "client_id": CLIENT_ID,

        "redirect_uri": REDIRECT_URI,

        "state": STATE,

        "scope": SCOPE,
    }

    # -------------------------------------------------
    # Build authorization URL
    # -------------------------------------------------

    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        + urllib.parse.urlencode(params)
    )

    print("\n")
    print("=" * 60)
    print("LINKEDIN OAUTH")
    print("=" * 60)

    print("\nClient ID:")
    print(CLIENT_ID)

    print("\nRedirect URI:")
    print(REDIRECT_URI)

    print("\nScope:")
    print(SCOPE)

    print("\nState:")
    print(STATE)

    print("\nAuthorization URL:")
    print(auth_url)

    print("\nOpening LinkedIn browser...")

    # -------------------------------------------------
    # Open browser
    # -------------------------------------------------

    webbrowser.open(auth_url)

    # -------------------------------------------------
    # Start callback server
    # -------------------------------------------------

    server = HTTPServer(
        ("localhost", 8000),
        CallbackHandler
    )

    print("\n")
    print("=" * 60)
    print("WAITING FOR LINKEDIN CALLBACK")
    print("=" * 60)

    print(
        f"\nListening on: {REDIRECT_URI}"
    )

    print(
        "\nIMPORTANT:"
    )

    print(
        "Do not manually open the callback URL."
    )

    print(
        "Complete the authorization in LinkedIn."
    )

    try:

        server.serve_forever()

    except SystemExit:

        pass

    finally:

        server.server_close()

        print("\nOAuth server stopped.")


if __name__ == "__main__":

    main()