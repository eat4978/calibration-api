"""
Tests for the five use cases described in the assignment:
  1. Create a calibration
  2. Add a calibration to a tag
  3. Remove a calibration from a tag
  4. Retrieve calibrations by filter (user, type, time range, tag)
  5. Query tags for a calibration
"""

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_calibration(client, cal_type="offset", value=1.0, username="alice"):
    resp = client.post("/calibrations", json={
        "calibration_type": cal_type,
        "value": value,
        "username": username,
    })
    assert resp.status_code == 201
    return resp.get_json()


# ---------------------------------------------------------------------------
# 1. Create a calibration
# ---------------------------------------------------------------------------

class TestCreateCalibration:
    def test_returns_201_with_all_fields(self, client):
        resp = client.post("/calibrations", json={
            "calibration_type": "offset",
            "value": 1.0,
            "username": "alice",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["calibration_type"] == "offset"
        assert data["value"] == 1.0
        assert data["username"] == "alice"
        assert "id" in data
        assert "timestamp" in data

    def test_missing_field_returns_400(self, client):
        resp = client.post("/calibrations", json={"calibration_type": "gain"})
        assert resp.status_code == 400

    def test_non_numeric_value_returns_400(self, client):
        resp = client.post("/calibrations", json={
            "calibration_type": "gain",
            "value": "not-a-number",
            "username": "bob",
        })
        assert resp.status_code == 400

    def test_each_calibration_gets_unique_id(self, client):
        a = make_calibration(client)
        b = make_calibration(client)
        assert a["id"] != b["id"]

    def test_nan_value_returns_400(self, client):
        resp = client.post("/calibrations", json={
            "calibration_type": "offset", "value": float("nan"), "username": "a",
        })
        assert resp.status_code == 400

    def test_infinity_value_returns_400(self, client):
        resp = client.post("/calibrations", json={
            "calibration_type": "offset", "value": float("inf"), "username": "a",
        })
        assert resp.status_code == 400

    def test_boolean_value_returns_400(self, client):
        resp = client.post("/calibrations", json={
            "calibration_type": "offset", "value": True, "username": "a",
        })
        assert resp.status_code == 400

    def test_non_string_type_returns_400(self, client):
        resp = client.post("/calibrations", json={
            "calibration_type": 123, "value": 1.0, "username": "a",
        })
        assert resp.status_code == 400

    def test_non_string_username_returns_400(self, client):
        resp = client.post("/calibrations", json={
            "calibration_type": "offset", "value": 1.0, "username": ["a"],
        })
        assert resp.status_code == 400

    def test_empty_string_fields_return_400(self, client):
        resp = client.post("/calibrations", json={
            "calibration_type": "", "value": 1.0, "username": "",
        })
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 2. Add a calibration to a tag
# ---------------------------------------------------------------------------

class TestAddToTag:
    def test_returns_201_on_success(self, client):
        cal = make_calibration(client)
        resp = client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "production"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["tag"] == "production"
        assert data["calibration_id"] == cal["id"]
        assert "time_added" in data

    def test_tag_is_created_implicitly(self, client):
        cal = make_calibration(client)
        client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "brand-new-tag"})
        tags = client.get(f"/calibrations/{cal['id']}/tags").get_json()
        assert any(t["name"] == "brand-new-tag" for t in tags)

    def test_duplicate_active_returns_409(self, client):
        cal = make_calibration(client)
        client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "staging"})
        resp = client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "staging"})
        assert resp.status_code == 409

    def test_nonexistent_calibration_returns_404(self, client):
        resp = client.post("/calibrations/9999/tags", json={"tag": "test"})
        assert resp.status_code == 404

    def test_missing_tag_field_returns_400(self, client):
        cal = make_calibration(client)
        resp = client.post(f"/calibrations/{cal['id']}/tags", json={})
        assert resp.status_code == 400

    def test_non_string_tag_returns_400(self, client):
        cal = make_calibration(client)
        resp = client.post(f"/calibrations/{cal['id']}/tags", json={"tag": 123})
        assert resp.status_code == 400

    def test_whitespace_only_tag_returns_400(self, client):
        cal = make_calibration(client)
        resp = client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "   "})
        assert resp.status_code == 400

    def test_out_of_range_calibration_id_returns_404(self, client):
        # Larger than SQLite's signed-64-bit max; must not 500.
        resp = client.post("/calibrations/99999999999999999999999/tags", json={"tag": "x"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. Remove a calibration from a tag
# ---------------------------------------------------------------------------

class TestRemoveFromTag:
    def test_returns_204_on_success(self, client):
        cal = make_calibration(client)
        client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "dev"})
        resp = client.delete(f"/calibrations/{cal['id']}/tags/dev")
        assert resp.status_code == 204

    def test_association_becomes_inactive(self, client):
        cal = make_calibration(client)
        client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "dev"})
        client.delete(f"/calibrations/{cal['id']}/tags/dev")
        tags = client.get(f"/calibrations/{cal['id']}/tags").get_json()
        dev = next(t for t in tags if t["name"] == "dev")
        assert dev["time_removed"] is not None

    def test_removing_nonexistent_association_returns_404(self, client):
        cal = make_calibration(client)
        resp = client.delete(f"/calibrations/{cal['id']}/tags/does-not-exist")
        assert resp.status_code == 404

    def test_readd_after_remove_is_allowed(self, client):
        cal = make_calibration(client)
        client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "cycle"})
        client.delete(f"/calibrations/{cal['id']}/tags/cycle")
        resp = client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "cycle"})
        assert resp.status_code == 201

    def test_tag_with_slash_round_trips(self, client):
        """Tags may contain slashes; the DELETE route uses <path:> to match them."""
        cal = make_calibration(client)
        assert client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "a/b/c"}).status_code == 201
        assert client.delete(f"/calibrations/{cal['id']}/tags/a/b/c").status_code == 204
        tags = client.get(f"/calibrations/{cal['id']}/tags").get_json()
        assert next(t for t in tags if t["name"] == "a/b/c")["time_removed"] is not None

    def test_tag_is_stored_lowercase(self, client):
        cal = make_calibration(client)
        resp = client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "Production"})
        assert resp.get_json()["tag"] == "production"
        tags = client.get(f"/calibrations/{cal['id']}/tags").get_json()
        assert tags[0]["name"] == "production"

    def test_tag_matching_is_case_insensitive(self, client):
        """Adding, filtering, and removing all normalize case, so a tag added as
        'Prod' is the same tag as 'prod'."""
        cal = make_calibration(client)
        client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "Prod"})

        # Duplicate in different case is rejected (same tag).
        dup = client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "PROD"})
        assert dup.status_code == 409

        # Filtering by any case finds it.
        found = client.get("/calibrations?tag=pRoD").get_json()
        assert any(c["id"] == cal["id"] for c in found)

        # Removing by any case works.
        assert client.delete(f"/calibrations/{cal['id']}/tags/PrOd").status_code == 204

    def test_history_preserved_after_readd(self, client):
        cal = make_calibration(client)
        client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "cycle"})
        client.delete(f"/calibrations/{cal['id']}/tags/cycle")
        client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "cycle"})
        tags = client.get(f"/calibrations/{cal['id']}/tags").get_json()
        cycle_entries = [t for t in tags if t["name"] == "cycle"]
        assert len(cycle_entries) == 2


