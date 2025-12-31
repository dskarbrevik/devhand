# Deployment Guide

Complete guide to deploying a full-stack web application from the hello-world templates to production.

## Overview

This guide takes you from zero to a fully deployed web application in approximately 30 minutes. You'll create a FastAPI backend on Railway, configure Supabase for authentication, deploy a Next.js frontend on Vercel, and manage all credentials with the `dh` CLI tool.

**What you'll build:**
- Backend API on Railway
- Supabase authentication with allowed users list
- Next.js frontend on Vercel
- Local development environment with all credentials configured

## Prerequisites

- GitHub account
- Railway account ([railway.app](https://railway.app))
- Supabase account ([supabase.com](https://supabase.com))
- Vercel account ([vercel.com](https://vercel.com))
- `dh` CLI installed (`pip install devhand`)
- Git, Python 3.12+, Node.js 20+

## Deployment Steps

### 1. Deploy Backend to Railway

**Create backend repository:**
```bash
# On GitHub, use hello-world-be as a template
# Create new repo: your-app-be
```

**Deploy to Railway:**
1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your `your-app-be` repository
4. Railway auto-detects Python/FastAPI and deploys
5. Click **Settings** → **Generate Domain** to get your API URL
6. Copy your backend URL (e.g., `https://your-app-be.up.railway.app`)

**Verify deployment:**
```bash
curl https://your-app-be.up.railway.app/
# Should return: {"message": "Hello World from FastAPI Backend!", "status": "success"}
```

**Duration:** ~5 minutes  
**Detailed guide:** [docs/railway-deployment.md](docs/railway-deployment.md)

---

### 2. Create & Configure Supabase Project

**Create project:**
1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Click **New Project**
3. Choose organization, name your project, set strong database password
4. Wait ~2 minutes for provisioning

**Collect credentials:**
Navigate to **Settings** → **API**:
- Copy **Project URL** (e.g., `https://xxx.supabase.co`)
- Copy **anon/public key** (starts with `sb_secret...`)
- Copy **service_role/secret key** (starts with `sbp_...`, keep secure!)

Navigate to **Settings** → **Database**:
- Copy your **Database password** (or reset it)

Generate **Access Token**:
- Go to [Account Tokens](https://supabase.com/dashboard/account/tokens)
- Click **Generate new token**
- Copy the token

**Configure authentication:**
1. Go to **Authentication** → **Providers**
2. Enable **Email** provider
3. **Save**

**Set callback URLs for authentication:**
1. Go to **Authentication** → **URL Configuration**
2. Add **Redirect URLs** (one per line):
   - `http://localhost:3000/auth/callback` (for local development)
   - You'll add your Vercel URL here after deployment in step 7
3. **Save**

**Note:** You'll update these URLs again after deploying to Vercel.

**Duration:** ~5 minutes  
**Detailed guide:** [docs/supabase-setup.md](docs/supabase-setup.md)

---

### 3. Create Frontend Repository

**Create from template:**
```bash
# On GitHub, use hello-world-fe as a template
# Create new repo: your-app-fe

# Clone locally
git clone https://github.com/your-username/your-app-fe.git
cd your-app-fe
```

**Duration:** ~2 minutes

---

### 4. Configure Local Environment with `dh`

From your frontend project directory:

```bash
dh setup
```

**What this does:**
- Installs dependencies (npm install)
- Creates `.env` file with prompts for:
  - Supabase URL (from step 2)
  - Supabase anon key (from step 2)
  - Backend API URL (from step 1)
  - Supabase DB password (from step 2)
  - Supabase access token (from step 2)
- Verifies Supabase CLI installation
- Links Supabase project

**Duration:** ~3 minutes  

---

### 5. Setup Supabase Database

**Run database migrations:**
```bash
dh db migrate
```

This creates the `allowed_users` table with row-level security policies.

**Add allowed users:**

Create `supabase/allowed_users.txt` with email addresses (one per line):
```txt
admin@yourcompany.com
user@example.com
```

**Sync users to database:**
```bash
dh db sync-users
```

**Important:** Users must sign up at least once before they can be added to the allowed list. The `dh db sync-users` command will skip emails that haven't signed up yet.

**Duration:** ~5 minutes  
**Detailed guide:** [docs/supabase-setup.md](docs/supabase-setup.md)

---

### 6. Test Local Development

**Start frontend:**
```bash
npm run dev
```
**Duration:** ~5 minutes

---

### 7. Deploy Frontend to Vercel

**From Vercel Dashboard:**

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click **Add New** → **Project**
3. Import your `your-app-fe` repository from GitHub
4. Vercel auto-detects Next.js framework

**Configure environment variables:**

Before deploying, add these environment variables:

| Variable | Value | Where to find |
|----------|-------|---------------|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://xxx.supabase.co` | Supabase → Settings → API |
| `NEXT_PUBLIC_SUPABASE_KEY` | `sbp_secret...` (public/anon key) | Supabase → Settings → API |
| `NEXT_PUBLIC_API_URL` | `https://your-app-be.up.railway.app` | Railway dashboard |

**Deploy:**
5. Click **Deploy**
6. Wait ~2 minutes for build
7. Your app is live! (e.g., `https://your-app.vercel.app`)

**Update Supabase redirect URLs:**

Now that your app is deployed, add the production URL to Supabase:

1. Go to **Supabase** → **Authentication** → **URL Configuration**
2. Update **Site URL:** `https://your-app.vercel.app`
3. Add to **Redirect URLs:**
   - `https://your-app.vercel.app/auth/callback` (add this new one)
   - Keep existing: `http://localhost:3000/auth/callback`
4. **Save**

**Important:** Without this step, users will get redirect errors after login on production.

**Duration:** ~5 minutes  
**Detailed guide:** [docs/vercel-deployment.md](docs/vercel-deployment.md)

---

### 8. Configure GitHub Actions Secrets (for CI/CD)

If your frontend repository has GitHub Actions workflows for testing, add the Supabase credentials as repository secrets:

1. Go to your **GitHub repository** → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add:
   - Name: `NEXT_PUBLIC_SUPABASE_URL`  
     Value: Your Supabase project URL (e.g., `https://xxx.supabase.co`)
   - Name: `NEXT_PUBLIC_SUPABASE_KEY`  
     Value: Your Supabase anon/public key
3. Click **Add secret** for each

**Why needed:** GitHub Actions workflows need these environment variables to run tests that interact with Supabase (e.g., authentication flows, API calls).

**Duration:** ~2 minutes

---

## Verification Checklist

After completing all steps, verify:

- [ ] Backend API responds at Railway URL
- [ ] Supabase project has `allowed_users` table
- [ ] Local frontend runs and connects to backend
- [ ] Can sign up with allowed email
- [ ] Can log in and access dashboard
- [ ] Production frontend deployed on Vercel
- [ ] Production auth flow works end-to-end

## Common Issues

**"User not allowed to access this application"**
- User email not in `allowed_users` table
- Run `dh db sync-users` after user signs up

**"Failed to fetch" errors in frontend**
- Check `NEXT_PUBLIC_API_URL` is correct
- Verify Railway backend is running
- Check CORS settings if custom domain

**Supabase redirect errors**
- Add your Vercel URL to Supabase redirect URLs
- Include `/auth/callback` path

**`dh` commands fail**
- Run `dh setup` to configure credentials
- Check `.env` file has all required variables

## Next Steps

**Development workflow:**
- Make changes locally with `npm run dev`
- Push to GitHub
- Vercel auto-deploys from main branch
- Backend deploys automatically on Railway

**Add more allowed users:**
```bash
echo "newuser@example.com" >> supabase/allowed_users.txt
dh db sync-users
```

**Monitor & logs:**
- **Railway:** Dashboard → Deployments → View Logs
- **Vercel:** Dashboard → Deployments → Function Logs
- **Supabase:** Dashboard → Database → Logs

## Documentation

- [Supabase Setup Guide](docs/supabase-setup.md) - Authentication & database details
- [Railway Deployment](docs/railway-deployment.md) - Backend deployment & configuration
- [Vercel Deployment](docs/vercel-deployment.md) - Frontend deployment & environment variables

## Support

- Backend template: [hello-world-be README](hello-world-be/README.md)
- Frontend template: [hello-world-fe README](hello-world-fe/README.md)
- DevHand CLI: [dh documentation](https://github.com/dskarbrevik/devhand)
