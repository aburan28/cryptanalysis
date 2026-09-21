"""Optional per-rollout PostgreSQL ingress, limited to actual worker IPv4 /32s.

The fleet controller removes only rules tagged for its own completed rollout.
Existing administrator rules are never adopted or removed. A configured static
egress proxy can instead use its existing allow-list with this option unset.
"""
import ipaddress
import os
import re
from urllib.request import urlopen

PREFIX = "ecc2k130-rollout-"


def client():
    import boto3
    from botocore.config import Config
    return boto3.client("ec2", config=Config(connect_timeout=5, read_timeout=10,
                        retries={"max_attempts": 2}))


def description(rollout):
    if not re.fullmatch(r"[a-f0-9]{32}", rollout):
        raise ValueError("invalid rollout identity")
    return PREFIX + rollout


def ensure_access(rollout):
    group = os.environ.get("ECC_RDS_SECURITY_GROUP")
    if not group:
        return {"managed": False}
    label = description(rollout)
    with urlopen("https://checkip.amazonaws.com", timeout=10) as response:
        address = ipaddress.ip_address(response.read(64).decode().strip())
    if address.version != 4 or not address.is_global:
        raise ValueError("outbound address must be a public IPv4 address")
    from botocore.exceptions import ClientError
    try:
        result = client().authorize_security_group_ingress(GroupId=group,
            IpPermissions=[{"IpProtocol": "tcp", "FromPort": 5432, "ToPort": 5432,
                "IpRanges": [{"CidrIp": str(address) + "/32", "Description": label}]}])
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "InvalidPermission.Duplicate":
            raise RuntimeError("could not authorize the worker's PostgreSQL egress") from None
        return {"managed": True, "ip": str(address), "existing_rule": True}
    return {"managed": True, "ip": str(address), "created_rules":
            [r["SecurityGroupRuleId"] for r in result.get("SecurityGroupRules", [])]}


def cleanup(rollout):
    group = os.environ.get("ECC_RDS_SECURITY_GROUP")
    if not group:
        return []
    label = description(rollout)
    ec2 = client()
    ids = []
    for page in ec2.get_paginator("describe_security_group_rules").paginate(
            Filters=[{"Name": "group-id", "Values": [group]}]):
        ids.extend(r["SecurityGroupRuleId"] for r in page["SecurityGroupRules"]
                   if r.get("Description") == label and not r["IsEgress"]
                   and r.get("FromPort") == 5432 and r.get("ToPort") == 5432
                   and r.get("IpProtocol") == "tcp" and r.get("CidrIpv4", "").endswith("/32"))
    if ids:
        ec2.revoke_security_group_ingress(GroupId=group, SecurityGroupRuleIds=ids)
    return ids
