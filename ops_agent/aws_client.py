import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_session(region=None, profile=None):
    kwargs = {}
    if profile:
        kwargs["profile_name"] = profile
    if region:
        kwargs["region_name"] = region
    return boto3.Session(**kwargs)


def get_client(service, region=None, profile=None):
    return get_session(region, profile).client(service)


def get_regions(region=None, profile=None):
    if region:
        return [region]
    ec2 = get_client("ec2", "us-east-1", profile)
    resp = ec2.describe_regions(
        Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required", "opted-in"]}]
    )
    return [r["RegionName"] for r in resp["Regions"]]


def get_account_id(profile=None):
    sts = get_client("sts", "us-east-1", profile)
    return sts.get_caller_identity()["Account"]


def parallel_regions(fn, regions, max_workers=10):
    """Run fn(region) in parallel across regions. Returns flat list of results."""
    results = []
    with ThreadPoolExecutor(max_workers=min(len(regions), max_workers)) as executor:
        futures = {executor.submit(fn, r): r for r in regions}
        for future in as_completed(futures):
            try:
                results.extend(future.result())
            except Exception:
                pass
    return results


def build_org_tree(profile=None):
    """Build org tree: {ou_name: {id, accounts: [{id, name}]}}.

    Reusable by both CLI and dashboard server.
    """
    org_client = get_client("organizations", "us-east-1", profile)
    tree = {}
    roots = org_client.list_roots()["Roots"]
    root_id = roots[0]["Id"]

    ous = org_client.list_organizational_units_for_parent(ParentId=root_id).get("OrganizationalUnits", [])
    for ou in ous:
        accounts = []
        paginator = org_client.get_paginator("list_accounts_for_parent")
        for page in paginator.paginate(ParentId=ou["Id"]):
            for a in page["Accounts"]:
                if a["Status"] == "ACTIVE":
                    accounts.append({"id": a["Id"], "name": a["Name"]})
        tree[ou["Name"]] = {"id": ou["Id"], "accounts": accounts}

    return tree


def assume_role_session(account_id, role_name, profile=None):
    """Assume a cross-account role and return temporary credentials dict.

    Returns dict with AccessKeyId, SecretAccessKey, SessionToken.
    Raises on failure.
    """
    session = get_session(profile=profile)
    sts = session.client("sts")
    creds = sts.assume_role(
        RoleArn=f"arn:aws:iam::{account_id}:role/{role_name}",
        RoleSessionName="OpsAgentDashboard",
        DurationSeconds=3600,
    )["Credentials"]
    return creds

