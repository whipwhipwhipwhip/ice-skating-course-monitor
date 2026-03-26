"""
Ice Skating Course Availability Monitor
Checks Active Lambeth / CourseProgress for available spaces
and sends a push notification via ntfy.sh when spots open up.
"""
 
import json
import urllib.request
import urllib.parse
import sys
from datetime import datetime, timezone
 
 
# ──────────────────────────────────────────────
# CONFIGURATION — edit these to suit your needs
# ──────────────────────────────────────────────
 
# The API endpoint (base URL)
API_BASE = "https://activelambeth.coursepro.co.uk/portal/api/HomePortal/booking/search"
 
# The filter from your original URL — ice skating courses at Streatham
API_FILTER = {
    "showFullCourses": True,
    "region": 1,
    "courseGroupCategory": [2],  # Ice Skating
    "centre": 4,                # Streatham Ice and Leisure Centre
    "offset": 0,
    "limit": 20,
}
 
# Courses to watch for (substring match, case-insensitive).
# Any course whose name contains one of these strings will be tracked.
# Use broad terms to cast a wide net, or specific names to be precise.
TARGET_COURSES = [
    "Level 1&2 (Adults Only)",
    "Level 1 (Adults",           # In case a Level-1-only course appears
]
 
# Set to True to also get notified about brand-new courses that match
# your targets, even if they're already full. Useful for spotting new
# course postings so you can keep an eye on them.
ALERT_NEW_COURSES = True
 
# ntfy.sh topic — pick something unique and hard to guess
# You'll subscribe to this same topic in the ntfy app on your phone
# e.g. "my-ice-skating-alert-a7x9" — treat it like a password
NTFY_TOPIC = "secret-streatham-ice-skate-alert-b46sm"
 
 
# ──────────────────────────────────────────────
# SCRIPT — you shouldn't need to edit below here
# ──────────────────────────────────────────────
 
def fetch_courses() -> dict:
    """Hit the CourseProgress API and return the JSON response."""
    filter_json = json.dumps(API_FILTER)
    url = f"{API_BASE}?filter={urllib.parse.quote(filter_json)}"
 
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "IceSkatingMonitor/1.0")
 
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())
 
 
def matches_target(name: str) -> bool:
    """Check if a course name matches any of our target strings."""
    name_lower = name.lower()
    return any(t.lower() in name_lower for t in TARGET_COURSES)
 
 
def check_availability(data: dict) -> tuple[list[dict], list[dict]]:
    """Find matching courses. Returns (available, new_but_full)."""
    available = []
    new_but_full = []
 
    # Navigate to the results — the API nests them under resultSet
    result_set = data.get("resultSet", data)
 
    # Results might be grouped or flat
    results = result_set.get("results", [])
    if not results and "grouped" in str(result_set):
        # Try to flatten grouped results
        for group in result_set.values():
            if isinstance(group, list):
                results.extend(group)
 
    for course in results:
        name = course.get("name", "")
 
        # Check if this is a course we care about
        if not matches_target(name):
            continue
 
        spaces = course.get("availability", {}).get("spaces", {})
        free = spaces.get("free", 0)
        total = spaces.get("all", 0)
        occupied = spaces.get("occupied", 0)
 
        schedule = course.get("schedule", {})
        price = course.get("priceIndication", {})
 
        info = {
            "name": name,
            "free_spaces": free,
            "total_spaces": total,
            "occupied": occupied,
            "day": schedule.get("dayOfWeek", "?"),
            "time": schedule.get("timeDescription", "?"),
            "date_desc": schedule.get("dateDescription", "?"),
            "price": f"£{price.get('price', '?')}/{price.get('per', '?')}",
            "course_id": course.get("courseId"),
        }
 
        if free > 0:
            available.append(info)
            print(f"✅ SPACES AVAILABLE: {name} — {free}/{total} free")
        else:
            print(f"❌ Full: {name} — {occupied}/{total} occupied")
            if ALERT_NEW_COURSES:
                new_but_full.append(info)
 
    return available, new_but_full
 
 
