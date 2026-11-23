# Deployment Guide

## 1. Current production deployment

| | |
|---|---|
| URL | https://trademind-ai-ujm6.onrender.com |
| Platform | Render web service · free plan · region Singapore |
| Build | `Dockerfile` at the repo root (Python 3.11-slim, non-root user) |
| Source | `https://github.com/rohan911438/TradeMind-AI`, branch `main`, **auto-deploy on push** |
| Health check | `GET /api/health` |
| Port | `$PORT` (set by Render) |

### Environment variables
| Variable | Purpose | Required |
|---|---|---|
| `GOOGLE_CLIENT_ID` | Enables Google Sign-In (shown to the browser, not secret) | for Google login |
| `SECRET_KEY` | Signs session cookies; keep it stable so sessions survive restarts | yes in production |
| `HTTPS_ONLY` | `true` marks the session cookie `Secure` | yes on HTTPS |
| `EVENTS_PER_SEC`, `BAR_SECONDS`, `STARTING_CAPITAL`, `RISK_PER_TRADE`, `MAX_SYMBOL_EXPOSURE`, `MAX_TOTAL_EXPOSURE`, `MIN_RR`, `DAILY_LOSS_LIMIT` | Tuning (see `backend/app/config.py`) | optional |

### Free-tier behaviour
- The service sleeps after ~15 minutes without traffic; the first request takes ~1 minute. **Open the URL before a demo.**
- The disk is ephemeral: paper accounts and Parquet recordings reset on restart or redeploy.
- 512 MB RAM is enough; FinBERT would not fit.

## 2. Google Sign-In configuration
1. Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID (Web application).
2. **Authorised JavaScript origins:**
   - `https://trademind-ai-ujm6.onrender.com`
   - `http://localhost:8000`
3. Set `GOOGLE_CLIENT_ID` in Render (Environment) and in `backend/.env` locally.
4. If the consent screen is in *Testing* mode, add the demo Google accounts as test users, or publish the app.

## 3. Deploying your own copy on Render
1. Fork or push the repo to GitHub (public, or connect Render to GitHub).
2. Render → **New → Web Service** → select the repo → runtime **Docker**.
3. Plan: Free; Region: Singapore (closest to India); Health check path `/api/health`.
4. Add the environment variables above (generate a long random `SECRET_KEY`).
5. Deploy. The app is live at `https://<name>.onrender.com`. Add that origin in Google Cloud Console.

## 4. Run with Docker anywhere
```bash
docker build -t trademind-ai .
docker run -p 8000:8000 -e SECRET_KEY=change-me -e GOOGLE_CLIENT_ID=... trademind-ai
```

## 5. AWS EC2 (alternative)
1. Launch Ubuntu 24.04 on **t3.small** (2 GB). Security group: allow 22 (your IP), 80 and 443.
2. Install Docker: `curl -fsSL https://get.docker.com | sh`
3. `git clone https://github.com/rohan911438/TradeMind-AI.git && cd TradeMind-AI && docker build -t trademind-ai .`
4. `docker run -d --restart unless-stopped -p 80:8000 -e SECRET_KEY=... -e GOOGLE_CLIENT_ID=... trademind-ai`
5. For HTTPS (needed for Google Sign-In on a public domain), put Caddy or Nginx with Let's Encrypt in front, and set `HTTPS_ONLY=true`.
6. **Stop the instance after the demo** to avoid charges.

## 6. Operational notes
- **Logs:** Render dashboard → Logs.
- **Redeploy:** push to `main`, or use Render → Manual Deploy.
- **Rotate secrets:** regenerate the Render API key and `SECRET_KEY` after the project ends (changing `SECRET_KEY` signs everyone out).
- **Model updates:** run `python -m app.predictx.train --refresh` locally, commit `backend/models/` and `backend/data/raw/`, then push.
