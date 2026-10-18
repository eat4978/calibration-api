# Calibration API

A REST API for managing hardware device calibrations. Built with Python, Flask, and SQLite.

---

## Overview

A **calibration** records a measurement made by a named user at a point in time. Each one has four fields:

| Field | Description |
|-------|-------------|
| `calibration_type` | What was measured (e.g. `offset`, `gain`, `temperature`) |
| `value` | The numeric result |
| `username` | Who performed the calibration |
| `timestamp` | When it was recorded (set automatically, stored in UTC) |

**Tags** are short labels that group calibrations into named states of a device (e.g. `production`, `baseline-2026-q1`). A calibration can belong to any number of tags at once.

**Tag membership is tracked over time.** When you add a calibration to a tag, the association is recorded with a timestamp. When you remove it, the removal is recorded too — the association is never deleted. This means you can always inspect the full history of which calibrations belonged to a tag, and when. Querying a tag by default returns only its *current* members (those not yet removed).

The API exposes five operations:
1. Create a calibration
2. Add a calibration to a tag (tag is created automatically if new)
3. Remove a calibration from a tag (history is preserved)
4. List calibrations, with optional filters by user, type, tag, and time window
5. Retrieve the full tag history for a calibration

For day-to-day use, interact via the `client.py` command-line tool. Raw HTTP examples are in the [API Reference](#api-reference).

---

## Table of Contents

- [Quick Start](#quick-start)
- [How to Test That This Repository Works](#how-to-test-that-this-repository-works)
- [Setup](#setup)
- [Running](#running)
- [Command-line Client](#command-line-client)
- [API Reference](#api-reference)
- [Database Schema](#database-schema)
- [Troubleshooting](#troubleshooting)
- [Feature Requests](#feature-requests)

---

## Quick Start

If you just want to get up and running, these are the only commands you need. For more detail on setup, running, and how the API works, see the sections below.

```bash
git clone <your-repo-url>
cd calibration-api
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m flask --app app init-db
python -m flask --app app seed-db # Optional: adds seed data to database
python -m flask --app app run
```

In a **second terminal**, activate the same environment and verify everything is working:

```bash
source venv/bin/activate
python client.py list
```

If the database is seeded, you should see 15 calibrations.

---

## How to Test That This Repository Works

This section walks through verifying all five use cases end to end. Make sure the server is running in one terminal (`python -m flask --app app run`) and run the following commands in a second terminal.

### Step 0 — Automated test suite

Run the full test suite first. All tests should pass.

```bash
python -m pytest -v
```

Tests run against a temporary, isolated database and do not affect your local data.

### Step 1 — Create a calibration

```bash
python client.py create --type offset --value 1.0 --user alice
```

Expected: a JSON object with an `id`, `calibration_type`, `value`, `timestamp`, and `username`. Note the `id` — you will use it in the steps below (replace `1` if yours differs).

### Step 2 — Add a calibration to a tag

```bash
python client.py add 1 production
```

Expected: confirmation showing `calibration_id`, `tag`, and `time_added`. Try adding it again — you should get a rejection since it is already active in that tag:

```bash
python client.py add 1 production
# → error: Calibration 1 is already in tag 'production'
```

### Step 3 — Remove a calibration from a tag

```bash
python client.py remove 1 production
```

Expected: `Removed calibration 1 from tag 'production'.`

### Step 4 — Filter calibrations

```bash
# All calibrations
python client.py list

# Filter by user
python client.py list --user alice

# Filter by type
python client.py list --type offset

# Filter by tag (only currently-active associations)
python client.py add 1 production   # re-add first
python client.py list --tag production

# Filter by time range (update timestamps to see data)
python client.py list --start 2026-10-18T19:58:56 --end 2026-10-18T19:59:56
```

### Step 5 — Query tags for a calibration

```bash
python client.py tags 1
```

Expected: a list with at least two entries for `production` — one with `time_removed` set (from Step 3) and one active (`time_removed: null`, from when you re-added it in Step 4). This demonstrates that the full history is preserved.

---

## Setup

**Requirements:** Python 3.9+

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize the database
python -m flask --app app init-db

# 4. (Optional) Seed with sample calibration data
python -m flask --app app seed-db
```

---

## Running

```bash
python -m flask --app app run
```

The server starts at `http://127.0.0.1:5000` and runs in the foreground. **Leave this terminal open** — open a second terminal to interact with the API.

---

## Command-line Client

`client.py` provides a simple interface to every endpoint — no curl required.

```bash
# Create a calibration
python client.py create --type offset --value 1.0 --user alice

# Add calibration 1 to a tag (tag is created if it does not exist)
python client.py add 1 production

# Remove calibration 1 from a tag
python client.py remove 1 production

# List calibrations — all filters are optional and combine with AND logic
python client.py list
python client.py list --user alice
python client.py list --type offset --user alice
python client.py list --tag production

python client.py list --start 2026-01-01 --end 2026-12-31

# Show all tag associations for calibration 1 (active and historical)
python client.py tags 1
```

Run `python client.py --help` or `python client.py <command> --help` for full usage.

---

## API Reference

The five endpoints correspond directly to the five use cases above. For day-to-day use, prefer `client.py`. These raw HTTP examples are provided for integration and debugging purposes.

### Input requirements

| Field | Requirement |
|-------|-------------|
| `calibration_type` | Non-empty string |
| `value` | Finite number (rejects `NaN`, `Infinity`, booleans) |
| `username` | Non-empty string |
| `tag` | Non-empty string; any characters allowed. Normalized to lowercase, so tags are case-insensitive. |
| `start` / `end` | ISO 8601 timestamp (see filter notes below) |

Invalid input returns a `400` with a descriptive message.

### 1. Create a calibration

`POST /calibrations`

```bash
curl -s -X POST http://127.0.0.1:5000/calibrations \
  -H "Content-Type: application/json" \
  -d '{"calibration_type": "offset", "value": 1.0, "username": "alice"}' | python3 -m json.tool
```

**Response (201)**
```json
{
  "id": 1,
  "calibration_type": "offset",
  "value": 1.0,
  "timestamp": "2026-10-17T16:30:00+00:00",
  "username": "alice"
}
```

### 2. Add a calibration to a tag

`POST /calibrations/{id}/tags`

The tag is created automatically if it does not already exist. Returns **409** if the calibration is already actively in that tag.

```bash
curl -s -X POST http://127.0.0.1:5000/calibrations/1/tags \
  -H "Content-Type: application/json" \
  -d '{"tag": "production"}' | python3 -m json.tool
```

### 3. Remove a calibration from a tag

`DELETE /calibrations/{id}/tags/{tag_name}`

The removal is recorded with a timestamp; the association history is preserved.

```bash
curl -s -X DELETE http://127.0.0.1:5000/calibrations/1/tags/production
```

**Response:** `204 No Content`

### 4. Retrieve calibrations by filter

`GET /calibrations`

| Parameter | Description |
|-----------|-------------|
| `user`    | Filter by username |
| `type`    | Filter by calibration type |
| `tag`     | Filter by currently-active tag |
| `start`   | ISO 8601 timestamp — return calibrations at or after this time |
| `end`     | ISO 8601 timestamp — return calibrations at or before this time |

All parameters are optional and combine with AND logic. Timestamps may be given
in any timezone (e.g. `2026-01-01T09:30:00-05:00`) or with none at all
(`2026-01-01`, interpreted as UTC); they are normalized to UTC before filtering.
An unparseable `start`/`end` returns a `400`.

```bash
curl -s "http://127.0.0.1:5000/calibrations?user=alice&type=offset" | python3 -m json.tool
```

### 5. Query tags for a calibration

`GET /calibrations/{id}/tags`

Returns all tag associations — both active (`time_removed: null`) and historical.

```bash
curl -s http://127.0.0.1:5000/calibrations/1/tags | python3 -m json.tool
```

---

## Database Schema

```
calibrations
  id               INTEGER PRIMARY KEY AUTOINCREMENT
  calibration_type TEXT
  value            REAL
  timestamp        TEXT  (ISO 8601, UTC)
  username         TEXT

tags
  id   INTEGER PRIMARY KEY AUTOINCREMENT
  name TEXT UNIQUE

tags_calibrations
  id             INTEGER PRIMARY KEY AUTOINCREMENT
  tag_id         INTEGER → tags.id
  calibration_id INTEGER → calibrations.id
  time_added     TEXT  (ISO 8601, UTC)
  time_removed   TEXT  (ISO 8601, UTC — NULL if still active)
```

Tag membership history is preserved via `time_added` / `time_removed` on `tags_calibrations`, so the state of any tag at any past point in time can be reconstructed.

---

## Troubleshooting

**Quick questions:** Open a discussion in the **Q&A** category under the Discussions tab.

**Bug reports:** Open an issue under the Issues tab with:
- What you ran (exact command)
- What you expected to happen
- What actually happened (include any error messages or unexpected output)

**Common issues:**

| Symptom | Fix |
|--------|-----|
| `Could not reach the server` | Start the server first: `python -m flask --app app run` |
| `Could not reach the server` (server is running) | Use `127.0.0.1` instead of `localhost` — common on macOS |
| Server is on a different host or port | Set `CALIBRATION_API_URL=http://<host>:<port>` before running `client.py` |
| `No module named 'flask'` | Activate the virtual environment: `source venv/bin/activate` |
| `sqlite3.OperationalError: no such table` | Run `python -m flask --app app init-db` |

---

## Feature Requests

Feature requests are tracked via GitHub Discussions — this keeps the issue tracker focused on bugs while giving ideas room to breathe, gather feedback, and be voted on.

To suggest a feature:
1. Go to the **Discussions** tab.
2. Click **New discussion** and choose the **Ideas** category.
3. Describe what you need and why — the more context, the better.
