"""Room Booker API - single Lambda behind CloudFront (Origin Access Control -> IAM-auth Function URL).

Sessions
  POST /api/session {"email": "name@prudential.com"}   employee session (trust-based: the address
                                                       is checked for the company domain, not proven)
  POST /api/session {"guest": true, "name": "Ana"}    guest session with a random, unguessable id
  Both return an HS256-signed session token; every other route except /api/config requires it in
  X-Auth-Token. (Authorization can't be used: CloudFront's OAC signs the origin request with it.)

Routes (CloudFront forwards /api/* unchanged)
  GET    /api/config                            public: rooms (capacity, features), slots, limits
  GET    /api/me                                current user, their upcoming bookings and quota
  GET    /api/bookings[?date=YYYY-MM-DD]        bookings for a day, or all upcoming
  POST   /api/bookings                          create {date, room, slot, title, attendees, needsAv}
  PATCH  /api/bookings/{date}/{room}/{slot}     change the meeting title (owner only)
  DELETE /api/bookings/{date}/{room}/{slot}     cancel the booking (owner only)

Table design (single table, on-demand)
  Booking:  pk = "YYYY-MM-DD", sk = "ROOM#HH:MM"        conditional put makes double booking impossible
            gsi1pk = "BOOKING", gsi1sk = "date#slot#room"   index "upcoming" (no table scans)
  Owner:    pk = "USER#<sub>", sk = "PROFILE"           active = {bookingKey: date}, version
            Quota: the booking and the owner item are written in ONE transaction conditioned on the
            version read, so concurrent requests can't both take the last slot.
  Rate:     pk = "RATE#<scope>", sk = window            fixed-window counters, TTL-expired
"""
import base64
import datetime as dt
import hashlib
import json
import logging
import os
import re
import secrets
import time
from urllib.parse import unquote

import boto3
import jwt
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

log = logging.getLogger()
log.setLevel(logging.INFO)

TABLE_NAME = os.environ["TABLE_NAME"]
TABLE = boto3.resource("dynamodb").Table(TABLE_NAME)
DDB = TABLE.meta.client   # resource-backed client: takes plain Python values, not {"S": ...}
SESSION_SECRET = os.environ["SESSION_SECRET"]
EMPLOYEE_DOMAIN = os.environ.get("EMPLOYEE_EMAIL_DOMAIN", "prudential.com").lower()
MAX_ACTIVE = {
    "employee": int(os.environ.get("MAX_ACTIVE_PER_EMPLOYEE", "3")),
    "guest": int(os.environ.get("MAX_ACTIVE_PER_GUEST", "1")),
}
SESSION_HOURS = {"employee": 12, "guest": 24 * 7}
WRITE_RATE_LIMIT = int(os.environ.get("WRITE_RATE_LIMIT", "20"))
GUEST_SESSIONS_PER_HOUR = int(os.environ.get("GUEST_SESSIONS_PER_HOUR", "5"))
TOKEN_ISSUER = "room-booker"

ROOMS = {
    "Fuji":        {"capacity": 4,  "floor": "Level 11", "av": True,  "features": ["TV screen", "Whiteboard"]},
    "Kilimanjaro": {"capacity": 6,  "floor": "Level 12", "av": False, "features": ["Whiteboard", "Natural light"]},
    "Denali":      {"capacity": 8,  "floor": "Level 12", "av": True,  "features": ["TV screen", "Video conferencing"]},
    "Everest":     {"capacity": 12, "floor": "Level 12", "av": True,  "features": ["TV screen", "Video conferencing", "Whiteboard"]},
    "Matterhorn":  {"capacity": 20, "floor": "Level 10", "av": True,  "features": ["Video wall", "Video conferencing", "Speakerphone"]},
    "Olympus":     {"capacity": 40, "floor": "Level 3",  "av": True,  "features": ["Projector", "Video conferencing", "Stage mic"]},
}
MAX_CAPACITY = max(r["capacity"] for r in ROOMS.values())
SLOTS = tuple(f"{h:02d}:00" for h in range(8, 18))  # 08:00 .. 17:00, one-hour slots
MAX_DAYS_AHEAD = 60
HISTORY_DAYS = 30          # past bookings shown under "My bookings"
RETAIN_DAYS = 90           # TTL: bookings are deleted this long after their date
MAX_BODY_BYTES = 2048
MAX_TITLE = 100
MAX_GUEST_NAME = 40
API_PREFIX = "api"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EMAIL_LOCAL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._%+-]{0,62}[a-z0-9])?$")
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class ApiError(Exception):
    def __init__(self, status, message, code=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(body),
    }


