"""The EC2 requests deploy/aws/launch.py would send; no service is called."""
import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launch  # noqa: E402

KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAItest test"
NOW = datetime.datetime(2026, 10, 17, 12, 0, tzinfo=datetime.timezone.utc)


class FakeEC2:
    def __init__(self, groups=(), key_pairs=()):
        self.groups, self.key_pairs, self.calls = list(groups), list(key_pairs), []

    def describe_vpcs(self, Filters):
        return {"Vpcs": [{"VpcId": "vpc-1"}]}

    def describe_security_groups(self, Filters):
        return {"SecurityGroups": self.groups}

    def create_security_group(self, **kw):
        self.calls.append(("create_security_group", kw))
        return {"GroupId": "sg-new"}

    def authorize_security_group_ingress(self, **kw):
        self.calls.append(("authorize", kw))

    def describe_key_pairs(self, Filters):
        name = Filters[0]["Values"][0]
        return {"KeyPairs": [{"KeyName": name}] if name in self.key_pairs else []}

    def import_key_pair(self, **kw):
        self.calls.append(("import_key_pair", kw))


class ParseTest(unittest.TestCase):
    def test_the_documented_command(self):
        args = launch.parse(["launch", "--region", "us-east-1", "--allow-cidr", "1.2.3.4/32"])
        self.assertEqual((args.name, args.type, args.hours, args.spot),
                         ("exp", launch.CPU_TYPE, 6.0, False))
        self.assertEqual(args.allow_cidr, ["1.2.3.4/32"])
        self.assertEqual(launch.region(args), "us-east-1")

    def test_gpu_shorthand(self):
        args = launch.parse(["launch", "--allow-cidr", "1.2.3.4/32", "--gpu"])
        self.assertEqual(args.type, launch.GPU_TYPE)

    def test_allow_cidr_is_required_and_never_the_internet(self):
        for bad in ([], ["--allow-cidr", "0.0.0.0/0"], ["--allow-cidr", "1.2.3.4"]):
            with self.assertRaises(SystemExit):
                launch.parse(["launch", *bad])

    def test_gpu_with_a_cpu_type_is_refused(self):
        with self.assertRaises(SystemExit):
            launch.parse(["launch", "--allow-cidr", "1.2.3.4/32", "--gpu", "--type", "c7i.large"])

    def test_run_keeps_the_command_and_outputs(self):
        args = launch.parse(["run", "exp", "--out", "a/b.json", "--", "make", "&&", "ls"])
        self.assertEqual(args.command, ["make", "&&", "ls"])
        self.assertEqual(args.out, ["a/b.json"])


class RequestTest(unittest.TestCase):
    def request(self, *extra):
        args = launch.parse(["launch", "--allow-cidr", "1.2.3.4/32", *extra])
        return launch.run_request(args, "ami-1", "kp", "sg-1", "/dev/sda1", 0, now=NOW)

    def test_shutdown_terminates_and_the_cap_comes_first(self):
        body = self.request("--hours", "1.5")
        self.assertEqual(body["InstanceInitiatedShutdownBehavior"], "terminate")
        self.assertEqual(body["UserData"].splitlines()[1], "shutdown -h +90")
        tags = {t["Key"]: t["Value"] for t in body["TagSpecifications"][0]["Tags"]}
        self.assertEqual(tags, {"Name": "exp", launch.TAG: "1",
                                "ca:deadline": "2026-10-17T13:30:00Z"})

    def test_imdsv2_and_an_encrypted_root(self):
        body = self.request()
        self.assertEqual(body["MetadataOptions"]["HttpTokens"], "required")
        ebs = body["BlockDeviceMappings"][0]["Ebs"]
        self.assertTrue(ebs["Encrypted"] and ebs["DeleteOnTermination"])
        self.assertEqual(ebs["VolumeSize"], 100)
        self.assertNotIn("InstanceMarketOptions", body)

    def test_root_volume_is_never_smaller_than_the_image(self):
        args = launch.parse(["launch", "--allow-cidr", "1.2.3.4/32", "--disk", "20"])
        body = launch.run_request(args, "ami-1", "kp", "sg-1", "/dev/xvda", 75, now=NOW)
        self.assertEqual(body["BlockDeviceMappings"][0]["DeviceName"], "/dev/xvda")
        self.assertEqual(body["BlockDeviceMappings"][0]["Ebs"]["VolumeSize"], 75)

    def test_spot(self):
        market = self.request("--spot")["InstanceMarketOptions"]
        self.assertEqual(market["SpotOptions"]["InstanceInterruptionBehavior"], "terminate")

    def test_gpu_families(self):
        for t, want in (("g7e.2xlarge", True), ("p5.48xlarge", True), ("g6e.xlarge", True),
                        ("c7i.4xlarge", False), ("c7g.4xlarge", False), ("m7i.large", False)):
            self.assertEqual(launch.is_gpu(t), want, t)


class GroupAndKeyTest(unittest.TestCase):
    def test_new_group_admits_only_ssh_from_the_cidrs(self):
        ec2 = FakeEC2()
        self.assertEqual(launch.ensure_group(ec2, ["1.2.3.4/32", "5.6.7.0/24"]), "sg-new")
        rule = dict(ec2.calls)["authorize"]["IpPermissions"]
        self.assertEqual(len(rule), 1)
        self.assertEqual((rule[0]["FromPort"], rule[0]["ToPort"]), (22, 22))
        self.assertEqual([r["CidrIp"] for r in rule[0]["IpRanges"]], ["1.2.3.4/32", "5.6.7.0/24"])

    def test_existing_ranges_are_not_added_twice(self):
        group = {"GroupId": "sg-1", "IpPermissions": [
            {"FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": "1.2.3.4/32"}]}]}
        ec2 = FakeEC2(groups=[group])
        launch.ensure_group(ec2, ["1.2.3.4/32"])
        self.assertEqual(ec2.calls, [])
        launch.ensure_group(ec2, ["1.2.3.4/32", "9.9.9.9/32"])
        rule = dict(ec2.calls)["authorize"]["IpPermissions"][0]
        self.assertEqual([r["CidrIp"] for r in rule["IpRanges"]], ["9.9.9.9/32"])

    def test_key_pair_is_imported_once(self):
        name = launch.key_pair_name(KEY)
        ec2 = FakeEC2(key_pairs=[name])
        self.assertEqual(launch.ensure_key_pair(ec2, KEY), name)
        self.assertEqual(ec2.calls, [])
        ec2 = FakeEC2()
        launch.ensure_key_pair(ec2, KEY)
        self.assertEqual(ec2.calls[0][1]["KeyName"], name)


class ScriptTest(unittest.TestCase):
    def test_user_data_formats(self):
        text = launch.USER_DATA.format(minutes=60, user="ubuntu")
        self.assertTrue(text.startswith("#!/bin/bash\nshutdown -h +60\n"))
        self.assertIn("sudo -u ubuntu", text)


if __name__ == "__main__":
    unittest.main()