def send_notification(hits: list[dict], *, new_course: bool = False):
    """Send a push notification via ntfy.sh."""
    if NTFY_TOPIC == "CHANGE-ME-ice-skating-12345":
        print("⚠️  WARNING: You haven't set your ntfy topic! Edit NTFY_TOPIC in the script.")
        print("   Skipping notification, but here's what would have been sent:")
        for h in hits:
            print(f"   → {h['name']}: {h['free_spaces']} spaces, {h['day']} {h['time']}")
        return
 
    for hit in hits:
        if new_course:
            title = "🆕 New Ice Skating Course Posted!"
            body = (
                f"{hit['name']}\n"
                f"Currently full ({hit['occupied']}/{hit['total_spaces']})\n"
                f"{hit['day']} {hit['time']}\n"
                f"{hit['date_desc']}\n"
                f"{hit['price']}\n\n"
                f"Keep an eye on it — spaces may open up!"
            )
            priority = "default"
        else:
            title = "🧊 Ice Skating Spaces Available!"
            body = (
                f"{hit['name']}\n"
                f"{hit['free_spaces']} space(s) free\n"
                f"{hit['day']} {hit['time']}\n"
                f"{hit['date_desc']}\n"
                f"{hit['price']}\n\n"
                f"Book now before they go!"
            )
            priority = "high"
 
        booking_url = (
            "https://activelambeth.coursepro.co.uk/onlinejoining/classes-results"
            "?filter=%7B%22showFullCourses%22:true,%22region%22:1,"
            "%22courseGroupCategory%22:%5B2%5D,%22centre%22:4%7D"
        )
 
        data = body.encode("utf-8")
        req = urllib.request.Request(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=data,
            method="POST",
        )
        req.add_header("Title", title)
        req.add_header("Priority", priority)
        req.add_header("Tags", "ice_cube,skating")
        req.add_header("Click", booking_url)
 
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print(f"📱 Notification sent for: {hit['name']}")
            else:
                print(f"⚠️  Notification failed (HTTP {resp.status})")
 
 
# File to track which course IDs we've already seen (so we only alert once
# for new courses). GitHub Actions gives us a fresh filesystem each run,
# so this uses the Actions cache or just re-alerts — acceptable for hourly
# checks. For a VPS/local cron setup, this file persists between runs.
SEEN_FILE = ".seen_course_ids.json"
 
 
def load_seen_ids() -> set:
    """Load previously seen course IDs from disk."""
    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()
 
 
def save_seen_ids(ids: set):
    """Save seen course IDs to disk."""
    with open(SEEN_FILE, "w") as f:
        json.dump(list(ids), f)
 
 
def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"🔍 Checking courses at {now}")
    print(f"   Watching for: {TARGET_COURSES}")
    print()
 
    try:
        data = fetch_courses()
    except Exception as e:
        print(f"❌ Failed to fetch course data: {e}")
        sys.exit(1)
 
    available, new_but_full = check_availability(data)
 
    if available:
        print(f"\n🎉 Found {len(available)} course(s) with availability!")
        send_notification(available)
    else:
        print("\n😴 No spaces available yet. Will check again next run.")
 
    # Check for brand-new course postings
    if ALERT_NEW_COURSES and new_but_full:
        seen_ids = load_seen_ids()
        truly_new = [c for c in new_but_full if c["course_id"] not in seen_ids]
 
        if truly_new:
            print(f"\n🆕 {len(truly_new)} new course(s) spotted (full, but newly posted):")
            for c in truly_new:
                print(f"   → {c['name']} ({c['day']} {c['time']})")
            send_notification(truly_new, new_course=True)
 
        # Remember all course IDs we've seen
        all_ids = seen_ids | {c["course_id"] for c in new_but_full}
        all_ids |= {c["course_id"] for c in available}
        save_seen_ids(all_ids)
 
 
if __name__ == "__main__":
    main()