# ---------- request helpers ----------

def headers_of(event):
    return {k.lower(): v for k, v in (event.get("headers") or {}).items()}


def read_json(event):
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8", errors="replace")
    if len(raw.encode("utf-8")) > MAX_BODY_BYTES:
        raise ApiError(413, "request body too large")
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        raise ApiError(400, "body must be valid JSON")
    if not isinstance(data, dict):
        raise ApiError(400, "body must be a JSON object")
    return data


def client_ip(event):
    """Real viewer IP. Behind CloudFront, sourceIp is an edge server, so prefer the header
    CloudFront sets itself (format "ip:port"; viewers cannot spoof it)."""
    addr = headers_of(event).get("cloudfront-viewer-address")
    if addr and ":" in addr:
        return addr.rsplit(":", 1)[0]
    return event.get("requestContext", {}).get("http", {}).get("sourceIp", "unknown")


def ip_scope(event):
    return "IP#" + hashlib.sha256(client_ip(event).encode()).hexdigest()[:32]   # raw IPs never stored


def rate_limit(scope, limit, window_seconds, message):
    """Fixed-window counter: at most `limit` hits per scope per window."""
    window = int(time.time()) // window_seconds
    try:
        TABLE.update_item(
            Key={"pk": f"RATE#{scope}", "sk": f"{window_seconds}:{window}"},
            UpdateExpression="ADD hits :one SET expiresAt = if_not_exists(expiresAt, :exp)",
            ConditionExpression="attribute_not_exists(hits) OR hits < :limit",
            ExpressionAttributeValues={":one": 1, ":limit": limit, ":exp": (window + 2) * window_seconds},
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ApiError(429, message, "rate")
        raise


def enforce_write_rate_limit(user, event):
    msg = "too many changes, please try again in a few minutes"
    rate_limit(user["sub"], WRITE_RATE_LIMIT, 600, msg)
    if user["kind"] == "guest":            # guests can mint new ids, so also limit their network
        rate_limit(ip_scope(event), WRITE_RATE_LIMIT, 600, msg)


# ---------- validation ----------

def today():
    return dt.datetime.now(dt.timezone.utc).date()


def active_cutoff():
    # One day of grace: the browser picks dates in the user's local timezone,
    # which can be a calendar day behind UTC.
    return today() - dt.timedelta(days=1)


def parse_date(value, *, allow_past=False):
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise ApiError(400, "date must be YYYY-MM-DD")
    try:
        day = dt.date.fromisoformat(value)
    except ValueError:
        raise ApiError(400, "date is not a real calendar date")
    if not allow_past:
        if day < active_cutoff():
            raise ApiError(400, "date is in the past")
        if day > today() + dt.timedelta(days=MAX_DAYS_AHEAD):
            raise ApiError(400, f"bookings open at most {MAX_DAYS_AHEAD} days ahead")
    return day


def parse_room(value):
    if value not in ROOMS:
        raise ApiError(400, f"room must be one of {', '.join(ROOMS)}")
    return value


def parse_slot(value):
    if value not in SLOTS:
        raise ApiError(400, f"slot must be one of {SLOTS[0]}..{SLOTS[-1]} on the hour")
    return value


def clean_text(value, field, max_len):
    if not isinstance(value, str):
        raise ApiError(400, f"{field} is required")
    value = CONTROL_CHARS.sub("", value).strip()
    if not value:
        raise ApiError(400, f"{field} is required")
    if len(value) > max_len:
        raise ApiError(400, f"{field} must be at most {max_len} characters")
    return value


def parse_attendees(value, room):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_CAPACITY:
        raise ApiError(400, f"attendees must be a whole number from 1 to {MAX_CAPACITY}")
    if value > ROOMS[room]["capacity"]:
        raise ApiError(400, f"{room} seats {ROOMS[room]['capacity']}; choose a bigger room for {value} people", "capacity")
    return value


def parse_employee_email(value):
    if not isinstance(value, str):
        raise ApiError(400, f"enter your @{EMPLOYEE_DOMAIN} email address", "domain")
    email = value.strip().lower()
    local, sep, domain = email.rpartition("@")
    if not sep or domain != EMPLOYEE_DOMAIN or not EMAIL_LOCAL_RE.match(local) or ".." in local:
        raise ApiError(400, f"use your @{EMPLOYEE_DOMAIN} email address", "domain")
    return email


def name_from_email(email):
    """ana.lim@prudential.com -> "Ana Lim"."""
    words = [w for w in re.split(r"[._+-]+", email.split("@")[0]) if w and not w.isdigit()]
    return (" ".join(w.capitalize() for w in words) or email.split("@")[0])[:50]


# ---------- sessions ----------

def issue_token(user):
    now = int(time.time())
    claims = {**user, "iss": TOKEN_ISSUER, "iat": now, "exp": now + SESSION_HOURS[user["kind"]] * 3600}
    return jwt.encode(claims, SESSION_SECRET, algorithm="HS256")


def authenticate(event):
    token = headers_of(event).get("x-auth-token", "")
    if not token or len(token) > 4096:
        raise ApiError(401, "please sign in or continue as a guest", "auth")
    try:
        claims = jwt.decode(token, SESSION_SECRET, algorithms=["HS256"], issuer=TOKEN_ISSUER,
                            options={"require": ["exp", "iat", "iss", "sub"]})
    except jwt.InvalidTokenError as e:
        log.info("rejected token", extra={"reason": type(e).__name__})
        raise ApiError(401, "your session has expired, please sign in again", "auth")
    if claims.get("kind") not in MAX_ACTIVE:
        raise ApiError(401, "please sign in again", "auth")
    return {"sub": claims["sub"], "kind": claims["kind"], "name": claims.get("name", ""), "email": claims.get("email", "")}


def user_summary(user):
    return {"name": user["name"], "email": user["email"], "kind": user["kind"], "maxActive": MAX_ACTIVE[user["kind"]]}


def create_session(event):
    data = read_json(event)
    if data.get("guest") is True:
        name = clean_text(data.get("name"), "name", MAX_GUEST_NAME)
        rate_limit(ip_scope(event), GUEST_SESSIONS_PER_HOUR, 3600,
                   "too many guest sessions from your network, please try again later")
        user = {"sub": "guest:" + secrets.token_urlsafe(18), "kind": "guest", "name": name, "email": ""}
    else:
        email = parse_employee_email(data.get("email"))
        user = {"sub": "emp:" + email, "kind": "employee", "name": name_from_email(email), "email": email}
    return respond(201, {"token": issue_token(user), "user": user_summary(user)})


# ---------- bookings ----------

def booking_key(date, room, slot):
    return f"{date}|{room}|{slot}"


def owner_key(user):
    return {"pk": f"USER#{user['sub']}", "sk": "PROFILE"}


def public_view(item, user):
    """Never expose owner ids or emails - only the display name and whether it's yours."""
    room, slot = item["sk"].split("#", 1)
    return {
        "date": item["pk"],
        "room": room,
        "slot": slot,
        "name": item["ownerName"],
        "guest": item.get("ownerKind") == "guest",
        "title": item["title"],
        "attendees": int(item.get("attendees", 0)) or None,
        "mine": item.get("ownerSub") == user["sub"],
        "createdAt": item.get("createdAt"),
        "updatedAt": item.get("updatedAt"),
    }


def sort_bookings(views):
    return sorted(views, key=lambda b: (b["date"], b["slot"], b["room"]))


def upcoming_items(**filter_kwargs):
    kwargs = {
        "IndexName": "upcoming",
        "KeyConditionExpression": Key("gsi1pk").eq("BOOKING") & Key("gsi1sk").gte(active_cutoff().isoformat()),
        **filter_kwargs,
    }
    items = []
    while True:   # bounded: at most rooms x slots x MAX_DAYS_AHEAD bookings can exist
        resp = TABLE.query(**kwargs)
        items.extend(resp["Items"])
        if "LastEvaluatedKey" not in resp:
            return items
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def get_config():
    return respond(200, {
        "rooms": [{"name": n, **info} for n, info in ROOMS.items()],
        "slots": SLOTS,
        "maxDaysAhead": MAX_DAYS_AHEAD,
        "maxActive": MAX_ACTIVE,
        "employeeDomain": EMPLOYEE_DOMAIN,
    })


def get_me(user):
    """Everything this user booked: upcoming (counts toward the quota) and the last HISTORY_DAYS.
    Employees are identified by email, so this follows them to any device they sign in on."""
    mine = Attr("ownerSub").eq(user["sub"])
    upcoming = upcoming_items(FilterExpression=mine)
    past, kwargs = [], {
        "IndexName": "upcoming",
        "KeyConditionExpression": Key("gsi1pk").eq("BOOKING") & Key("gsi1sk").between(
            (today() - dt.timedelta(days=HISTORY_DAYS)).isoformat(), active_cutoff().isoformat()),
        "FilterExpression": mine,
    }
    while True:
        resp = TABLE.query(**kwargs)
        past.extend(resp["Items"])
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return respond(200, {
        **user_summary(user),
        "upcoming": sort_bookings(public_view(i, user) for i in upcoming),
        "past": sort_bookings(public_view(i, user) for i in past)[::-1],   # most recent first
    })


def list_bookings(event, user):
    params = event.get("queryStringParameters") or {}
    if params.get("date"):
        day = parse_date(params["date"], allow_past=True)
        items = TABLE.query(KeyConditionExpression=Key("pk").eq(day.isoformat()))["Items"]
    else:
        items = upcoming_items()
    return respond(200, {"bookings": sort_bookings(public_view(i, user) for i in items)})


def quota_message(user):
    limit = MAX_ACTIVE[user["kind"]]
    if user["kind"] == "guest":
        return (f"Guests can hold {limit} upcoming booking. Cancel it, or sign in with your "
                f"@{EMPLOYEE_DOMAIN} email to book up to {MAX_ACTIVE['employee']}.")
    return f"You already have {limit} upcoming bookings. Cancel one to book another."


def create_booking(event, user):
    data = read_json(event)
    day = parse_date(data.get("date"))
    room = parse_room(data.get("room"))
    slot = parse_slot(data.get("slot"))
    title = clean_text(data.get("title"), "title", MAX_TITLE)
    attendees = parse_attendees(data.get("attendees"), room)
    if data.get("needsAv") is True and not ROOMS[room]["av"]:
        raise ApiError(400, f"{room} has no TV or video conferencing", "av")
    enforce_write_rate_limit(user, event)

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    expires = dt.datetime.combine(day + dt.timedelta(days=RETAIN_DAYS), dt.time(), tzinfo=dt.timezone.utc)
    item = {
        "pk": day.isoformat(),
        "sk": f"{room}#{slot}",
        "gsi1pk": "BOOKING",
        "gsi1sk": f"{day.isoformat()}#{slot}#{room}",
        "ownerSub": user["sub"],
        "ownerKind": user["kind"],
        "ownerName": user["name"],
        "title": title,
        "attendees": attendees,
        "createdAt": now,
        "expiresAt": int(expires.timestamp()),
    }
    bkey = booking_key(day.isoformat(), room, slot)
    cutoff = active_cutoff().isoformat()
    limit = MAX_ACTIVE[user["kind"]]

    for _ in range(3):   # optimistic concurrency on the owner item
        profile = TABLE.get_item(Key=owner_key(user), ConsistentRead=True).get("Item", {})
        active = {k: v for k, v in profile.get("active", {}).items() if v >= cutoff}
        if len(active) >= limit:
            raise ApiError(409, quota_message(user), "quota")
        active[bkey] = day.isoformat()
        version = int(profile.get("version", 0))
        owner = {**owner_key(user), "active": active, "version": version + 1,
                 "kind": user["kind"], "name": user["name"], "updatedAt": now,
                 # outlive the furthest-out booking, or a TTL delete would reset the quota
                 "expiresAt": max(int(profile.get("expiresAt", 0)), int(expires.timestamp()))}
        try:
            DDB.transact_write_items(TransactItems=[
                {"Put": {
                    "TableName": TABLE_NAME,
                    "Item": item,
                    "ConditionExpression": "attribute_not_exists(pk)",
                }},
                {"Put": {
                    "TableName": TABLE_NAME,
                    "Item": owner,
                    "ConditionExpression": "attribute_not_exists(pk) OR version = :v",
                    "ExpressionAttributeValues": {":v": version},
                }},
            ])
            return respond(201, {"booking": public_view(item, user)})
        except ClientError as e:
            if e.response["Error"]["Code"] != "TransactionCanceledException":
                raise
            reasons = [r.get("Code") for r in e.response.get("CancellationReasons", [])]
            if reasons and reasons[0] == "ConditionalCheckFailed":
                raise ApiError(409, f"{room} is already booked at {slot} on {day.isoformat()}", "taken")
            if len(reasons) > 1 and reasons[1] == "ConditionalCheckFailed":
                continue   # another request by this user won the race - re-read and re-check
            raise
    raise ApiError(409, "please try again", "retry")


def key_from_path(parts):
    # parts = ["bookings", date, room, slot]
    if len(parts) != 4:
        raise ApiError(404, "not found")
    day = parse_date(parts[1], allow_past=True)
    room = parse_room(parts[2])
    slot = parse_slot(parts[3])
    return {"pk": day.isoformat(), "sk": f"{room}#{slot}"}, booking_key(day.isoformat(), room, slot)


def ownership_failed(key, user):
    """Distinguish 'no such booking' (404) from 'not yours' (403) after a failed condition."""
    existing = TABLE.get_item(Key=key).get("Item")
    if not existing:
        return ApiError(404, "booking not found")
    if existing.get("ownerSub") != user["sub"]:
        return ApiError(403, "this booking belongs to someone else")
    return ApiError(409, "booking changed, please refresh")


def update_booking(event, parts, user):
    key, _ = key_from_path(parts)
    title = clean_text(read_json(event).get("title"), "title", MAX_TITLE)
    enforce_write_rate_limit(user, event)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    try:
        resp = TABLE.update_item(
            Key=key,
            UpdateExpression="SET title = :t, updatedAt = :u",
            ConditionExpression="attribute_exists(pk) AND ownerSub = :s",
            ExpressionAttributeValues={":t": title, ":u": now, ":s": user["sub"]},
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ownership_failed(key, user)
        raise
    return respond(200, {"booking": public_view(resp["Attributes"], user)})


def delete_booking(event, parts, user):
    key, bkey = key_from_path(parts)
    enforce_write_rate_limit(user, event)
    try:
        DDB.transact_write_items(TransactItems=[
            {"Delete": {
                "TableName": TABLE_NAME,
                "Key": key,
                "ConditionExpression": "attribute_exists(pk) AND ownerSub = :s",
                "ExpressionAttributeValues": {":s": user["sub"]},
            }},
            {"Update": {   # free the quota slot
                "TableName": TABLE_NAME,
                "Key": owner_key(user),
                "UpdateExpression": "REMOVE active.#b ADD version :one",
                # A user who never booked has no profile; without this condition the REMOVE
                # path would be invalid (ValidationException -> 500) instead of a clean 403.
                "ConditionExpression": "attribute_exists(active)",
                "ExpressionAttributeNames": {"#b": bkey},
                "ExpressionAttributeValues": {":one": 1},
            }},
        ])
    except ClientError as e:
        if e.response["Error"]["Code"] == "TransactionCanceledException":
            raise ownership_failed(key, user)
        raise
    return respond(200, {"deleted": True})


def route(method, parts, event):
    if parts[:1] != [API_PREFIX]:
        raise ApiError(404, "not found")
    parts = parts[1:]
    if parts == ["config"] and method == "GET":
        return get_config()
    if parts == ["session"] and method == "POST":
        return create_session(event)
    user = authenticate(event)          # everything below requires an employee or guest session
    if parts == ["me"] and method == "GET":
        return get_me(user)
    if parts == ["bookings"] and method == "GET":
        return list_bookings(event, user)
    if parts == ["bookings"] and method == "POST":
        return create_booking(event, user)
    if parts[:1] == ["bookings"] and method == "PATCH":
        return update_booking(event, parts, user)
    if parts[:1] == ["bookings"] and method == "DELETE":
        return delete_booking(event, parts, user)
    raise ApiError(404, "not found")


def lambda_handler(event, context):
    started = time.perf_counter()
    http = event.get("requestContext", {}).get("http", {})
    method = http.get("method", "")
    path = event.get("rawPath", "/")
    parts = [unquote(p) for p in path.split("/") if p]
    try:
        result = route(method, parts, event)
    except ApiError as e:
        body = {"error": e.message}
        if e.code:
            body["code"] = e.code
        result = respond(e.status, body)
    except Exception:
        log.exception("unhandled error", extra={"method": method, "path": path})
        result = respond(500, {"error": "internal error"})
    # One structured line per request (JSON log format is set on the function).
    # No names, emails, titles or tokens are logged.
    log.info("request", extra={
        "method": method,
        "path": path,
        "status": result["statusCode"],
        "latencyMs": round((time.perf_counter() - started) * 1000, 1),
        "requestId": getattr(context, "aws_request_id", None),
    })
    return result
