"""Remove the Room Booker stack.

  python teardown.py --yes                 delete the stack; the DynamoDB table is RETAINED (data kept)
  python teardown.py --yes --delete-data   also turn off deletion protection and delete the table
"""
import argparse

import boto3
from botocore.exceptions import ClientError

p = argparse.ArgumentParser()
p.add_argument("--stack", default="room-booker-prod")
p.add_argument("--yes", action="store_true")
p.add_argument("--delete-data", action="store_true")
opts = p.parse_args()
if not opts.yes:
    raise SystemExit(f"This deletes stack {opts.stack} (site, API, alarms). Re-run with --yes to confirm.")

session = boto3.session.Session()
region = session.region_name or "us-east-1"
account = session.client("sts").get_caller_identity()["Account"]
cfn = session.client("cloudformation", region_name=region)
s3 = session.resource("s3", region_name=region)

out = {o["OutputKey"]: o["OutputValue"]
       for o in cfn.describe_stacks(StackName=opts.stack)["Stacks"][0].get("Outputs", [])}

# CloudFormation can't delete a non-empty (versioned) bucket.
s3.Bucket(out["SiteBucketName"]).object_versions.delete()
print(f"emptied {out['SiteBucketName']}")

cfn.delete_stack(StackName=opts.stack)
print("deleting stack (CloudFront takes several minutes)...")
cfn.get_waiter("stack_delete_complete").wait(StackName=opts.stack, WaiterConfig={"Delay": 15, "MaxAttempts": 160})
print("stack deleted")

if opts.delete_data:
    ddb = session.client("dynamodb", region_name=region)
    ddb.update_table(TableName=out["TableName"], DeletionProtectionEnabled=False)
    ddb.delete_table(TableName=out["TableName"])
    print(f"deleted table {out['TableName']}")
    artifacts = s3.Bucket(f"room-booker-artifacts-{account}-{region}")
    try:
        artifacts.object_versions.delete()
        artifacts.delete()
        print(f"deleted {artifacts.name}")
    except ClientError as e:
        print(f"skip artifacts bucket: {e.response['Error']['Code']}")
else:
    print(f"table {out['TableName']} retained (use --delete-data to remove it)")
