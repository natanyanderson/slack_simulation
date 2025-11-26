#!/usr/bin/env python3
import os, json
from urllib.parse import urlencode
from flask import Flask, request, redirect, Response
from slack_sdk import WebClient

# ---- Config ----
CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
# Slack console also must list this exact URL under OAuth & Permissions → Redirect URLs
REDIRECT = os.getenv("SLACK_REDIRECT_URI", "https://localhost:5417/callback")

TOKENS_PATH = "secrets/personas.tokens.json"
USER_SCOPES = "chat:write,channels:read,channels:history,groups:read,groups:history,users:read"

app = Flask(__name__)
os.makedirs("secrets", exist_ok=True)

def _err(msg: str, code: int = 500) -> Response:
    return Response(msg, status=code, mimetype="text/plain")

@app.get("/install")
def install():
    if not CLIENT_ID:
        return _err("Missing SLACK_CLIENT_ID")
    params = {
        "client_id": CLIENT_ID,
        "user_scope": USER_SCOPES,   # request user token scopes
        "redirect_uri": REDIRECT,
    }
    return redirect(f"https://slack.com/oauth/v2/authorize?{urlencode(params)}")

@app.get("/callback")
def callback():
    if not CLIENT_ID or not CLIENT_SECRET:
        return _err("Missing SLACK_CLIENT_ID or SLACK_CLIENT_SECRET")
    code = request.args.get("code")
    if not code:
        return _err("Missing ?code in callback. Start at /install.", 400)

    client = WebClient()  # no token required for oauth exchange
    try:
        resp = client.oauth_v2_access(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            code=code,
            redirect_uri=REDIRECT
        )
    except Exception as e:
        return _err(f"OAuth exchange failed: {e}", 500)

    # Expect authed_user with a user access_token (xoxp-…)
    au = resp.get("authed_user", {})
    xoxp = au.get("access_token")
    user_id = au.get("id")
    if not xoxp or not user_id:
        return _err(f"Unexpected OAuth response:\n{json.dumps(resp, indent=2)}", 500)

    # Persist/update token keyed by Slack user ID
    data = {}
    if os.path.exists(TOKENS_PATH):
        try:
            data = json.load(open(TOKENS_PATH))
        except Exception:
            data = {}
    data[user_id] = {"user_token": xoxp}
    json.dump(data, open(TOKENS_PATH, "w"), indent=2)

    team = (resp.get("team") or {}).get("name", "")
    return f"Authorized user {user_id} on team {team}. You can close this tab."

if __name__ == "__main__":
    # Serve HTTPS locally using mkcert-generated certs
    cert = "secrets/certs/localhost.pem"
    key  = "secrets/certs/localhost-key.pem"
    if not (os.path.exists(cert) and os.path.exists(key)):
        raise SystemExit("Missing TLS cert or key. See README: generate with `mkcert localhost 127.0.0.1 ::1`.")
    app.run(host="127.0.0.1", port=5417, debug=True, ssl_context=(cert, key))