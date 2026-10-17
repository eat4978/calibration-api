# Calibration API

A simple REST API for managing hardware device calibrations. Built with Python, Flask, and SQLite.

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
flask --app app init-db

# 4. (Optional) Seed with sample data
flask --app app seed-db
```

---

## Running

```bash
flask --app app run
```

The server starts at `http://127.0.0.1:5000` and runs in the foreground. **Leave this terminal open** — open a second terminal to run the curl commands in the API Reference section below.

---

## API Reference

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
  "timestamp": "2026-10-17T12:00:00+00:00",
  "username": "alice"
}
```

---

### 2. Add a calibration to a tag

`POST /calibrations/<id>/tags`

The tag is created automatically if it does not already exist.

```bash
curl -s -X POST http://127.0.0.1:5000/calibrations/1/tags \
  -H "Content-Type: application/json" \
  -d '{"tag": "production"}' | python3 -m json.tool
```

**Response (201)**
```json
{
  "calibration_id": 1,
  "tag": "production",
  "time_added": "2026-10-17T12:00:01+00:00"
}
```

Returns **409** if the calibration is already actively in that tag.

---

### 3. Remove a calibration from a tag

`DELETE /calibrations/<id>/tags/<tag_name>`

```bash
curl -s -X DELETE http://127.0.0.1:5000/calibrations/1/tags/production
```

**Response:** `204 No Content`

The removal is recorded with a timestamp; the association history is preserved (see endpoint 5).

---

### 4. Retrieve calibrations by filter

`GET /calibrations`

All query parameters are optional and combine with AND logic.

| Parameter | Description |
|-----------|-------------|
| `user`    | Filter by username |
| `type`    | Filter by calibration type |
| `tag`     | Filter by currently-active tag |
| `start`   | ISO 8601 timestamp — return calibrations at or after this time |
| `end`     | ISO 8601 timestamp — return calibrations at or before this time |

```bash
# All calibrations by alice of type "offset"
curl -s "http://127.0.0.1:5000/calibrations?user=alice&type=offset" | python3 -m json.tool

# All calibrations currently in the "production" tag
curl -s "http://127.0.0.1:5000/calibrations?tag=production" | python3 -m json.tool

# Calibrations created within a time range
curl -s "http://127.0.0.1:5000/calibrations?start=2026-01-01T00:00:00%2B00:00&end=2026-12-31T23:59:59%2B00:00" | python3 -m json.tool

# No filters — return everything
curl -s "http://127.0.0.1:5000/calibrations" | python3 -m json.tool
```

**Response (200):** Array of calibration objects, ordered by timestamp descending.

---

### 5. Query tags for a calibration

`GET /calibrations/<id>/tags`

Returns all tag associations — both active (`time_removed: null`) and historical.

```bash
curl -s http://127.0.0.1:5000/calibrations/1/tags | python3 -m json.tool
```

**Response (200)**
```json
[
  {
    "name": "production",
    "time_added": "2026-10-17T12:00:01+00:00",
    "time_removed": null
  },
  {
    "name": "staging",
    "time_added": "2026-10-16T09:00:00+00:00",
    "time_removed": "2026-10-17T11:00:00+00:00"
  }
]
```

---

## Running Tests

```bash
pytest
```

Tests run against a temporary, isolated SQLite database — no setup required beyond the initial `pip install`.

To see more detail:

```bash
pytest -v
```

---

## Database Schema

```
calibrations
  id               INTEGER PRIMARY KEY AUTOINCREMENT
  calibration_type TEXT
  value            REAL
  timestamp        TEXT  (ISO 8601)
  username         TEXT

tags
  id   INTEGER PRIMARY KEY AUTOINCREMENT
  name TEXT UNIQUE

tags_calibrations
  id             INTEGER PRIMARY KEY AUTOINCREMENT
  tag_id         INTEGER → tags.id
  calibration_id INTEGER → calibrations.id
  time_added     TEXT  (ISO 8601)
  time_removed   TEXT  (ISO 8601, NULL if still active)
```

Tag membership history is tracked via `time_added` / `time_removed` on `tags_calibrations`, so any past state of a tag can be reconstructed by filtering on those timestamps.
