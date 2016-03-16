#!/usr/bin/env python
"""
This creates LIVE RESOURCES that will be torn down afterwards.

Requires that the following environment variables be present:

    - AWS_DEFAULT_REGION (preferably one where nothing currently exists)
    - AWS_ACCESS_KEY_ID
    - AWS_SECRET_ACCESS_KEY

"""
import logging

import boto3

from rds_cp import rds_cp


INSTANCE_TYPE = 'db.t1.micro'

log = logging.getLogger(__name__)
log.setLevel('INFO')
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter(
    '[%(asctime)s:test] %(message)s'))
log.addHandler(ch)


def run():
    exit_code = 0
    passed = lambda: log.info('passed.')
    src_name = 'temporary-rds-cp-test-source'
    dest_name = 'temporary-rds-cp-test-destination'

    rds = boto3.client('rds')
    log.info("Creating test instance %r." % src_name)
    _create_db_instance(rds, src_name, INSTANCE_TYPE)

    try:
        log.info("Testing cp with no existing destination...")
        rds_cp.cp(rds, src_name, dest_name, INSTANCE_TYPE, 'new_pass')
        passed()

        log.info("Ensuring src instance is still alive...")
        rds.describe_db_instances(DBInstanceIdentifier=src_name)
        passed()

        log.info("Ensuring dest instance exists...")
        resp = rds.describe_db_instances(DBInstanceIdentifier=dest_name)
        _check_created_instance(resp, dest_name)
        passed()

        log.info("Testing cp with an existing destination...")
        rds_cp.cp(rds, src_name, dest_name, INSTANCE_TYPE, 'new_pass', True)
        passed()

        log.info("Ensuring dest instance exists...")
        resp = rds.describe_db_instances(DBInstanceIdentifier=dest_name)
        _check_created_instance(resp, dest_name)
        passed()
    except Exception:
        log.exception("Tests failed.")
        exit_code = 1
    finally:
        log.info("Tearing down...")
        rds_cp.delete_instance(rds, src_name)
        rds_cp.delete_instance(rds, dest_name)

    return exit_code


def _create_db_instance(rds, name, instance_type):
    rds.create_db_instance(
        DBName='test',
        DBInstanceIdentifier=name,
        AllocatedStorage=10,
        DBInstanceClass=instance_type,
        Engine='postgres',
        MasterUsername='root',
        MasterUserPassword='sosecretz',
        BackupRetentionPeriod=0,
    )
    waiter = rds.get_waiter('db_instance_available')
    waiter.wait(DBInstanceIdentifier=name)


def _check_created_instance(response, name):
    db = response['DBInstances'][0]
    assert db['DBInstanceIdentifier'] == name
    assert db['DBInstanceClass'] == INSTANCE_TYPE

if __name__ == '__main__':
    exit(run())
