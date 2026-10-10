# Grapsy AI Personal Teacher

## Run locally

1. Install dependencies with `pip install -r requirements.txt`.
2. Copy `.env.example` to `.env` and set a long, random `SECRET_KEY`.
3. Start the app with `uvicorn app.main:app --reload`.
4. Open `http://127.0.0.1:8000`.

Email verification codes are printed in the server terminal until SMTP is configured. The code expires after ten minutes and can be resent after one minute.

## Google and Facebook sign-in

Social sign-in is optional. Create OAuth apps with Google and Facebook, then set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `FACEBOOK_CLIENT_ID`, and `FACEBOOK_CLIENT_SECRET` in `.env`. Set `BASE_URL` to the exact origin used to visit Grapsy. Register these callback URLs with the providers:

- `{BASE_URL}/auth/google/callback`
- `{BASE_URL}/auth/facebook/callback`

For local development, the default origin is `http://127.0.0.1:8000`. Production deployments should use their public HTTPS origin.

## Safety reports

Set `ADMIN_EMAIL` in `.env` to the email address of the Grapsy moderator. That signed-in account can open `/admin/safety-reports` to review reports and update their status. Users can report accounts or messages, block accounts, and manage their block list at `/safety`.

The Privacy Notice and Terms and Conditions are available at `/privacy` and `/terms`. Review their descriptions of data providers, deletion, and report retention whenever the product or its providers change.
