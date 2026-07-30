# Google OAuth Setup

## Table of Contents

- [Prerequisites](#prerequisites)
  - [Create Google OAuth Credentials](#create-google-oauth-credentials)
  - [Configure `oauth.yml`](#configure-oauthyml)
  - [Optionally Disable Self-Registration](#optionally-disable-self-registration)
  - [Run the Config Checker](#run-the-config-checker)
  - [Restart the Web Service](#restart-the-web-service)
- [How It Works](#how-it-works)
- [User Profile](#user-profile)
- [Security Notes](#security-notes)
- [Troubleshooting](#troubleshooting)

QUADS supports Google OAuth2/OpenID Connect for single sign-on. Users click
"SSO Login" on the web UI and authenticate via their Google account. Only
email addresses from explicitly allowed domains are granted access.

## Prerequisites

- A Google Cloud project with the OAuth consent screen configured
- QUADS web UI accessible over HTTPS (required for secure cookies in production)
- The QUADS database migration `cf4d6cca178b` applied (`alembic upgrade head`)

### Create Google OAuth Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Select or create a project.
3. Navigate to **APIs & Services > Credentials**.
4. Click **Create Credentials > OAuth client ID**.
5. Set application type to **Web application**.
6. Under **Authorized redirect URIs**, add:
   ```
   https://<your-quads-host>/auth/callback
   ```
   For local development, also add:
   ```
   http://localhost:5000/auth/callback
   ```
7. Click **Create** and note the **Client ID** and **Client Secret**.
> [!NOTE]
> **Consent screen**: Under **APIs & Services > OAuth consent screen**, set the
> user type to **Internal** (G Workspace) or **External** and add the
> `email`, `profile`, and `openid` scopes.

### Configure `oauth.yml`

Edit `/opt/quads/conf/oauth.yml` (or `$QUADS_CONF_DIR/oauth.yml`):

```yaml
google_oauth:
  client_id: '<your-client-id>.apps.googleusercontent.com'
  client_secret: '<your-client-secret>'
  server_metadata_url: 'https://accounts.google.com/.well-known/openid-configuration'
  client_kwargs:
    scope: 'openid email profile'

oauth_settings:
  flask_secret_key: '<random-secret-key>'
  allowed_domains:
    - 'yourcompany.com'
  session_lifetime_hours: 24
  remember_me_duration_days: 30
```

| Key | Description |
|-----|-------------|
| `client_id` / `client_secret` | From step 1 |
| `server_metadata_url` | Google's OIDC discovery endpoint (no need to change) |
| `flask_secret_key` | Random string used to sign session cookies. Generate with: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `allowed_domains` | List of email domains permitted to log in. Users with emails outside these domains are denied. |
| `session_lifetime_hours` | How long a session lasts (default: 24) |
| `remember_me_duration_days` | Duration of the "remember me" cookie (default: 30) |

### Optionally Disable Self-Registration

If you want all new users to come through Google SSO (no self-registration via
the API), set `require_auth_provider: true` in `/opt/quads/conf/selfservice.yml`:

```yaml
require_auth_provider: true
```

This disables the `POST /api/v3/register/` endpoint. Existing local users can
still log in with their password via the API; new users must use SSO or be
created by an admin.

### Run the Config Checker

Verify your configuration has no issues:

```bash
quads --conf-check
```

This warns if `allowed_domains` still contains the placeholder `example.com`.
When `require_auth_provider` is `true`, that warning becomes an error.

### Restart the Web Service

```bash
systemctl restart quads-web
```

## How It Works

1. User clicks **SSO Login** on the web UI.
2. QUADS redirects to Google's authorization endpoint.
3. User authenticates with Google.
4. Google redirects back to `/auth/callback` with an authorization code.
5. QUADS exchanges the code for an access token and reads the user's email,
   name, and profile picture from the ID token.
6. If the email domain is in `allowed_domains` and the email is verified, QUADS
   creates or updates the user record and starts a session.

Users who authenticate via Google do not need a local password. Their account
is linked by Google ID (`sub` claim), so email changes on the Google side are
handled gracefully.

## User Profile

Authenticated users get a profile page at `/auth/profile` where they can:

- View their Google profile picture and email
- Create and revoke API tokens (for CLI/API access)
- Set an SSH public key
- Set a release command
- See their active cloud assignments

## Security Notes

- **HTTPS required in production.** Session and remember-me cookies are set with
  `Secure=True` unless `FLASK_ENV=development`.
- **Domain allowlist is deny-by-default.** If `allowed_domains` is empty or
  missing, all logins are rejected.
- **Profile pictures** are sanitized to only allow URLs from
  `lh3-6.googleusercontent.com` over HTTPS.
- **Session protection** is set to `strong` (Flask-Login regenerates the session
  on IP/user-agent change).

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Access denied" after Google login | Email domain not in `allowed_domains` | Add the domain to `oauth.yml` |
| "Email not verified" flash message | Google account has an unverified email | User must verify their email in Google |
| `RuntimeError` on startup about missing secret key | `flask_secret_key` is blank or missing | Set a random value in `oauth.yml` |
| Redirect URI mismatch error from Google | Callback URL not registered | Add `https://<host>/auth/callback` to the Google Cloud Console |
| Cookies not persisting | Not using HTTPS in production | Deploy behind HTTPS or set `FLASK_ENV=development` for local testing |
