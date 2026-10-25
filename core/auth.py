"""
REA Core - Google OAuth 2.0 Desktop Authentication Module (RFC 8252)
Implements standard loopback IP authorization flow for desktop clients:
  - Scopes: openid, profile, email
  - Local HTTP server on 127.0.0.1 for browser authorization callback
  - Token exchange & userinfo retrieval (Name, Picture, Email)
  - Persistent local session storage in ~/.config/reamusic/session.json
  - 100% optional: app remains completely usable in anonymous/guest mode.
"""

import http.server
import json
import os
import socket
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from typing import Any, Callable, Dict, Optional, Tuple


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Temporary local HTTP handler that receives the OAuth code callback from the browser."""

    auth_code: Optional[str] = None
    auth_error: Optional[str] = None

    def log_message(self, format, *args):
        # Suppress noisy standard server logging
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            success_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>REA Music - Authenticated</title>
                <style>
                    body { background: #0a0a0a; color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                    .card { background: #161616; border: 1px solid #282828; border-radius: 16px; padding: 40px 50px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.6); }
                    h1 { font-size: 24px; margin: 0 0 12px 0; color: #3b82f6; }
                    p { color: #a7a7a7; font-size: 14px; margin: 0; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>✓ Connected Successfully!</h1>
                    <p>Your Google account has been connected to <b>REA Music</b>.<br>You may now close this browser tab and return to the application.</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(success_html.encode("utf-8"))
        elif "error" in params:
            OAuthCallbackHandler.auth_error = params["error"][0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset="utf-8"><title>Authentication Error</title></head>
            <body style="background:#0a0a0a;color:#ff5555;font-family:sans-serif;text-align:center;padding:50px;">
                <h2>Authentication Failed</h2>
                <p>Google returned the following error: {OAuthCallbackHandler.auth_error}</p>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


class AuthManager:
    """Manages Google OAuth 2.0 flow, local credentials, and session persistence."""

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
    SCOPES = "openid profile email"

    def __init__(self):
        self.config_dir = os.path.expanduser("~/.config/reamusic")
        os.makedirs(self.config_dir, exist_ok=True)
        self.session_file = os.path.join(self.config_dir, "session.json")
        self.credentials_file = os.path.join(self.config_dir, "credentials.json")
        self.local_credentials_file = os.path.join(os.getcwd(), "credentials.json")

    def get_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Retrieves client_id and client_secret from:
          1. Environment variables GOOGLE_CLIENT_ID & GOOGLE_CLIENT_SECRET (or .env file)
          2. ./credentials.json
          3. ~/.config/reamusic/credentials.json
        """
        # Load from local .env if present
        env_file = os.path.join(os.getcwd(), ".env")
        if os.path.exists(env_file):
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip("'\"")
                            if k and k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass

        env_id = os.environ.get("GOOGLE_CLIENT_ID")
        env_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        if env_id and env_secret:
            return env_id.strip(), env_secret.strip()

        for path in (self.local_credentials_file, self.credentials_file):
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # Check standard Google Cloud Console downloaded JSON formats
                    installed = data.get("installed") or data.get("web") or data
                    c_id = installed.get("client_id")
                    c_secret = installed.get("client_secret")
                    if c_id and c_secret:
                        return c_id.strip(), c_secret.strip()
                except Exception:
                    pass

        return None, None

    def save_credentials(self, client_id: str, client_secret: str) -> None:
        """Saves Google OAuth credentials to the user config directory."""
        payload = {"installed": {"client_id": client_id.strip(), "client_secret": client_secret.strip()}}
        with open(self.credentials_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def load_session(self) -> Optional[Dict[str, Any]]:
        """Loads cached user session from local storage."""
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data and "user" in data:
                    return data["user"]
            except Exception:
                return None
        return None

    def save_session(self, user_info: Dict[str, Any], tokens: Dict[str, Any]) -> None:
        """Saves authenticated user profile and tokens to session.json."""
        data = {
            "user": user_info,
            "tokens": tokens,
        }
        with open(self.session_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def clear_session(self) -> None:
        """Removes local session file to log out the user."""
        if os.path.exists(self.session_file):
            try:
                os.remove(self.session_file)
            except Exception:
                pass

    @staticmethod
    def _find_free_port() -> int:
        """Finds an available TCP port for loopback listening."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def login_async(
        self,
        callback: Callable[[bool, Optional[Dict[str, Any]], Optional[str]], None],
    ) -> None:
        """
        Executes RFC 8252 loopback authorization in a separate background thread.
        Calls callback(success: bool, user_info: dict, error_message: str) on completion.
        """
        threading.Thread(target=self._oauth_worker, args=(callback,), daemon=True).start()

    def _oauth_worker(self, callback: Callable[[bool, Optional[Dict[str, Any]], Optional[str]], None]):
        client_id, client_secret = self.get_credentials()
        if not client_id or not client_secret:
            callback(
                False,
                None,
                "OAuth credentials not found.\n"
                "Please configure your client_id and client_secret from the Google Cloud Console.",
            )
            return

        port = self._find_free_port()
        redirect_uri = f"http://127.0.0.1:{port}"

        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.auth_error = None

        server = http.server.HTTPServer(("127.0.0.1", port), OAuthCallbackHandler)
        server.timeout = 120  # 2 minute timeout for user interaction

        # Build authorization URL
        auth_params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": self.SCOPES,
            "access_type": "offline",
            "prompt": "consent",
        }
        auth_url = f"{self.GOOGLE_AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

        # Launch default browser
        webbrowser.open(auth_url)

        # Handle incoming HTTP request
        while OAuthCallbackHandler.auth_code is None and OAuthCallbackHandler.auth_error is None:
            server.handle_request()
            if OAuthCallbackHandler.auth_code or OAuthCallbackHandler.auth_error:
                break

        server.server_close()

        if OAuthCallbackHandler.auth_error:
            callback(False, None, f"Authorization cancelled: {OAuthCallbackHandler.auth_error}")
            return

        code = OAuthCallbackHandler.auth_code
        if not code:
            callback(False, None, "Timeout exceeded or authorization code not received.")
            return

        # Exchange authorization code for tokens
        token_data = urllib.parse.urlencode({
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }).encode("utf-8")

        try:
            req_token = urllib.request.Request(
                self.GOOGLE_TOKEN_URL,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urllib.request.urlopen(req_token, timeout=15) as resp:
                token_resp = json.loads(resp.read().decode("utf-8"))

            access_token = token_resp.get("access_token")
            if not access_token:
                callback(False, None, "Failed to obtain access token from Google.")
                return

            # Fetch user profile from userinfo endpoint
            req_info = urllib.request.Request(
                self.GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            with urllib.request.urlopen(req_info, timeout=15) as resp:
                user_info = json.loads(resp.read().decode("utf-8"))

            clean_user = {
                "name": user_info.get("name", "User"),
                "given_name": user_info.get("given_name") or user_info.get("name", "User").split()[0],
                "email": user_info.get("email", ""),
                "picture": user_info.get("picture", ""),
            }

            self.save_session(clean_user, token_resp)
            callback(True, clean_user, None)

        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace")
            callback(False, None, f"HTTP Error {err.code}: {err_body}")
        except Exception as e:
            callback(False, None, f"Unexpected error during authentication: {e}")
