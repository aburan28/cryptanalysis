"""Reject false speedups and unsafe EC2 launch inheritance without a GPU/AWS."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

import native_candidate_bench as bench

spec=importlib.util.spec_from_file_location('native_aws',bench.ROOT/'aws/native_benchmark.py')
aws=importlib.util.module_from_spec(spec);spec.loader.exec_module(aws)


def sample(weight=0,mode='combined',records=0):
    square,karat=bench.MODES[mode]
    raw=('packed direct reduction: 1\npacked generated product: 1\n'
         'packed native carryless multiply: 1\n'
         f'packed native carryless square: {square}\npacked three-limb Karatsuba: {karat}\n'
         'packed weighted prefix: 2\npacked compact state: 1\npacked shared sigma: 1\npacked state tile: 256\n'
         f'backend cuda-packed131: 385024 threads x 16 slots x 1 lanes = 6160384 walks, dp weight {weight}, 1024 steps per launch\n'
         f'14.0 s 14500.000 M it/s {bench.ITERATIONS} iterations {records} dp {records} stored 0 dropped\n'
         f'finished: 14500.000 M it/s, {records} distinguished points (0 verified against the reference, 0 dropped)\n')
    return dict(command=['fixture'],returncode=0,raw=raw,wallSeconds=15)


class BenchmarkGates(unittest.TestCase):
    def test_complete_scalar_run(self):
        result=bench.validate_sample(sample(),'combined',0)
        self.assertEqual(result['iterations'],201863462912)
        self.assertEqual(result['rate'],14500)

    def test_reject_incomplete_wrong_identity_and_false_rates(self):
        raw=sample()['raw']
        corruptions=[raw.replace(str(bench.ITERATIONS),str(bench.ITERATIONS-1)),
            raw.replace('385024 threads','385023 threads'),
            raw.replace('x 16 slots','x 32 slots'),raw.replace('0 dropped','1 dropped'),
            raw.replace('finished:','interrupted:'),raw.replace('14500.000','NaN'),
            raw.replace('14500.000','inf'),raw.replace('14500.000','-1'),
            raw+'MISMATCH\n',raw+'stopping: cancelled\n']
        for marker in ('packed three-limb Karatsuba: 1\n','packed native carryless square: 1\n'):
            corruptions.extend([raw.replace(marker,''),raw+marker,raw.replace(marker,marker.replace(': 1',': 0'))])
        for bad in corruptions:
            with self.subTest(bad=bad),self.assertRaises(RuntimeError):
                bench.validate_sample(dict(sample(),raw=bad),'combined',0)
        with self.assertRaises(RuntimeError):
            bench.validate_sample(dict(sample(),returncode=1),'combined',0)

    def test_corpus_multiset_preserves_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'corpus'; a=b'a'*32;b=b'b'*32
            p.write_bytes(a+b+a)
            first=bench.validate_sample(sample(34,records=3),'combined',34,p)
            p.write_bytes(a+a+b)
            self.assertEqual(first['corpusSha256'],bench.validate_sample(sample(34,records=3),'combined',34,p)['corpusSha256'])
            p.write_bytes(a+b+b)
            self.assertNotEqual(first['corpusSha256'],bench.validate_sample(sample(34,records=3),'combined',34,p)['corpusSha256'])
            p.write_bytes(a+b)
            with self.assertRaises(RuntimeError): bench.validate_sample(sample(34,records=3),'combined',34,p)

    def test_sass_counter_excludes_other_kernel_and_counts_predicates(self):
        text=f'.section .text.{bench.WALK},"ax"\n/*0000*/ CLMAD.LO R0, R2, R2, RZ;\n/*0010*/ @UP0 BRA target;\n/*0020*/ @!P1 NOP ;\n.section .text.other,"ax"\n/*0000*/ MOV R0, R1;\n'
        counts=bench.sass_counts(text)
        self.assertEqual((counts['instructions'],counts['nonNop']),(3,2))


class IsolatedLaunch(unittest.TestCase):
    def template(self):
        return dict(ImageId='ami-fixture',IamInstanceProfile={'Name':'ecc2k130-worker'},
            SecurityGroupIds=['sg-fixture'],BlockDeviceMappings=[{'DeviceName':'/dev/sda1',
                'Ebs':{'VolumeSize':100,'DeleteOnTermination':True,'VolumeType':'gp3'}}],
            UserData='production-worker',TagSpecifications=[{'ResourceType':'instance','Tags':[{'Key':'Project','Value':'ecc2k130'}]}],
            InstanceMarketOptions={'MarketType':'spot'},NetworkInterfaces=[{'NetworkInterfaceId':'live'}])

    def test_one_disposable_gpu_never_inherits_production_startup(self):
        template=self.template();before=copy.deepcopy(template)
        script=aws.bootstrap('ecc2k130-123456789012','benchmarks/native/fixture','us-west-2','a'*64)
        request=aws.launch_request(template,'subnet-fixture',script,'token')
        self.assertEqual(template,before)
        self.assertEqual((request['MinCount'],request['MaxCount']),(1,1))
        self.assertEqual(request['InstanceType'],'g7e.2xlarge')
        self.assertEqual(request['InstanceInitiatedShutdownBehavior'],'terminate')
        self.assertEqual(request['UserData'],script)
        for key in ('LaunchTemplate','InstanceMarketOptions','NetworkInterfaces','KeyName'):
            self.assertNotIn(key,request)
        self.assertNotIn('production-worker',str(request))
        self.assertNotIn('campaign.json',script)
        self.assertIn('--on-active=55m',script)
        self.assertIn('timeout 2700 docker run',script)
        self.assertEqual(subprocess.run(['bash','-n'],input=script,text=True,capture_output=True).returncode,0)

    def test_reject_persistent_or_extra_volumes(self):
        for kind in ('persistent','extra','large'):
            data=self.template()
            if kind=='persistent': data['BlockDeviceMappings'][0]['Ebs']['DeleteOnTermination']=False
            if kind=='extra': data['BlockDeviceMappings']*=2
            if kind=='large': data['BlockDeviceMappings'][0]['Ebs']['VolumeSize']=200
            with self.assertRaises(ValueError): aws.launch_request(data,'subnet','script','token')

    def test_presigned_mode_has_no_instance_role_or_credential_material(self):
        urls={k:'https://example.invalid/'+k+'?signature=test&expires=3600' for k in ('source','results','done')}
        script=aws.bootstrap('bucket','benchmarks/test','us-west-2','a'*64,urls)
        template=self.template();template.pop('IamInstanceProfile')
        request=aws.launch_request(template,'subnet',script,'token',require_profile=False)
        self.assertNotIn('IamInstanceProfile',request)
        self.assertNotIn('aws s3 cp',script)
        self.assertNotIn('AWS_SECRET_ACCESS_KEY',script)
        self.assertNotIn('AWS_ACCESS_KEY_ID',script)
        for url in urls.values():self.assertIn(url,script)
        self.assertEqual(subprocess.run(['bash','-n'],input=script,text=True,capture_output=True).returncode,0)
        with self.assertRaises(ValueError): aws.launch_request(template,'subnet',script,'token')

    def test_capacity_fallback_cannot_select_multi_gpu_sizes(self):
        request=aws.launch_request(self.template(),'subnet','script','token',instance_type='g7e.4xlarge')
        self.assertEqual(request['InstanceType'],'g7e.4xlarge')
        self.assertEqual((request['MinCount'],request['MaxCount']),(1,1))
        g7=aws.launch_request(self.template(),'subnet','script','token',instance_type='g7.4xlarge')
        self.assertEqual((g7['InstanceType'],g7['MinCount'],g7['MaxCount']),('g7.4xlarge',1,1))
        with self.assertRaises(ValueError):
            aws.launch_request(self.template(),'subnet','script','token',instance_type='g7e.48xlarge')


if __name__=='__main__': unittest.main()
