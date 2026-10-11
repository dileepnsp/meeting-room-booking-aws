"""Deploy Room Booker with CloudFormation (infra/template.yaml).

  python deploy.py [--stack room-booker-prod] [--alert-email you@example.com]

Steps: package Lambda -> upload to a private artifacts bucket -> CloudFormation change set
(create or update, automatic rollback on failure) -> upload frontend -> CloudFront invalidation
-> live smoke tests. Safe to re-run; unchanged infrastructure is a no-op.
"""
import argparse
import hashlib
import io
import mimetypes
import pathlib
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

import boto3
from botocore.exceptions import ClientError, WaiterError

ROOT = pathlib.Path(__file__).parent
TEMPLATE = (ROOT / "infra" / "template.yaml").read_text()

args = argparse.ArgumentParser()
args.add_argument("--stack", default="room-booker-prod")
args.add_argument("--alert-email", default=None, help="email for alarm notifications")
args.add_argument("--employee-domain", default=None, help='company email domain (default "prudential.com")')
opts = args.parse_args()

session = boto3.session.Session()
REGION = session.region_name or "us-east-1"
ACCOUNT = session.client("sts").get_caller_identity()["Account"]
ARTIFACTS = f"room-booker-artifacts-{ACCOUNT}-{REGION}"

cfn = session.client("cloudformation", region_name=REGION)
s3 = session.client("s3", region_name=REGION)
cloudfront = session.client("cloudfront")


def step(msg):
    print(f"\n==> {msg}", flush=True)


def ensure_artifacts_bucket():
    step(f"Artifacts bucket {ARTIFACTS} (private)")
    try:
        kwargs = {} if REGION == "us-east-1" else {"CreateBucketConfiguration": {"LocationConstraint": REGION}}
        s3.create_bucket(Bucket=ARTIFACTS, **kwargs)
        print("   created")
    except ClientError as e:
        if e.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
            raise
        print("   exists")
    s3.put_public_access_block(Bucket=ARTIFACTS, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    s3.put_bucket_versioning(Bucket=ARTIFACTS, VersioningConfiguration={"Status": "Enabled"})
    s3.put_bucket_encryption(Bucket=ARTIFACTS, ServerSideEncryptionConfiguration={
        "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]})


def build_dependencies():
    """Install backend/requirements.txt as Linux arm64 / CPython 3.12 wheels (matches the Lambda
    runtime), so native packages like `cryptography` work even when deploying from Windows/macOS."""
    reqs = ROOT / "backend" / "requirements.txt"
    stamp = hashlib.sha256(reqs.read_bytes()).hexdigest()[:16]
    # Build outside the project: sync clients (OneDrive, Dropbox) lock freshly written folders.
    target = pathlib.Path(tempfile.gettempdir()) / "room-booker-build" / f"deps-{stamp}"
    done = target / ".complete"
    if not done.exists():
        shutil.rmtree(target, ignore_errors=True)
        subprocess.run([
            sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
            "--requirement", str(reqs), "--target", str(target),
            "--platform", "manylinux2014_aarch64", "--platform", "manylinux_2_28_aarch64",
            "--implementation", "cp", "--python-version", "3.12", "--only-binary=:all:",
        ], check=True)
        done.write_text(stamp)
    return target


def upload_lambda():
    step("Packaging Lambda")
    deps = build_dependencies()
    files = {"lambda_function.py": (ROOT / "backend" / "lambda_function.py").read_bytes()}
    for path in sorted(deps.rglob("*")):
        rel = path.relative_to(deps).as_posix()
        if path.is_file() and "__pycache__" not in rel and not rel.startswith("bin/") and rel != ".complete":
            files[rel] = path.read_bytes()
    buf = io.BytesIO()
    digest = hashlib.sha256()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))  # reproducible zip
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])
            digest.update(name.encode() + b"\0" + files[name])
    key = f"lambda/{digest.hexdigest()[:16]}.zip"
    s3.put_object(Bucket=ARTIFACTS, Key=key, Body=buf.getvalue())
    print(f"   s3://{ARTIFACTS}/{key} ({len(buf.getvalue()) // 1024} KB, {len(files)} files)")
    return key


def stack_exists():
    try:
        status = cfn.describe_stacks(StackName=opts.stack)["Stacks"][0]["StackStatus"]
    except ClientError:
        return False
    if status == "ROLLBACK_COMPLETE":       # failed first create: must be deleted before retrying
        print(f"   previous create failed ({status}); deleting it first")
        cfn.delete_stack(StackName=opts.stack)
        cfn.get_waiter("stack_delete_complete").wait(StackName=opts.stack)
        return False
    return True


def current_parameters():
    stack = cfn.describe_stacks(StackName=opts.stack)["Stacks"][0]
    return {p["ParameterKey"] for p in stack.get("Parameters", [])}


def print_failure_events():
    events = cfn.describe_stack_events(StackName=opts.stack)["StackEvents"]
    for ev in reversed(events[:40]):
        if "FAILED" in ev["ResourceStatus"]:
            print(f"   {ev['LogicalResourceId']}: {ev['ResourceStatus']} - {ev.get('ResourceStatusReason')}")


