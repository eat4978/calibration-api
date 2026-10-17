"""
Command-line client for the Calibration API.

Usage examples:
  python client.py create --type offset --value 1.0 --user alice
  python client.py add 1 production
  python client.py remove 1 production
  python client.py list --user alice --type offset
  python client.py list --tag production --start 2026-01-01
  python client.py tags 1
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "http://127.0.0.1:5000"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _request(method, path, body=None, params=None):
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})

    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw) if raw else {"error": e.reason}
    except urllib.error.URLError as e:
        print(f"Could not reach the server at {BASE_URL}. Is it running?")
        sys.exit(1)


def _print(data):
    print(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_create(args):
    status, data = _request("POST", "/calibrations", body={
        "calibration_type": args.type,
        "value": args.value,
        "username": args.user,
    })
    _print(data)
    sys.exit(0 if status == 201 else 1)


def cmd_add(args):
    status, data = _request("POST", f"/calibrations/{args.id}/tags", body={"tag": args.tag})
    _print(data)
    sys.exit(0 if status == 201 else 1)


def cmd_remove(args):
    tag = urllib.parse.quote(args.tag, safe="")
    status, data = _request("DELETE", f"/calibrations/{args.id}/tags/{tag}")
    if status == 204:
        print(f"Removed calibration {args.id} from tag '{args.tag}'.")
    else:
        _print(data)
    sys.exit(0 if status == 204 else 1)


def cmd_list(args):
    status, data = _request("GET", "/calibrations", params={
        "user":  args.user,
        "type":  args.type,
        "tag":   args.tag,
        "start": args.start,
        "end":   args.end,
    })
    if status == 200 and not data:
        print("No calibrations found matching those filters.")
    else:
        _print(data)
    sys.exit(0 if status == 200 else 1)


def cmd_tags(args):
    status, data = _request("GET", f"/calibrations/{args.id}/tags")
    if status == 200 and not data:
        print(f"Calibration {args.id} has no tag associations.")
    else:
        _print(data)
    sys.exit(0 if status == 200 else 1)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Calibration API command-line client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # create
    p_create = sub.add_parser("create", help="Create a new calibration")
    p_create.add_argument("--type",  required=True, metavar="TYPE",     help="Calibration type (e.g. offset, gain)")
    p_create.add_argument("--value", required=True, metavar="VALUE",    help="Numeric value", type=float)
    p_create.add_argument("--user",  required=True, metavar="USERNAME", help="Username")
    p_create.set_defaults(func=cmd_create)

    # add
    p_add = sub.add_parser("add", help="Add a calibration to a tag")
    p_add.add_argument("id",  type=int, help="Calibration ID")
    p_add.add_argument("tag", help="Tag name")
    p_add.set_defaults(func=cmd_add)

    # remove
    p_remove = sub.add_parser("remove", help="Remove a calibration from a tag")
    p_remove.add_argument("id",  type=int, help="Calibration ID")
    p_remove.add_argument("tag", help="Tag name")
    p_remove.set_defaults(func=cmd_remove)

    # list
    p_list = sub.add_parser("list", help="List calibrations (with optional filters)")
    p_list.add_argument("--user",  metavar="USERNAME", help="Filter by username")
    p_list.add_argument("--type",  metavar="TYPE",     help="Filter by calibration type")
    p_list.add_argument("--tag",   metavar="TAG",      help="Filter by currently-active tag")
    p_list.add_argument("--start", metavar="DATETIME", help="Return calibrations at or after this ISO 8601 timestamp")
    p_list.add_argument("--end",   metavar="DATETIME", help="Return calibrations at or before this ISO 8601 timestamp")
    p_list.set_defaults(func=cmd_list)

    # tags
    p_tags = sub.add_parser("tags", help="List tags for a calibration")
    p_tags.add_argument("id", type=int, help="Calibration ID")
    p_tags.set_defaults(func=cmd_tags)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
