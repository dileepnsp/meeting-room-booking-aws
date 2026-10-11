"""Exercise the Lambda against a moto-mocked DynamoDB table (same schema as template.yaml)."""
import datetime as dt
import importlib
import json
import os
import sys
import time

import boto3
import jwt
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

UTC_TODAY = dt.datetime.now(dt.timezone.utc).date()
D1, D2, D3, D4 = ((UTC_TODAY + dt.timedelta(days=n)).isoformat() for n in (1, 2, 3, 4))
SECRET = "test-secret-that-is-long-enough-for-hs256"


@pytest.fixture
def api(monkeypatch):
    os.environ.update(TABLE_NAME="t", SESSION_SECRET=SECRET, EMPLOYEE_EMAIL_DOMAIN="prudential.com",
                      WRITE_RATE_LIMIT="50", MAX_ACTIVE_PER_EMPLOYEE="3", MAX_ACTIVE_PER_GUEST="1",
                      GUEST_SESSIONS_PER_HOUR="5", AWS_DEFAULT_REGION="us-east-1",
                      AWS_ACCESS_KEY_ID="x", AWS_SECRET_ACCESS_KEY="x")
    with mock_aws():
        boto3.client("dynamodb").create_table(
            TableName="t", BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[{"AttributeName": n, "AttributeType": "S"} for n in ("pk", "sk", "gsi1pk", "gsi1sk")],
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            GlobalSecondaryIndexes=[{
                "IndexName": "upcoming", "Projection": {"ProjectionType": "ALL"},
                "KeySchema": [{"AttributeName": "gsi1pk", "KeyType": "HASH"},
                              {"AttributeName": "gsi1sk", "KeyType": "RANGE"}]}])
        import lambda_function
        importlib.reload(lambda_function)

        def call(method, path, body=None, query=None, token=None, ip="203.0.113.7"):
            event = {"requestContext": {"http": {"method": method, "sourceIp": "130.176.0.1"}},
                     "rawPath": "/api" + path, "queryStringParameters": query,
                     "headers": {"CloudFront-Viewer-Address": f"{ip}:51234"}}
            if body is not None:
                event["body"] = body if isinstance(body, str) else json.dumps(body)
            if token:
                event["headers"]["X-Auth-Token"] = token
            r = lambda_function.lambda_handler(event, None)
            assert not any(h.lower().startswith("access-control") for h in r["headers"])  # same-origin: no CORS
            return r["statusCode"], json.loads(r["body"])

        def employee(email="ana.lim@prudential.com"):
            status, body = call("POST", "/session", {"email": email})
            assert status == 201, body
            return body["token"]

        def guest(name="Visitor", ip="203.0.113.7"):
            status, body = call("POST", "/session", {"guest": True, "name": name}, ip=ip)
            assert status == 201, body
            return body["token"]

        call.module, call.employee, call.guest = lambda_function, employee, guest
        yield call


def booking(**over):
    return {"date": D1, "room": "Everest", "slot": "09:00", "title": "Standup", "attendees": 6, "needsAv": False, **over}


# ---------- sessions ----------

def test_config_is_public(api):
    status, cfg = api("GET", "/config")
    assert status == 200 and cfg["employeeDomain"] == "prudential.com"
    assert cfg["maxActive"] == {"employee": 3, "guest": 1}
    rooms = {r["name"]: r for r in cfg["rooms"]}
    assert rooms["Kilimanjaro"]["av"] is False and rooms["Olympus"]["capacity"] == 40


def test_employee_session_from_company_email(api):
    status, body = api("POST", "/session", {"email": "  Ana.Lim@Prudential.com "})
    assert status == 201
    assert body["user"] == {"name": "Ana Lim", "email": "ana.lim@prudential.com", "kind": "employee", "maxActive": 3}
    _, me = api("GET", "/me", token=body["token"])
    assert me["name"] == "Ana Lim" and me["kind"] == "employee"


@pytest.mark.parametrize("email", [
    "ana@gmail.com", "ana@prudential.com.evil.com", "ana@evilprudential.com", "ana@sub.prudential.com",
    "@prudential.com", "ana..lim@prudential.com", ".ana@prudential.com", "ana@prudential", "", None, 42,
    "a" * 70 + "@prudential.com", "ana lim@prudential.com",
])
def test_non_company_emails_rejected(api, email):
    status, body = api("POST", "/session", {"email": email})
    assert status == 400 and body["code"] == "domain", body