def deploy_stack(code_key):
    step(f"CloudFormation stack {opts.stack}")
    exists = stack_exists()
    previous = current_parameters() if exists else set()

    def secret(key):
        # Generated once, then kept (NoEcho - never printed or stored locally).
        if key in previous:
            return {"ParameterKey": key, "UsePreviousValue": True}
        return {"ParameterKey": key, "ParameterValue": secrets.token_urlsafe(32)}

    params = [
        {"ParameterKey": "CodeBucket", "ParameterValue": ARTIFACTS},
        {"ParameterKey": "CodeKey", "ParameterValue": code_key},
        secret("OriginSecret"),
        secret("SessionSecret"),
    ]
    if opts.alert_email is not None:
        params.append({"ParameterKey": "AlertEmail", "ParameterValue": opts.alert_email})
    elif "AlertEmail" in previous:
        params.append({"ParameterKey": "AlertEmail", "UsePreviousValue": True})
    if opts.employee_domain is not None:
        params.append({"ParameterKey": "EmployeeEmailDomain", "ParameterValue": opts.employee_domain})
    elif "EmployeeEmailDomain" in previous:
        params.append({"ParameterKey": "EmployeeEmailDomain", "UsePreviousValue": True})

    name = f"deploy-{int(time.time())}"
    cfn.create_change_set(
        StackName=opts.stack, ChangeSetName=name, ChangeSetType="UPDATE" if exists else "CREATE",
        TemplateBody=TEMPLATE, Parameters=params, Capabilities=["CAPABILITY_IAM"],
        Tags=[{"Key": "app", "Value": "room-booker"}],
    )
    try:
        cfn.get_waiter("change_set_create_complete").wait(
            StackName=opts.stack, ChangeSetName=name, WaiterConfig={"Delay": 5})
    except WaiterError:
        cs = cfn.describe_change_set(StackName=opts.stack, ChangeSetName=name)
        if "didn't contain changes" in cs.get("StatusReason", "") or "No updates" in cs.get("StatusReason", ""):
            print("   no infrastructure changes")
            cfn.delete_change_set(StackName=opts.stack, ChangeSetName=name)
            return
        raise SystemExit(f"   change set failed: {cs.get('StatusReason')}")

    changes = cfn.describe_change_set(StackName=opts.stack, ChangeSetName=name)["Changes"]
    for c in changes:
        rc = c["ResourceChange"]
        print(f"   {rc['Action']:<7} {rc['LogicalResourceId']} ({rc['ResourceType']})"
              + ("  [REPLACEMENT]" if rc.get("Replacement") == "True" else ""))
    cfn.execute_change_set(StackName=opts.stack, ChangeSetName=name)
    print("   executing (CloudFront takes a few minutes on first create)...", flush=True)
    waiter = "stack_update_complete" if exists else "stack_create_complete"
    try:
        cfn.get_waiter(waiter).wait(StackName=opts.stack, WaiterConfig={"Delay": 15, "MaxAttempts": 160})
    except WaiterError:
        print_failure_events()
        raise SystemExit("   stack deployment failed and was rolled back")
    print("   complete")


def outputs():
    stack = cfn.describe_stacks(StackName=opts.stack)["Stacks"][0]
    return {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}


def upload_frontend(bucket):
    step("Uploading frontend")
    site = ROOT / "frontend"
    local = {p.relative_to(site).as_posix(): p for p in sorted(site.rglob("*")) if p.is_file()}
    for key, path in local.items():
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        s3.put_object(Bucket=bucket, Key=key, Body=path.read_bytes(),
                      ContentType=ctype, CacheControl="no-cache")
        print(f"   {key}")
    # Remove files that no longer exist locally (e.g. the old config.js).
    for obj in s3.list_objects_v2(Bucket=bucket).get("Contents", []):
        if obj["Key"] not in local:
            s3.delete_object(Bucket=bucket, Key=obj["Key"])
            print(f"   removed stale {obj['Key']}")


def invalidate(distribution_id):
    step("CloudFront invalidation")
    inv = cloudfront.create_invalidation(DistributionId=distribution_id, InvalidationBatch={
        "Paths": {"Quantity": 1, "Items": ["/*"]}, "CallerReference": str(time.time())})
    cloudfront.get_waiter("invalidation_completed").wait(
        DistributionId=distribution_id, Id=inv["Invalidation"]["Id"], WaiterConfig={"Delay": 10, "MaxAttempts": 60})
    print("   done")


def fetch(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=15) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers)


def smoke_test(out):
    step("Smoke tests")
    app = out["AppUrl"]
    checks = [
        ("app over HTTPS", f"{app}/", 200),
        ("API through CloudFront", f"{app}/api/config", 200),
        ("bookings require sign-in", f"{app}/api/bookings", 401),
        ("direct Function URL is refused", f"{out['FunctionUrl'].rstrip('/')}/api/config", 403),
        ("direct S3 website is refused", f"{out['DirectS3WebsiteUrl']}/index.html", 403),
    ]
    ok = True
    for label, url, expected in checks:
        for attempt in range(8):
            status, headers = fetch(url)
            if status == expected:
                break
            time.sleep(10)
        good = status == expected
        ok &= good
        print(f"   {'PASS' if good else 'FAIL'}  {label}: {status} (expected {expected})")
    status, headers = fetch(f"{app}/")
    for h in ("Strict-Transport-Security", "Content-Security-Policy", "X-Frame-Options"):
        present = h.lower() in {k.lower() for k in headers}
        ok &= present
        print(f"   {'PASS' if present else 'FAIL'}  header {h}")
    return ok


def main():
    print(f"Account {ACCOUNT}, region {REGION}, stack {opts.stack}")
    ensure_artifacts_bucket()
    code_key = upload_lambda()
    deploy_stack(code_key)
    out = outputs()
    upload_frontend(out["SiteBucketName"])
    invalidate(out["DistributionId"])
    ok = smoke_test(out)
    print(f"\n{'Done' if ok else 'Deployed, but some smoke tests FAILED'}.\n  App: {out['AppUrl']}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