# ---------------------------------------------------------------------------
# 4. Retrieve calibrations by filter
# ---------------------------------------------------------------------------

class TestGetCalibrations:
    @pytest.fixture(autouse=True)
    def seed(self, client):
        self.alice_offset = make_calibration(client, "offset", 1.0, "alice")
        self.alice_gain   = make_calibration(client, "gain",   1.5, "alice")
        self.bob_gain     = make_calibration(client, "gain",   1.4, "bob")
        self.bob_temp     = make_calibration(client, "temperature", -0.3, "bob")

        # Add some to tags
        client.post(f"/calibrations/{self.alice_offset['id']}/tags", json={"tag": "production"})
        client.post(f"/calibrations/{self.bob_gain['id']}/tags",     json={"tag": "production"})

        self.client = client

    def test_no_filters_returns_all(self, client):
        resp = client.get("/calibrations")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 4

    def test_filter_by_user(self, client):
        resp = client.get("/calibrations?user=alice")
        data = resp.get_json()
        assert len(data) == 2
        assert all(c["username"] == "alice" for c in data)

    def test_filter_by_type(self, client):
        resp = client.get("/calibrations?type=gain")
        data = resp.get_json()
        assert len(data) == 2
        assert all(c["calibration_type"] == "gain" for c in data)

    def test_filter_by_tag(self, client):
        resp = client.get("/calibrations?tag=production")
        data = resp.get_json()
        assert len(data) == 2
        ids = {c["id"] for c in data}
        assert self.alice_offset["id"] in ids
        assert self.bob_gain["id"] in ids

    def test_filter_by_user_and_type(self, client):
        resp = client.get("/calibrations?user=alice&type=gain")
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["id"] == self.alice_gain["id"]

    def test_filter_by_start_time(self, client):
        future = "2099-01-01T00:00:00+00:00"
        resp = client.get(f"/calibrations?start={future}")
        assert resp.get_json() == []

    def test_filter_by_end_time(self, client):
        past = "2000-01-01T00:00:00+00:00"
        resp = client.get(f"/calibrations?end={past}")
        assert resp.get_json() == []

    def test_removed_tag_not_returned(self, client):
        client.delete(f"/calibrations/{self.alice_offset['id']}/tags/production")
        resp = client.get("/calibrations?tag=production")
        ids = {c["id"] for c in resp.get_json()}
        assert self.alice_offset["id"] not in ids


