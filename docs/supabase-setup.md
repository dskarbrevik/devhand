# Supabase Setup Guide

Detailed guide for configuring Supabase authentication with allowed users access control.

## Overview

This guide covers:
- Creating and configuring a Supabase project
- Setting up email authentication
- Creating the `allowed_users` table with RLS policies
- Managing allowed users with `dh` CLI
- Troubleshooting common issues

## Create Supabase Project

### 1. Sign up / Log in

Visit [supabase.com](https://supabase.com) and sign in with GitHub or create an account.

### 2. Create New Project

1. From the dashboard, click **New Project**
2. Select your organization (or create one)
3. Fill in project details:
   - **Name:** `your-app` (or your chosen name)
   - **Database Password:** Generate a strong password and save it securely
   - **Region:** Choose closest to your users
   - **Pricing Plan:** Free tier is fine for development

4. Click **Create new project**
5. Wait ~2 minutes for provisioning

### 3. Collect Project Credentials

You'll need several credentials for local development and deployment:

#### API Credentials

Navigate to **Settings** → **API**:

| Credential | Location | Use |
|------------|----------|-----|
| **Project URL** | Project Settings → API | Frontend environment variable |
| **anon/public key** | Project Settings → API (anon public) | Frontend - public operations |
| **service_role key** | Project Settings → API (service_role) | Backend/CLI - admin operations |

**⚠️ Important:** The service_role key bypasses Row Level Security. Never expose it in frontend code or commit it to git.

#### Database Credentials

Navigate to **Settings** → **Database**:

| Credential | Location | Use |
|------------|----------|-----|
| **Password** | Database Settings | `dh` CLI and direct database access |
| **Project Reference** | Connection string (`xxx` in `xxx.supabase.co`) | CLI operations |

If you lost your password, click **Reset Database Password**.

#### Access Token

Navigate to [Account Settings → Access Tokens](https://supabase.com/dashboard/account/tokens):

1. Click **Generate new token**
2. Name it (e.g., "Local Development")
3. Copy the token immediately (shown only once)

**Use:** Supabase CLI operations via `dh` commands.

## Configure Authentication

### Enable Email Provider

1. Navigate to **Authentication** → **Providers**
2. Find **Email** in the provider list
3. Toggle **Enable Email provider** to ON
4. Configure email confirmation:
   - **Disable** for development (users can log in immediately)
   - **Enable** for production (users must verify email)

5. Click **Save**

### Configure URL Settings

Navigate to **Authentication** → **URL Configuration**:

Add your application URLs:

**Site URL:**
```
https://your-app.vercel.app
```

**Redirect URLs** (one per line):
```
https://your-app.vercel.app/auth/callback
http://localhost:3000/auth/callback
```

If you have multiple environments (staging, preview), add those URLs too.

### Configure OAuth Providers (Optional)

The template includes OAuth support. To enable providers like Google:

#### Enable Google OAuth

**1. Create Google OAuth Credentials**

Visit [Google Cloud Console](https://console.cloud.google.com):

1. Create a new project or select existing one
2. Navigate to **APIs & Services** → **Credentials**
3. Click **Create Credentials** → **OAuth 2.0 Client ID**
4. Configure OAuth consent screen if prompted:
   - User Type: External (for public apps)
   - Add app name, user support email, developer email
   - Add scopes: `email`, `profile`, `openid`
5. Select **Web application** as application type
6. Add **Authorized JavaScript origins**:
   - `http://localhost:3000` (local development)
   - `https://your-app.vercel.app` (production)
7. Add **Authorized redirect URIs**:
   - `https://<project-ref>.supabase.co/auth/v1/callback`
   - Replace `<project-ref>` with your Supabase project reference
8. Click **Create**
9. Copy the **Client ID** and **Client Secret**

**2. Configure Supabase**

Navigate to **Authentication** → **Providers** in Supabase:

1. Find **Google** in the provider list
2. Toggle **Enable Google provider** to ON
3. Paste your **Client ID** from Google
4. Paste your **Client Secret** from Google
5. The callback URL is pre-filled: `https://<project-ref>.supabase.co/auth/v1/callback`
6. Click **Save**

**3. Verify Frontend Implementation**

Your template already includes Google OAuth:
- `AuthForm.tsx` has `handleGoogleLogin()` function
- Google sign-in button is displayed on auth page
- Callback route handles OAuth redirects

**4. Test Google Sign-In**

1. Start your frontend: `npm run dev`
2. Visit `http://localhost:3000`
3. Click the **Google** button
4. Complete Google OAuth flow
5. You should be redirected to `/dashboard`

**⚠️ Important:** Users who sign in via Google must still be added to `allowed_users` table. After first Google sign-in:
1. Add their email to `supabase/allowed_users.txt`
2. Run `dh db sync-users`

#### Other OAuth Providers

The same pattern applies for GitHub, Microsoft, etc.:
1. Create OAuth app in provider's console
2. Get Client ID and Secret
3. Enable provider in Supabase → Authentication → Providers
4. Update redirect URIs to use Supabase callback URL

### Optional: Customize Email Templates

Navigate to **Authentication** → **Email Templates** to customize:
- Confirmation email
- Password reset email  
- Magic link email

Use the template editor to match your branding.

## Database Setup

### Run Migrations with `dh`

From your frontend project directory:

```bash
dh db migrate
```

**What this does:**
1. Connects to your Supabase project using credentials from `.env`
2. Finds migration files in `supabase/migrations/`
3. Executes SQL to create the `allowed_users` table
4. Sets up Row Level Security (RLS) policies

**Migration creates:**
- `allowed_users` table with columns:
  - `id` (primary key)
  - `user_id` (references auth.users)
  - `created_at` (timestamp)
- RLS policies:
  - Users can only read their own allowed status
  - Only service role can insert/update/delete
- Index on `user_id` for fast lookups

### Manual Migration (Alternative)

If you prefer to run migrations manually:

1. Navigate to **SQL Editor** in Supabase dashboard
2. Run this SQL:

```sql
-- Create allowed_users table
CREATE TABLE IF NOT EXISTS public.allowed_users (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    UNIQUE(user_id)
);

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_allowed_users_user_id ON public.allowed_users(user_id);

-- Enable Row Level Security
ALTER TABLE public.allowed_users ENABLE ROW LEVEL SECURITY;

-- Policy: Users can read their own allowed status
CREATE POLICY "Users can view their own allowed status"
    ON public.allowed_users
    FOR SELECT
    USING (auth.uid() = user_id);

-- Policy: Only service role can insert
CREATE POLICY "Service role can insert allowed users"
    ON public.allowed_users
    FOR INSERT
    WITH CHECK (auth.role() = 'service_role');

-- Policy: Only service role can delete
CREATE POLICY "Service role can delete allowed users"
    ON public.allowed_users
    FOR DELETE
    USING (auth.role() = 'service_role');

-- Grant access
GRANT SELECT ON public.allowed_users TO authenticated;
GRANT ALL ON public.allowed_users TO service_role;
```

## Managing Allowed Users

### Understanding the Workflow

**Important:** Users must sign up at least once before they can be added to the allowed users list.

**Workflow:**
1. User visits your app and signs up with email/password
2. User is created in `auth.users` table
3. Admin adds user's email to `allowed_users.txt`
4. Admin runs `dh db sync-users`
5. User can now access protected content

### Add Users via `dh` CLI

#### Initial Setup

Create `supabase/allowed_users.txt` with emails (one per line):

```txt
admin@yourcompany.com
developer@yourcompany.com
user@example.com
```

#### Sync to Database

```bash
dh db sync-users
```

**What this does:**
1. Reads emails from `supabase/allowed_users.txt`
2. Looks up each email in `auth.users` table
3. Inserts matching user IDs into `allowed_users` table
4. Skips emails that haven't signed up yet
5. Reports results

**Example output:**
```
📋 Syncing allowed users from supabase/allowed_users.txt

✓ Successfully added: admin@yourcompany.com
✓ Successfully added: developer@yourcompany.com
⚠ Skipped (not found): user@example.com - User hasn't signed up yet

Summary: 2 added, 1 skipped
```

### Add Users Manually (SQL)

If you prefer manual control:

1. Get user's UUID from **Authentication** → **Users** table
2. Navigate to **SQL Editor**
3. Run:

```sql
INSERT INTO public.allowed_users (user_id)
VALUES ('user-uuid-here')
ON CONFLICT (user_id) DO NOTHING;
```

### Verify Allowed Users

Check who's on the allowed list:

**Via SQL Editor:**
```sql
SELECT 
    au.id,
    u.email,
    au.created_at
FROM public.allowed_users au
JOIN auth.users u ON au.user_id = u.id
ORDER BY au.created_at DESC;
```

**Via Table Editor:**
1. Navigate to **Table Editor**
2. Select `allowed_users` table
3. View all entries

### Remove Users

**Via `dh` CLI:**
Remove email from `supabase/allowed_users.txt` and run:
```bash
dh db sync-users --remove-unlisted
```

**Via SQL:**
```sql
DELETE FROM public.allowed_users
WHERE user_id = (
    SELECT id FROM auth.users WHERE email = 'user@example.com'
);
```

## Testing Authentication Flow

### Test Signup & Login

1. Start your frontend: `npm run dev`
2. Visit `http://localhost:3000`
3. Click **Sign Up**
4. Enter an email from `allowed_users.txt` and password
5. Submit form
6. You should be redirected to dashboard

### Test Unauthorized Access

1. Sign out
2. Sign up with an email NOT in `allowed_users.txt`
3. You should see "User not allowed to access this application"

### Test Protected Routes

The middleware in `src/middleware.ts` checks:
1. Is user authenticated? (has valid session)
2. Is user in `allowed_users` table?

If either check fails, user is redirected to home or coming-soon page.

## RLS Policy Explanation

### Why Row Level Security?

RLS ensures users can only:
- Read their own allowed status
- Cannot add themselves or others to the allowed list
- Cannot remove themselves from the allowed list

### Policy Breakdown

**SELECT Policy:**
```sql
CREATE POLICY "Users can view their own allowed status"
    ON public.allowed_users
    FOR SELECT
    USING (auth.uid() = user_id);
```
- Authenticated users can check if they're allowed
- Used by middleware to verify access

**INSERT/DELETE Policies:**
```sql
CREATE POLICY "Service role can insert allowed users"
    ON public.allowed_users
    FOR INSERT
    WITH CHECK (auth.role() = 'service_role');
```
- Only service_role key can modify allowed users
- Prevents users from granting themselves access

## Troubleshooting

### "User not allowed to access this application"

**Cause:** User not in `allowed_users` table

**Solution:**
1. Verify user has signed up: Check **Authentication** → **Users**
2. Add email to `supabase/allowed_users.txt`
3. Run `dh db sync-users`
4. Have user log out and log back in

### "`dh db` commands fail"

**Cause:** Missing or incorrect credentials

**Solution:**
1. Run `dh setup` to reconfigure
2. Verify `.env` has:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `SUPABASE_DB_PASSWORD`
   - `SUPABASE_ACCESS_TOKEN`
3. Check service_role key is correct (not anon key)

### "Could not connect to Supabase"

**Cause:** Network issue or incorrect URL

**Solution:**
1. Verify Project URL in Supabase dashboard
2. Check URL format: `https://xxx.supabase.co` (no trailing slash)
3. Test connection: `curl https://xxx.supabase.co`

### Migration already exists

**Cause:** Running `dh db migrate` multiple times

**Solution:**
- Safe to ignore if table already exists
- Or manually drop table and re-run

### Users can't log in after being added

**Cause:** Session cache or middleware not checking latest data

**Solution:**
1. Have user log out completely
2. Clear browser cache/cookies
3. Log back in
4. Middleware will re-check allowed status

## Advanced Configuration

### Custom RLS Policies

Add more granular policies for your use case:

```sql
-- Allow users to see all allowed users (for admin panel)
CREATE POLICY "Admins can view all allowed users"
    ON public.allowed_users
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.user_roles
            WHERE user_id = auth.uid() AND role = 'admin'
        )
    );
```

### Audit Logging

Track who added users and when:

```sql
-- Add columns to allowed_users
ALTER TABLE public.allowed_users
ADD COLUMN added_by UUID REFERENCES auth.users(id),
ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE;

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc'::text, NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON public.allowed_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
```

### Email Invitations

Instead of manual list, send invitation codes:

1. Create `invitations` table with unique codes
2. User enters code during signup
3. Middleware validates invitation
4. Automatically adds to allowed_users

## Next Steps

- [Railway Deployment](railway-deployment.md) - Deploy your backend
- [Vercel Deployment](vercel-deployment.md) - Deploy your frontend
- [Main Deployment Guide](../DEPLOYMENT_GUIDE.md) - Complete workflow

## Resources

- [Supabase Auth Documentation](https://supabase.com/docs/guides/auth)
- [Row Level Security Guide](https://supabase.com/docs/guides/auth/row-level-security)
- [Supabase CLI Reference](https://supabase.com/docs/reference/cli)
