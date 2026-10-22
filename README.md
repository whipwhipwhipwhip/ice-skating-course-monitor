# Ice Skating Course Monitor

Watches Active Lambeth's booking system for open spaces on adult ice skating
courses at Streatham Ice and Leisure Centre, and sends a push notification
when a spot opens up.

## How it works

1. A GitHub Actions cron job runs `check_courses.py` every hour.
2. The script queries the CourseProgress API (the same one the booking site uses).
3. If a course matching `TARGET_COURSES` has free spaces, it sends a push
   notification via [ntfy.sh](https://ntfy.sh). It can also alert once when a
   matching course is first posted, even if it's already full.

Standard library only, no dependencies.

## Setup

### 1. Notifications

1. Install the **ntfy** app ([iOS](https://apps.apple.com/app/ntfy/id1625396347) / [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)).
2. Pick a hard-to-guess topic name, e.g. `my-skating-alert-k8m2`. Anyone who
   knows it can read your alerts, so treat it like a password.
3. Subscribe to that topic in the app.

### 2. GitHub

1. Fork or push this repo to GitHub.
2. Under **Settings → Secrets and variables → Actions**, add a repository
   secret named `NTFY_TOPIC` with your topic name.
3. Open the **Actions** tab and enable workflows if prompted.
4. Click **Run workflow** to test it. The log should look like:

```
Checking courses at 2026-03-25 14:00 UTC
Watching for: ['Level 1&2 (Adults Only)', ...]

Full: New Skate UK - Level 1&2 (Adults Only) (12/12 occupied)

No spaces available.
```

### Running locally

```bash
NTFY_TOPIC=your-topic python check_courses.py
```

Without `NTFY_TOPIC` set, the script prints what it would have sent instead.

## Customisation

- **Courses**: edit `TARGET_COURSES` in `check_courses.py`. Each entry is a
  case-insensitive substring match against the course name.
- **Venue / activity**: edit `API_FILTER` (`centre`, `courseGroupCategory`).
- **Frequency**: edit the cron expression in `.github/workflows/check.yml`,
  e.g. `"*/30 * * * *"` for every 30 minutes. GitHub may delay scheduled runs
  during busy periods.

## Notes

- `.seen_course_ids.json` records courses already alerted on as new. The
  workflow commits it back to the repo whenever it changes, so pull before
  pushing your own changes.
- Scheduled workflows are disabled after 60 days without repo activity; push a
  commit or re-enable them from the Actions tab.
- Free to run: ntfy.sh is free for this usage, and an hourly check fits easily
  within the GitHub Actions free tier.

## License

[MIT](LICENSE)