# ---------------------------------------------------------------------------
# 5. Query tags for a calibration
# ---------------------------------------------------------------------------

class TestGetTagsForCalibration:
    def test_returns_empty_list_when_no_tags(self, client):
        cal = make_calibration(client)
        resp = client.get(f"/calibrations/{cal['id']}/tags")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_active_tag(self, client):
        cal = make_calibration(client)
        client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "staging"})
        tags = client.get(f"/calibrations/{cal['id']}/tags").get_json()
        assert len(tags) == 1
        assert tags[0]["name"] == "staging"
        assert tags[0]["time_removed"] is None

    def test_returns_multiple_tags(self, client):
        cal = make_calibration(client)
        client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "a"})
        client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "b"})
        tags = client.get(f"/calibrations/{cal['id']}/tags").get_json()
        assert {t["name"] for t in tags} == {"a", "b"}

    def test_includes_historical_associations(self, client):
        cal = make_calibration(client)
        client.post(f"/calibrations/{cal['id']}/tags", json={"tag": "old"})
        client.delete(f"/calibrations/{cal['id']}/tags/old")
        tags = client.get(f"/calibrations/{cal['id']}/tags").get_json()
        old = next(t for t in tags if t["name"] == "old")
        assert old["time_removed"] is not None

    def test_nonexistent_calibration_returns_404(self, client):
        resp = client.get("/calibrations/9999/tags")
        assert resp.status_code == 404

    def test_out_of_range_calibration_id_returns_404(self, client):
        resp = client.get("/calibrations/99999999999999999999999/tags")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Timestamp / timezone handling in the time filter
# ---------------------------------------------------------------------------

class TestTimeFilter:
    def test_timestamps_are_stored_in_utc(self, client):
        cal = make_calibration(client)
        assert cal["timestamp"].endswith("+00:00")

    def test_tz_aware_filter_matches_same_instant(self, client):
        """A filter expressed in a non-UTC offset must compare by instant,
        not by the raw string, so the equivalent UTC moment still matches."""
        make_calibration(client)
        # Far-future in UTC, but written with a +14:00 offset so the naive
        # string would sort *earlier* than a UTC string. Instant-wise it is
        # still in the future, so nothing should match.
        resp = client.get("/calibrations?start=2099-01-01T00:00:00+14:00")
        assert resp.get_json() == []

        # Far-past expressed with a -12:00 offset: instant is still the past,
        # everything should match regardless of the lexical offset ordering.
        resp = client.get("/calibrations?start=2000-01-01T00:00:00-12:00")
        assert len(resp.get_json()) == 1

    def test_z_suffix_is_accepted(self, client):
        make_calibration(client)
        resp = client.get("/calibrations?end=2000-01-01T00:00:00Z")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_date_only_is_accepted(self, client):
        make_calibration(client)
        resp = client.get("/calibrations?start=2000-01-01")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 1

    def test_invalid_timestamp_returns_400(self, client):
        resp = client.get("/calibrations?start=not-a-date")
        assert resp.status_code == 400

    def test_invalid_end_timestamp_returns_400(self, client):
        resp = client.get("/calibrations?end=2026-13-99")
        assert resp.status_code == 400