def test_guest_session(api):
    status, body = api("POST", "/session", {"guest": True, "name": "  Pat  "})
    assert status == 201 and body["user"] == {"name": "Pat", "email": "", "kind": "guest", "maxActive": 1}
    assert api("POST", "/session", {"guest": True, "name": ""})[0] == 400
    assert api("POST", "/session", {"guest": True, "name": "x" * 41})[0] == 400


def test_guest_sessions_rate_limited_per_network(api):
    for _ in range(5):
        api.guest(ip="198.51.100.1")
    status, body = api("POST", "/session", {"guest": True, "name": "Again"}, ip="198.51.100.1")
    assert status == 429 and body["code"] == "rate"
    api.guest(ip="198.51.100.2")                                       # other networks unaffected
    api.employee()                                                     # employees unaffected


@pytest.mark.parametrize("token", [
    None, "garbage",
    jwt.encode({"sub": "emp:x@prudential.com", "kind": "employee", "iss": "room-booker",
                "iat": int(time.time()), "exp": int(time.time()) + 60}, "wrong-secret-wrong-secret-wrong!!", algorithm="HS256"),
    jwt.encode({"sub": "emp:x@prudential.com", "kind": "employee", "iss": "room-booker",
                "iat": int(time.time()) - 100, "exp": int(time.time()) - 10}, SECRET, algorithm="HS256"),
    jwt.encode({"sub": "x", "kind": "admin", "iss": "room-booker",
                "iat": int(time.time()), "exp": int(time.time()) + 60}, SECRET, algorithm="HS256"),
    jwt.encode({"sub": "x", "kind": "employee", "iss": "room-booker",
                "iat": int(time.time()), "exp": int(time.time()) + 60}, None, algorithm="none"),
])
def test_bad_tokens_rejected(api, token):
    for method, path, body in [("GET", "/bookings", None), ("GET", "/me", None), ("POST", "/bookings", booking())]:
        status, body = api(method, path, body, token=token)
        assert status == 401 and body["code"] == "auth"


# ---------- CRUD + ownership ----------

def test_create_list_update_delete(api):
    ana, bob = api.employee(), api.employee("bob.tan@prudential.com")
    status, created = api("POST", "/bookings", booking(), token=ana)
    assert status == 201 and created["booking"]["name"] == "Ana Lim" and created["booking"]["mine"]
    assert created["booking"]["attendees"] == 6

    _, day = api("GET", "/bookings", query={"date": D1}, token=bob)
    b = day["bookings"][0]
    assert b["title"] == "Standup" and b["mine"] is False and b["guest"] is False
    assert not {"ownerSub", "email", "ownerKind"} & set(b)

    path = f"/bookings/{D1}/Everest/09%3A00"   # encoded colon must work too
    assert api("PATCH", path, {"title": "Hijack"}, token=bob)[0] == 403
    assert api("DELETE", path, token=bob)[0] == 403
    assert api("PATCH", path, {"title": "Retro"}, token=ana)[0] == 200
    assert api("DELETE", path, token=ana)[0] == 200
    assert api("DELETE", path, token=ana)[0] == 404


def test_guest_booking_is_owned_by_that_guest_only(api):
    g1, g2, ana = api.guest("Pat"), api.guest("Lee"), api.employee()
    _, created = api("POST", "/bookings", booking(), token=g1)
    assert created["booking"]["guest"] is True and created["booking"]["name"] == "Pat"
    path = f"/bookings/{D1}/Everest/09:00"
    assert api("DELETE", path, token=g2)[0] == 403
    assert api("DELETE", path, token=ana)[0] == 403
    assert api("DELETE", path, token=g1)[0] == 200


def test_double_booking_rejected(api):
    assert api("POST", "/bookings", booking(), token=api.employee())[0] == 201
    status, body = api("POST", "/bookings", booking(), token=api.guest())
    assert status == 409 and body["code"] == "taken"


