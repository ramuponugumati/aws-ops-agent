#!/usr/bin/env python3
"""Apply auto-delete=no tag to all taggable resources across accounts and regions."""
import boto3

MANAGEMENT_ACCOUNT = "073369242087"
MEMBER_ACCOUNTS = ["130871338503", "761288222017", "316319294488", "505192030782"]
CROSS_ACCOUNT_ROLE = "OrganizationAccountAccessRole"
TAG = {"auto-delete": "no"}


def get_all_regions(session):
    ec2 = session.client("ec2", region_name="us-east-1")
    return [r["RegionName"] for r in ec2.describe_regions(AllRegions=False)["Regions"]]


def tag_account(session, account_id, regions):
    tagged, errors = 0, 0
    for region in regions:
        try:
            client = session.client("resourcegroupstaggingapi", region_name=region)
            paginator = client.get_paginator("get_resources")
            arns = []
            for page in paginator.paginate():
                arns.extend(r["ResourceARN"] for r in page["ResourceTagMappingList"])
            # Tag in batches of 20 (API limit)
            for i in range(0, len(arns), 20):
                batch = arns[i:i+20]
                resp = client.tag_resources(ResourceARNList=batch, Tags=TAG)
                failed = resp.get("FailedResourcesMap", {})
                tagged += len(batch) - len(failed)
                errors += len(failed)
                if failed:
                    for arn, err in failed.items():
                        print(f"  FAILED [{region}] {arn}: {err['ErrorMessage']}")
        except Exception as e:
            print(f"  ERROR [{account_id}][{region}]: {e}")
    return tagged, errors


def get_session_for_account(base_session, account_id):
    if account_id == MANAGEMENT_ACCOUNT:
        return base_session
    sts = base_session.client("sts")
    creds = sts.assume_role(
        RoleArn=f"arn:aws:iam::{account_id}:role/{CROSS_ACCOUNT_ROLE}",
        RoleSessionName="tag-auto-delete"
    )["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )


def main():
    base_session = boto3.Session(profile_name="ramuponu-admin")
    regions = get_all_regions(base_session)
    print(f"Regions: {len(regions)} | Accounts: {1 + len(MEMBER_ACCOUNTS)}\n")

    all_accounts = [MANAGEMENT_ACCOUNT] + MEMBER_ACCOUNTS
    total_tagged, total_errors = 0, 0

    for account_id in all_accounts:
        print(f"→ Account {account_id} ...")
        try:
            session = get_session_for_account(base_session, account_id)
            tagged, errors = tag_account(session, account_id, regions)
            print(f"  ✓ tagged={tagged} errors={errors}")
            total_tagged += tagged
            total_errors += errors
        except Exception as e:
            print(f"  ✗ Could not access account {account_id}: {e}")

    print(f"\nDone. Total tagged={total_tagged} total_errors={total_errors}")


if __name__ == "__main__":
    main()
