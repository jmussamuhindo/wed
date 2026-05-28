# Wedding Confirmation — Adeline &amp; Mussa

A bilingual (English / Polish) wedding confirmation app for
**Adeline Helga Munezero &amp; Mussa Justin Muhindo** on **June 20, 2026** in Łódź.

The app has two faces:

- **Guest side** (`/`) — anyone with the link can confirm whether they will
  attend, how many people are on their side, how many children under 5, meal
  preference, dietary restrictions, and a message.
- **Admin side** (`/admin`) — password-protected dashboard for the couple, with
  live totals, search, filters, edit, delete, and CSV export.

## Run locally

```bash
cd wedding_rsvp
pip3 install -r requirements.txt
python3 app.py
```

Open these URLs:

| URL                            | Who                                             |
|--------------------------------|-------------------------------------------------|
| `http://127.0.0.1:5002/`       | Guests — confirmation form                      |
| `http://127.0.0.1:5002/admin`  | You — admin dashboard (redirects to login)      |

The default admin password is `muhindo2026`. **Change it in production** by
setting the `ADMIN_PASSWORD` environment variable (see below).

## Admin dashboard features

- **Big headline number** — total people coming, split into adults vs children
- **Status cards** — confirmed yes, declining, total responses
- **Meal breakdown** — how many standard menus vs vegetarian, with a bar chart
- **Search box** — filter by name, phone, message, dietary restrictions
- **Status filter** — All / Attending / Declining
- **Edit per row** — fix any mistake instantly
- **Delete per row** — remove bad rows (with confirm dialog)
- **Export CSV** — download every response as a clean spreadsheet
- **Logout** — clears your admin session

## Deploy (Render — recommended, free tier works)

1. Push this folder to GitHub.
2. On [render.com](https://render.com), New → **Web Service** → connect repo.
3. Settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`
4. Environment variables (Render dashboard → Environment):

   ```
   ADMIN_PASSWORD=your-strong-password-here
   SECRET_KEY=<paste a long random string>
   ```

   Optional, for email notifications:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=jmussamuhindo@gmail.com
   SMTP_PASS=your_gmail_app_password
   NOTIFY_EMAIL=jmussamuhindo@gmail.com
   ```

5. Deploy. Render gives you a URL like `https://wedding-rsvp.onrender.com`.
   Share that URL with your guests; visit `/admin` yourself.

> **Persistence note:** Render's free tier has ephemeral filesystem — the
> `responses.csv` file resets on every redeploy. For permanent storage, either
> attach a persistent disk in Render, or download a fresh CSV via the **Export**
> button frequently.

### Other hosts

- **Railway / Fly.io** — same idea: connect the repo, set the env vars, deploy.
- **PythonAnywhere** — set up a Flask web app, point WSGI to `app:app`, add the
  env vars in the Web tab.
- **Heroku** — works out of the box with the included `Procfile`.

## Generating a strong `SECRET_KEY`

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Paste the output as your `SECRET_KEY` env var.

## Where guest responses live

Every submission is written to `responses.csv` next to `app.py`. CSV columns:

```
id, submitted_at, language, full_name, phone, attending,
number_of_guests, children_under_5, meal_preference,
dietary_restrictions, message
```

You can open this file in Excel / Google Sheets directly, or click **Export CSV**
in the admin dashboard for a clean download.

## Editing wedding details

All wedding details live in the `WEDDING` dict at the top of `app.py`. Edit
there to change the couple names, venues, date, or RSVP deadline.

## Security model

- Admin uses session-based login (Flask `session` cookie signed with
  `SECRET_KEY`). The password is never sent in URLs.
- Guests editing their own submission use a unique unguessable URL
  (`/edit/<uuid>`). The link is sent to them only after they re-submit a name
  that's already in the database. This is "security by unguessability" —
  appropriate for a wedding context but not banking.
- Set a strong `ADMIN_PASSWORD` and a fresh `SECRET_KEY` in production.