def test_upcoming_and_me(api):
    ana, bob = api.employee(), api.employee("bob@prudential.com")
    api("POST", "/bookings", booking(date=D2, slot="11:00"), token=ana)
    api("POST", "/bookings", booking(slot="10:00"), token=bob)
    api("POST", "/bookings", booking(room="Denali", slot="10:00"), token=ana)
    _, everyone = api("GET", "/bookings", token=ana)
    assert [(b["date"], b["slot"], b["room"], b["mine"]) for b in everyone["bookings"]] == [
        (D1, "10:00", "Denali", True), (D1, "10:00", "Everest", False), (D2, "11:00", "Everest", True)]
    _, me = api("GET", "/me", token=ana)
    assert me["maxActive"] == 3 and [(b["date"], b["room"]) for b in me["upcoming"]] == [(D1, "Denali"), (D2, "Everest")]


# ---------- capacity and AV ----------

def test_capacity_enforced(api):
    ana = api.employee()
    status, body = api("POST", "/bookings", booking(room="Fuji", attendees=5), token=ana)
    assert status == 400 and body["code"] == "capacity"
    assert api("POST", "/bookings", booking(room="Fuji", attendees=4), token=ana)[0] == 201


@pytest.mark.parametrize("attendees", [0, -1, 41, 2.5, "6", True, None])
def test_attendees_validated(api, attendees):
    assert api("POST", "/bookings", booking(attendees=attendees), token=api.employee())[0] == 400


def test_av_requirement_enforced(api):
    ana = api.employee()
    status, body = api("POST", "/bookings", booking(room="Kilimanjaro", attendees=4, needsAv=True), token=ana)
    assert status == 400 and body["code"] == "av"
    assert api("POST", "/bookings", booking(room="Kilimanjaro", attendees=4), token=ana)[0] == 201


# ---------- quotas ----------

def test_employee_quota_of_three(api):
    ana = api.employee()
    for slot in ["08:00", "09:00", "10:00"]:
        assert api("POST", "/bookings", booking(slot=slot), token=ana)[0] == 201
    status, body = api("POST", "/bookings", booking(slot="11:00"), token=ana)
    assert status == 409 and body["code"] == "quota"
    assert api("POST", "/bookings", booking(slot="11:00"), token=api.employee("bob@prudential.com"))[0] == 201
    assert api("DELETE", f"/bookings/{D1}/Everest/08:00", token=ana)[0] == 200    # cancelling frees a slot
    assert api("POST", "/bookings", booking(slot="12:00"), token=ana)[0] == 201


def test_same_email_is_same_employee_quota(api):
    """Trust-based login: the email IS the identity, so new sessions don't reset the quota."""
    for slot in ["08:00", "09:00", "10:00"]:
        api("POST", "/bookings", booking(slot=slot), token=api.employee())
    assert api("POST", "/bookings", booking(slot="11:00"), token=api.employee())[1]["code"] == "quota"


def test_guest_quota_of_one(api):
    g = api.guest()
    assert api("POST", "/bookings", booking(slot="08:00"), token=g)[0] == 201
    status, body = api("POST", "/bookings", booking(slot="09:00"), token=g)
    assert status == 409 and body["code"] == "quota" and "prudential.com" in body["error"]


def test_quota_ignores_past_bookings(api):
    ana = api.employee()
    for slot in ["08:00", "09:00", "10:00"]:
        api("POST", "/bookings", booking(slot=slot), token=ana)
    tbl = boto3.resource("dynamodb").Table("t")
    key = {"pk": "USER#emp:ana.lim@prudential.com", "sk": "PROFILE"}
    prof = tbl.get_item(Key=key)["Item"]
    old = (UTC_TODAY - dt.timedelta(days=5)).isoformat()
    tbl.update_item(Key=key, UpdateExpression="SET active = :a",
                    ExpressionAttributeValues={":a": {k: old for k in prof["active"]}})
    assert api("POST", "/bookings", booking(date=D3), token=ana)[0] == 201


