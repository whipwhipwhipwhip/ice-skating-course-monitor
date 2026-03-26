# 🧊 Ice Skating Course Monitor

Checks Active Lambeth's booking system for available spaces on the
**New Skate UK - Level 1&2 (Adults Only)** course and sends you a push
notification when a spot opens up.

## How it works

1. A GitHub Actions cron job runs `check_courses.py` every hour
2. The script calls the CourseProgress API (the same one the booking website uses)
3. If any matching course has `free > 0` spaces, it sends a push notification via [ntfy.sh](https://ntfy.sh)

No dependencies beyond Python's standard library.

## Setup (10 minutes)

### 1. Set up notifications

1. Install the **ntfy** app on your phone ([iOS](https://apps.apple.com/app/ntfy/id1625396347) / [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy))
2. Pick a unique topic name — treat it like a password, e.g. `my-skating-alert-k8m2`
3. In the app, subscribe to that topic
4. Edit `check_courses.py` and replace `CHANGE-ME-ice-skating-12345` with your topic name

### 2. Push to GitHub

```bash
# Create a new private repo on github.com, then:
git init
git add .
git commit -m "Initial commit"
git remote add origin git@github.com:YOUR_USERNAME/ice-skating-monitor.git
git branch -M main
git push -u origin main
```

### 3. Enable GitHub Actions

- Go to your repo → **Actions** tab
- GitHub may ask you to enable workflows — click to allow
- The check will now run every hour automatically
- You can also click **"Run workflow"** to test it immediately

### 4. Test it

Click "Run workflow" in the Actions tab and check the logs. You should see:

```
🔍 Checking courses at 2026-03-25 14:00 UTC
   Looking for: 'Level 1&2 (Adults Only)'

❌ Full: New Skate UK - New Skate UK - Level 1&2 (Adults Only) — 12/12 occupied

😴 No spaces available yet. Will check again next run.
```

## Customisation

### Watch for a different course

Edit `TARGET_COURSE` in `check_courses.py`. It does a case-insensitive
substring match, so `"Level 3"` would match any course with "Level 3" in the name.

### Change the check frequency

Edit the cron expression in `.github/workflows/check.yml`:

- `"0 * * * *"` = every hour (default)
- `"*/30 * * * *"` = every 30 minutes
- `"0 9-21 * * *"` = every hour between 9am–9pm UTC

Note: GitHub Actions cron can be delayed by a few minutes during busy periods.

### Check multiple courses

Change `TARGET_COURSE` to a broader match, or modify `check_availability()`
to check a list of target names.

## Troubleshooting

- **"Failed to fetch course data"** — the API endpoint may have changed,
  or CourseProgress may be doing maintenance. Check if the booking website
  itself is working.
- **No notification received** — make sure your ntfy topic matches exactly
  in both the script and the app. Test manually:
  `curl -d "test" https://ntfy.sh/YOUR-TOPIC`
- **GitHub Actions not running** — check the Actions tab for errors.
  Scheduled workflows are automatically disabled after 60 days of repo
  inactivity; just push a commit or re-enable manually.

## Cost

Completely free:
- ntfy.sh is free for this kind of usage
- GitHub Actions free tier gives you 2,000 minutes/month — this uses ~30