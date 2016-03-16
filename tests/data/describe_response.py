"""
Mock data for `rds.describe_instances`.

"""
import datetime

db = {
    'AllocatedStorage': 100,
    'AutoMinorVersionUpgrade': True,
    'AvailabilityZone': 'us-west-1a',
    'BackupRetentionPeriod': 0,
    'CACertificateIdentifier': 'rds-ca-2015',
    'CopyTagsToSnapshot': False,
    'DBInstanceClass': 'db.m3.large',
    'DBInstanceIdentifier': 'o-clone',
    'DBInstanceStatus': 'available',
    'DBName': 'w',
    'DBParameterGroups': [{'DBParameterGroupName': 'o-clone',
                            'ParameterApplyStatus': 'in-sync'}],
    'DBSecurityGroups': [],
    'DBSubnetGroup': {
        'DBSubnetGroupDescription': 'RDS instances',
        'DBSubnetGroupName': 'rds',
        'SubnetGroupStatus': 'Complete',
        'Subnets': [{'SubnetAvailabilityZone': {'Name': 'us-west-1a'},
                        'SubnetIdentifier': 'subnet-bbbbbb08',
                        'SubnetStatus': 'Active'},
                    {'SubnetAvailabilityZone': {'Name': 'us-west-1a'},
                        'SubnetIdentifier': 'subnet-bbbbbb58',
                        'SubnetStatus': 'Active'},
                    {'SubnetAvailabilityZone': {'Name': 'us-west-1a'},
                        'SubnetIdentifier': 'subnet-bbbbbbbe',
                        'SubnetStatus': 'Active'}],
        'VpcId': 'vpc-bbbbbb50'},
    'DbInstancePort': 0,
    'DbiResourceId': 'db-xx',
    'DomainMemberships': [],
    'Endpoint': {'Address': 'o-clone.xx.us-west-2.rds.amazonaws.com',
                 'Port': 5432},
    'Engine': 'postgres',
    'EngineVersion': '9.4.1',
    'InstanceCreateTime': datetime.datetime(
        2015, 5, 20, 21, 46, 51, 884000),
    'KmsKeyId': 'arn:aws:kms:us-west-2:111111111139:key/xx',
    'LicenseModel': 'postgresql-license',
    'MasterUsername': 'wetlab_o',
    'MultiAZ': False,
    'OptionGroupMemberships': [{
        'OptionGroupName': 'default:postgres-9-4', 'Status': 'in-sync'}],
    'PendingModifiedValues': {},
    'PreferredBackupWindow': '09:37-10:07',
    'PreferredMaintenanceWindow': 'fri:12:01-fri:12:31',
    'PubliclyAccessible': False,
    'ReadReplicaDBInstanceIdentifiers': [],
    'ReadReplicaSourceDBInstanceIdentifier': 'o-prod',
    'StatusInfos': [{'Normal': True,
                     'Status': 'replicating',
                     'StatusType': 'read replication'}],
    'StorageEncrypted': True,
    'StorageType': 'gp2',
    'VpcSecurityGroups': [{'Status': 'active',
                           'VpcSecurityGroupId': 'sg-bbbbbdd'}]}

response = {
    'DBInstances': [db],
    'ResponseMetadata': {
        'HTTPStatusCode': 200,
        'RequestId': 'e28fea01-4205-11e5-a81e-338c703bbbbb',
    }
}
