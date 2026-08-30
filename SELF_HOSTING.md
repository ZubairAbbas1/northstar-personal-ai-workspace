# Self-hosting Northstar

Northstar is designed to run on a person's own computer. You do not need to buy a domain or use a Northstar-hosted service. The normal local addresses are:

- Web app: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API documentation: `http://localhost:8000/docs`

## What stays local

The default installation uses SQLite files on the host computer. Northstar users, tasks, projects, memories, integration metadata, and encrypted provider credentials are stored in that installation. `.env`, databases, provider tokens, logs, and vector data are excluded from Git.

Anyone with access to the computer and its files should still be treated as a trusted administrator. Use a strong local login, keep `.env` private, and back up the encryption key if you need to preserve encrypted connections.

## Install from source

Requirements:

- Git
- Python 3.11 or newer
- Node.js 20 or newer

```bash
git clone https://github.com/ZubairAbbas1/northstar-personal-ai-workspace.git
cd northstar-personal-ai-workspace
python -m venv .venv
```

Activate the Python environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# Linux or macOS
source .venv/bin/activate
```

Install dependencies and create the local environment file:

```bash
pip install -r requirements.txt
cd frontend
npm ci
cd ..
```

Copy `.env.example` to `.env`, then generate private values:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put the first value in `JWT_SECRET` and the second in `ENCRYPTION_KEY`. Leave provider fields empty until you configure the integrations you want.

Start the backend:

```bash
python -m uvicorn backend.main:app --reload --port 8000
```

In a second terminal, start the frontend:

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000`, create an account, and complete onboarding. The account exists only in this Northstar installation.

## Connect Google on localhost

Google OAuth credentials belong to the person operating the installation; they are not shared by the open-source project.

1. Create or select a project in Google Cloud Console.
2. Enable the Gmail API and Google Calendar API.
3. Configure the OAuth consent screen. While the app is in testing, add the Google accounts that will connect as test users.
4. Create an OAuth 2.0 Client ID with application type **Web application**.
5. Add this authorized redirect URI exactly:

   `http://localhost:8000/api/v1/integrations/google/callback`

6. Put its values in the local `.env`:

   ```dotenv
   GOOGLE_CLIENT_ID=your-local-google-client-id
   GOOGLE_CLIENT_SECRET=your-local-google-client-secret
   ```

7. Restart the backend. Open **Integrations** and connect Gmail or Google Calendar.

For Gmail only, a Google App Password is also supported when two-step verification and App Passwords are available on the Google account.

## Connect GitHub on localhost

1. In GitHub, open **Settings → Developer settings → OAuth Apps → New OAuth App**.
2. Use `http://localhost:3000` as the homepage URL.
3. Use this authorization callback URL exactly:

   `http://localhost:8000/api/v1/integrations/github/callback`

4. Put the generated values in `.env`:

   ```dotenv
   GITHUB_CLIENT_ID=your-local-github-client-id
   GITHUB_CLIENT_SECRET=your-local-github-client-secret
   ```

5. Restart the backend and connect GitHub from **Integrations**.

## Connect Discord

1. Create an application and bot in the Discord Developer Portal.
2. Enable **Message Content Intent**.
3. Invite the bot to a server with **View Channels** and **Read Message History** only.
4. In Northstar, open **Integrations**, paste the bot token, and select up to ten readable channels.

Use a bot token only—never a personal Discord account token. Northstar's current Discord integration is read-only and uses the explicit channel allow-list.

## Configure AI

Choose one of these approaches in Northstar settings or `.env`:

- Run Ollama locally and use its local base URL.
- Add a Groq, OpenAI, Anthropic, or Gemini API key to the server.
- Let each Northstar user save their own provider key through BYOK settings. Saved keys are encrypted at rest.

Without a configured model, the deterministic workspace features still run, but open-ended AI answers require an available provider.

## Update an installation

Stop the servers, back up `.env` and the database files, then run:

```bash
git pull
pip install -r requirements.txt
cd frontend
npm ci
cd ..
```

Restart both servers after the update. Never copy another person's `.env`, database, OAuth token files, or encryption key into a public issue or commit.