def test_quota_cannot_be_raced_with_a_stale_read(api, monkeypatch):
    """Deterministic race: a request that read the owner record BEFORE other bookings landed must
    not be able to write. (moto isn't thread-safe, so a threaded test here proves nothing; the
    live e2e test fires real parallel requests at DynamoDB.)"""
    ana = api.employee()
    real_get = api.module.TABLE.get_item
    stale = real_get(Key={"pk": "USER#emp:ana.lim@prudential.com", "sk": "PROFILE"}, ConsistentRead=True)
    for slot in ["08:00", "09:00", "10:00"]:
        assert api("POST", "/bookings", booking(date=D4, slot=slot), token=ana)[0] == 201

    def stale_get_item(**kw):            # always returns the pre-booking (empty) owner record
        return stale if kw["Key"]["sk"] == "PROFILE" else real_get(**kw)
    monkeypatch.setattr(api.module.TABLE, "get_item", stale_get_item)
    status, body = api("POST", "/bookings", booking(date=D4, slot="11:00"), token=ana)
    assert status == 409 and body["code"] == "retry"           # version check rejected the stale write
    monkeypatch.setattr(api.module.TABLE, "get_item", real_get)
    _, me = api("GET", "/me", token=ana)
    assert len(me["upcoming"]) == 3


# ---------- validation, limits, logging ----------

def test_write_rate_limit(api, monkeypatch):
    monkeypatch.setattr(api.module, "WRITE_RATE_LIMIT", 2)
    ana = api.employee()
    path = f"/bookings/{D1}/Everest/09:00"
    api("POST", "/bookings", booking(), token=ana)
    assert api("PATCH", path, {"title": "a"}, token=ana)[0] == 200
    assert api("PATCH", path, {"title": "b"}, token=ana)[0] == 429
    assert api("GET", "/bookings", token=ana)[0] == 200                          # reads never limited


@pytest.mark.parametrize("over", [
    {"room": "Broom closet"}, {"slot": "09:30"}, {"slot": "23:00"}, {"date": "2020-01-01"},
    {"date": "2026-02-30"}, {"date": "not-a-date"}, {"title": ""}, {"title": None}, {"title": "x" * 101},
])
def test_validation(api, over):
    status, body = api("POST", "/bookings", booking(**over), token=api.employee())
    assert status == 400, body


def test_bad_bodies_and_routes(api):
    ana = api.employee()
    assert api("POST", "/bookings", "{not json", token=ana)[0] == 400
    assert api("POST", "/bookings", "[1,2]", token=ana)[0] == 400
    assert api("POST", "/bookings", json.dumps(booking(title="x" * 3000)), token=ana)[0] == 413
    assert api("GET", "/nope", token=ana)[0] == 404
    r = api.module.lambda_handler({"requestContext": {"http": {"method": "GET"}}, "rawPath": "/config"}, None)
    assert r["statusCode"] == 404                                                 # /api prefix required


def test_control_chars_stripped(api):
    _, created = api("POST", "/bookings", booking(title="Plan\x00ning\n"), token=api.employee())
    assert created["booking"]["title"] == "Planning"


def test_structured_request_log_has_no_user_data(api, caplog):
    ana = api.employee()
    caplog.set_level("INFO")
    api("POST", "/bookings", booking(title="Secret Plan"), token=ana)
    rec = next(r for r in caplog.records if r.getMessage() == "request")
    assert rec.status == 201 and rec.method == "POST" and rec.latencyMs >= 0
    dumped = json.dumps(rec.__dict__, default=str)
    assert "Secret" not in dumped and "ana.lim" not in dumped


def test_me_lists_upcoming_and_recent_past(api):
    ana = api.employee()
    api("POST", "/bookings", booking(date=D2), token=ana)
    tbl = boto3.resource("dynamodb").Table("t")
    past_day = (UTC_TODAY - dt.timedelta(days=3)).isoformat()
    old_day = (UTC_TODAY - dt.timedelta(days=45)).isoformat()
    for day, title in [(past_day, "Last week"), (old_day, "Too old")]:
        tbl.put_item(Item={"pk": day, "sk": "Fuji#10:00", "gsi1pk": "BOOKING", "gsi1sk": f"{day}#10:00#Fuji",
                           "ownerSub": "emp:ana.lim@prudential.com", "ownerKind": "employee",
                           "ownerName": "Ana Lim", "title": title, "attendees": 2})
    _, me = api("GET", "/me", token=api.employee())       # a fresh session (e.g. another device) sees them
    assert [b["date"] for b in me["upcoming"]] == [D2]
    assert [b["title"] for b in me["past"]] == ["Last week"]
