"""
Ice skating course availability monitor.

Checks the Active Lambeth (CourseProgress) booking API for open spaces on
selected courses and sends a push notification via ntfy.sh.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


# --- Configuration ---

API_BASE = "https://activelambeth.coursepro.co.uk/portal/api/HomePortal/booking/search"

API_FILTER = {
    "showFullCourses": True,
    "region": 1,
    "courseGroupCategory": [2],  # Ice Skating
    "centre": 4,                 # Streatham Ice and Leisure Centre
    "offset": 0,
    "limit": 20,
}

BOOKING_URL = (
    "https://activelambeth.coursepro.co.uk/onlinejoining/classes-results"
    "?filter=%7B%22showFullCourses%22:true,%22region%22:1,"
    "%22courseGroupCategory%22:%5B2%5D,%22centre%22:4%7D"
)

# Case-insensitive substring match against course names.
TARGET_COURSES = [
    "Level 1&2 (Adults Only)",
    "Level 2 (Adults",
    "Level 1 & 2 (All Ages)",
    "Level 2 (All Ages)",
    "Level 3 (Adults",
    "Level 3 (All Ages)",
]

# Also notify once when a matching course is first posted, even if full.
ALERT_NEW_COURSES = True

# Treat the topic like a password: anyone who knows it can read your alerts.
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

# Course IDs already alerted on as new. Only persists between runs if the
# file is committed back or the script runs somewhere with a stable disk.
SEEN_FILE = ".seen_course_ids.json"


# --- Script ---

def fetch_courses() -> dict:
    filter_json = json.dumps(API_FILTER)
    url = f"{API_BASE}?filter={urllib.parse.quote(filter_json)}"

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "IceSkatingMonitor/1.0")

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def matches_target(name: str) -> bool:
    name_lower = name.lower()
    return any(t.lower() in name_lower for t in TARGET_COURSES)


def check_availability(data: dict) -> tuple[list[dict], list[dict]]:
    """Return (available, full) lists of matching courses."""
    available = []
    full = []

    result_set = data.get("resultSet", data)
    results = result_set.get("results", [])
    if not results and "grouped" in str(result_set):
        for group in result_set.values():
            if isinstance(group, list):
                results.extend(group)

    for course in results:
        name = course.get("name", "")
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
            print(f"Available: {name} ({free}/{total} free)")
        else:
            full.append(info)
            print(f"Full: {name} ({occupied}/{total} occupied)")

    return available, full


def send_notification(hits: list[dict], *, new_course: bool = False):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC not set; skipping notification. Would have sent:")
        for h in hits:
            print(f"  - {h['name']}: {h['free_spaces']} spaces, {h['day']} {h['time']}")
        return

    for hit in hits:
        if new_course:
            title = "New Ice Skating Course Posted"
            body = (
                f"{hit['name']}\n"
                f"Currently full ({hit['occupied']}/{hit['total_spaces']})\n"
                f"{hit['day']} {hit['time']}\n"
                f"{hit['date_desc']}\n"
                f"{hit['price']}\n\n"
                f"Keep an eye on it, spaces may open up."
            )
            priority = "default"
        else:
            title = "Ice Skating Spaces Available"
            body = (
                f"{hit['name']}\n"
                f"{hit['free_spaces']} space(s) free\n"
                f"{hit['day']} {hit['time']}\n"
                f"{hit['date_desc']}\n"
                f"{hit['price']}\n\n"
                f"Book now before they go."
            )
            priority = "high"

        req = urllib.request.Request(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            method="POST",
        )
        req.add_header("Title", title)
        req.add_header("Priority", priority)
        req.add_header("Tags", "ice_cube,skating")
        req.add_header("Click", BOOKING_URL)

        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print(f"Notification sent for: {hit['name']}")
            else:
                print(f"Notification failed (HTTP {resp.status})")


def load_seen_ids() -> set:
    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen_ids(ids: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(ids), f)


def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"Checking courses at {now}")
    print(f"Watching for: {TARGET_COURSES}")
    print()

    try:
        data = fetch_courses()
    except urllib.error.HTTPError as e:
        print(f"HTTP error {e.code}: {e.reason}")
        print(f"  URL: {API_BASE}")
        body = e.read().decode(errors="replace")[:500]
        if body:
            print(f"  Response body: {body}")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to fetch course data: {type(e).__name__}: {e}")
        sys.exit(1)

    available, full = check_availability(data)

    if available:
        print(f"\nFound {len(available)} course(s) with availability.")
        send_notification(available)
    else:
        print("\nNo spaces available.")

    if ALERT_NEW_COURSES:
        seen_ids = load_seen_ids()
        new = [c for c in full if c["course_id"] not in seen_ids]

        if new:
            print(f"\n{len(new)} new course(s) posted (currently full):")
            for c in new:
                print(f"  - {c['name']} ({c['day']} {c['time']})")
            send_notification(new, new_course=True)

        save_seen_ids(seen_ids | {c["course_id"] for c in available + full})


if __name__ == "__main__":
    main()
