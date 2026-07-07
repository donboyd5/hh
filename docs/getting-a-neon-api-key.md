# Getting a Neon CRM API key

Hubbard Hall's data lives in **Neon CRM** (by Neon One). This project pulls that data through
Neon's **REST API v2** instead of manual report exports, so every pull is automatic, timestamped,
and repeatable.

To use the API you need **two values** from your Neon CRM system:

| Value | What it is | Where to find it |
|---|---|---|
| **Org ID** | Your organization's unique Neon system ID | Settings → Organization Profile |
| **API key** | A secret key tied to a Neon user | Settings → User Management |

---

## Step 1 — Copy your Org ID

1. Sign in to your Hubbard Hall Neon CRM.
2. Click the **Settings** cog (top right).
3. Go to **Organization Profile**.
4. Under **Account Information**, copy the **Organization ID**.

## Step 2 — Create a dedicated user and generate an API key

> An API key inherits **all the permissions** of the Neon user it belongs to. Best practice is to
> create a dedicated "integration" user with the minimum access this project needs, so you can
> rotate or revoke it independently of any real person's login. You will likely need a Neon
> **admin** (e.g., Judy) to create the user and assign its role.

1. Settings cog → **User Management**.
2. Create a new user (suggested name: **"HH Data Integration"**).
3. Grant it **read** access to: **Accounts, Donations, Events, and Event Registrations** (and
   Campaigns / Memberships if those modules are available). **Avoid granting write/delete** — this
   project only reads.
4. On that user's page, enable **API Access** and **copy the API key** shown.
   (You usually can't view it again later — store it somewhere safe now.)

## Step 3 — Put the credentials in `.env`

Create a file named **`.env`** in the **project root** (next to `pyproject.toml`) with:

```
NEON_ORG_ID=paste-your-org-id-here
NEON_API_KEY=paste-your-api-key-here
```

`.env` is gitignored — it is never committed. See `.env.example` for the template. The code reads
these two variables automatically; nothing else needs the values.

---

## Security notes

- **Never paste the API key into chat, email, Slack, or a commit.** Put it only in `.env`.
- If a key leaks, disable **API Access** on that user (User Management) and generate a new one.
- Because the key's permissions equal the user's permissions, a locked-down, read-only user is the
  safe choice.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `401 Unauthorized` | Wrong Org ID or API key |
| `403 Forbidden` | The API-key user lacks permission for that data |
| `429 Too Many Requests` | Hit Neon's rate limit (the client throttles + backs off automatically) |
| Empty results | Filters too narrow, or the user can't see that module |
