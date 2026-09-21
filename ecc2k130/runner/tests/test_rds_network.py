"""Verify managed ingress stays limited to the current rollout and one host."""
import os
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'aws'))
import rds_network


class ClientError(Exception):
    def __init__(self, code):
        self.response = {'Error': {'Code': code}}


class NetworkTests(unittest.TestCase):
    rollout = 'a' * 32

    def setUp(self):
        self.env = patch.dict(os.environ, {'ECC_RDS_SECURITY_GROUP': 'sg-test'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.ec2 = MagicMock()
        self.client = patch.object(rds_network, 'client', return_value=self.ec2).start()
        self.addCleanup(patch.stopall)
        self.response = MagicMock()
        self.response.__enter__.return_value.read.return_value = b'8.8.8.8\n'
        self.urlopen = patch.object(rds_network, 'urlopen', return_value=self.response).start()
        exceptions = ModuleType('botocore.exceptions')
        exceptions.ClientError = ClientError
        patch.dict(sys.modules, {'botocore.exceptions': exceptions}).start()

    def test_unset_group_performs_no_network_actions(self):
        os.environ.pop('ECC_RDS_SECURITY_GROUP')
        self.assertEqual(rds_network.ensure_access(self.rollout), {'managed': False})
        self.assertEqual(rds_network.cleanup(self.rollout), [])
        self.client.assert_not_called()
        self.urlopen.assert_not_called()

    def test_authorize_exact_public_host_and_database_port(self):
        self.ec2.authorize_security_group_ingress.return_value = {
            'SecurityGroupRules': [{'SecurityGroupRuleId': 'sgr-owned'}]}
        result = rds_network.ensure_access(self.rollout)
        self.assertEqual(result['created_rules'], ['sgr-owned'])
        self.ec2.authorize_security_group_ingress.assert_called_once_with(
            GroupId='sg-test', IpPermissions=[{'IpProtocol': 'tcp', 'FromPort': 5432,
                'ToPort': 5432, 'IpRanges': [{'CidrIp': '8.8.8.8/32',
                    'Description': rds_network.PREFIX + self.rollout}]}])

    def test_invalid_rollout_cannot_add_or_remove_rules(self):
        for rollout in ('', 'a', '../other', 'a' * 31, 'A' * 32):
            with self.subTest(rollout=rollout):
                with self.assertRaises(ValueError):
                    rds_network.ensure_access(rollout)
                with self.assertRaises(ValueError):
                    rds_network.cleanup(rollout)
        self.client.assert_not_called()
        self.urlopen.assert_not_called()

    def test_private_or_invalid_addresses_never_authorized(self):
        for address in (b'127.0.0.1', b'10.0.0.1', b'0.0.0.0', b'::1', b'8.8.8.8/0'):
            with self.subTest(address=address), self.assertRaises(ValueError):
                self.response.__enter__.return_value.read.return_value = address
                rds_network.ensure_access(self.rollout)
        self.client.assert_not_called()

    def test_existing_rule_is_never_adopted(self):
        self.ec2.authorize_security_group_ingress.side_effect = ClientError('InvalidPermission.Duplicate')
        result = rds_network.ensure_access(self.rollout)
        self.assertTrue(result['existing_rule'])
        self.ec2.modify_security_group_rules.assert_not_called()
        self.ec2.revoke_security_group_ingress.assert_not_called()

    def test_unexpected_authorization_failure_is_fatal(self):
        self.ec2.authorize_security_group_ingress.side_effect = ClientError('UnauthorizedOperation')
        with self.assertRaisesRegex(RuntimeError, 'could not authorize'):
            rds_network.ensure_access(self.rollout)

    def test_cleanup_only_removes_owned_exact_database_host_rules(self):
        owned = {'SecurityGroupRuleId': 'sgr-owned', 'Description': rds_network.PREFIX + self.rollout,
                 'IsEgress': False, 'IpProtocol': 'tcp', 'FromPort': 5432, 'ToPort': 5432,
                 'CidrIpv4': '8.8.8.8/32'}
        other = [dict(owned, SecurityGroupRuleId='sgr-other', **change) for change in (
            {'Description': rds_network.PREFIX + 'b' * 32}, {'Description': 'administrator'},
            {'IsEgress': True}, {'FromPort': 0}, {'ToPort': 65535}, {'IpProtocol': 'udp'},
            {'CidrIpv4': '8.8.8.0/24'})]
        self.ec2.get_paginator.return_value.paginate.return_value = [
            {'SecurityGroupRules': other}, {'SecurityGroupRules': [owned]}]
        self.assertEqual(rds_network.cleanup(self.rollout), ['sgr-owned'])
        self.ec2.revoke_security_group_ingress.assert_called_once_with(
            GroupId='sg-test', SecurityGroupRuleIds=['sgr-owned'])


if __name__ == '__main__':
    unittest.main()
