"""
Copy a source RDS instance to a destination instance, optionally changing
the instance type. If it exists, the existing destination instance will be
overwritten. This tool was motivated by the need to create staging databases
that are periodically made to mimic production clones.

Copied instances will retain most characteristics from the source instances,
including:

    - Availability zones
    - DB subnet group
    - VPC security groups
    - DB security groups

Commandline arguments will be inherited from environment variables of the
same name, e.g. `export RDSCP_SRC_NAME=sys-clone` is equivalent to
`--src=sys-clone`.

AWS credentials and region must be provided a la `awscli`.

Log level can be set with the env var `LOG_LEVEL`, e.g. `LOG_LEVEL=debug`.


Usage:
    rds_cp [--force]
           [--src=<RDSCP_SRC_NAME>]
           [--dest=<RDSCP_DEST_NAME>]
           [--dest-class=<RDSCP_DEST_INSTANCE_CLASS>]
           [--new-password=<RDSCP_NEW_PASSWORD>]
    rds_cp (-h | --help)
    rds_cp --version

Options:
    -h --help                           Show this screen.
    --version                           Show version.
    --src=<RDSCP_SRC_NAME>              The identifier for the RDS instance
                                        to copy from.
    --dest=<RDSCP_DEST_NAME>            The identifier for the RDS instance to
                                        be copied to. If an instance of this
                                        name currently exists, it will be
                                        removed.
    --dest-class=<DEST_INSTANCE_CLASS>  The type of instance to instantiate
                                        for the destination instance, e.g.
                                        `db.m3.medium`.
    --new-password=<NEW_PASSWORD>       Specify a new master password for the
                                        destination database.
    --force                             If specified, do not prompt for the
                                        removal of an existing `dest` instance.

"""
import logging
import os
import time
from contextlib import contextmanager
from sys import exit

import boto3
import botocore
import docopt

from .version import __version__ as version

SNAPSHOT_FAILED_ERR = 1
DEST_CREATION_ERR = 2
DEST_RENAME_ERR = 3
SRC_EXISTS_ERR = 4

# A suffix applied during existing destination instance renames.
BACKUP_SUFFIX = '-rdscp-bak'

# A suffix applied to the snapshot of the src.
SNAPSHOT_SUFFIX = '-rdscp-temp'

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
log = logging.getLogger(__name__)
log.setLevel(LOG_LEVEL)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter(
    '[%(asctime)s:%(name)s:%(levelname)s] %(message)s'))
log.addHandler(ch)


def cp(rds,
       src_instance_name: str,
       dest_instance_name: str,
       dest_instance_class: str,
       new_password: str or None=None,
       force: bool=False) -> int:
    """
    Copy an RDS instance. If an instance named `dest_instance_name` exists,
    it will be replaced.

    - Create a snapshot of the source
    - Move the old destination to a backup (if it exists)
    - Create a new destination instance based on snapshot
        * If this fails, roll back to the old dest (if it exists)
    - Change the destination's password to `new_password` (if specified)
        * If this fails, delete the new dest and rollback
    - Delete the old, moved destination (prompt if `not force`)
    - Delete the snapshot

    Returns:
        int. specific error codes are used, 0 for success.

    """
    snapshot_name = src_instance_name + SNAPSHOT_SUFFIX
    dest_backup_name = dest_instance_name + BACKUP_SUFFIX

    try:
        src_described = rds.describe_db_instances(
            DBInstanceIdentifier=src_instance_name)
    except Exception:
        log.exception(
            "Wasn't able to describe instance %r. Does it exist?",
            src_instance_name)
        return SRC_EXISTS_ERR

    log.debug("Src %r described as %s", src_instance_name, src_described)

    # Certain parameters that we need to copy over manually for the dest.
    src_params = SrcParams.from_describe_dict(src_described)

    with _temp_snapshot(rds, snapshot_name, src_instance_name):
        is_existing_dest = instance_exists(rds, dest_instance_name)

        if is_existing_dest:
            renamed = rename_instance(
                rds, dest_instance_name, dest_backup_name)

            if not renamed:
                return DEST_RENAME_ERR

        new_dest_created = restore_instance(
            rds,
            dest_instance_name,
            snapshot_name,
            dest_instance_class,
            src_params,
        )

        if new_password is not None:
            succeeded = change_password(rds, dest_instance_name, new_password)

            if not succeeded:
                log.error(
                    "Couldn't change password on new instance %r; "
                    "deleting and rolling back",
                    dest_instance_name)
                delete_instance(rds, dest_instance_name)
                new_dest_created = False

        if not new_dest_created:
            if is_existing_dest:
                log.error(
                    "Restoring previous dest %r from rename",
                    dest_instance_name)
                rename_instance(rds, dest_backup_name, dest_instance_name)

            return DEST_CREATION_ERR

        if is_existing_dest:
            confirm = 'y'

            if not force:
                confirm = input(
                    "Delete old dest %r? [y/n]: " % dest_backup_name)

            if confirm == 'y':
                delete_instance(rds, dest_backup_name)

    log.info("done.")

    return 0


class SrcParams:
    """
    Encapsulates parameters that need to be copied over from the src instance
    manually.

    """
    def __init__(self,
                 AvailabilityZone: str,
                 DBSubnetGroupName: str,
                 VpcSecurityGroupIds: [str],
                 DBSecurityGroups: [str],
                 ):
        """
        See: http://boto3.readthedocs.org/en/latest/reference/services/rds.html

        """
        self.AvailabilityZone = AvailabilityZone
        self.DBSubnetGroupName = DBSubnetGroupName
        self.VpcSecurityGroupIds = VpcSecurityGroupIds
        self.DBSecurityGroups = DBSecurityGroups

    @classmethod
    def from_describe_dict(cls, describe_dict: dict):
        """`describe_dict` is the return of rds.describe_db_instances."""
        [db] = describe_dict['DBInstances']
        subnet_group = db.get('DBSubnetGroup')

        return cls(
            db['AvailabilityZone'],
            subnet_group['DBSubnetGroupName'] if subnet_group else '',
            [i['VpcSecurityGroupId'] for i in db['VpcSecurityGroups']],
            [i['DBSecurityGroupName'] for i in db['DBSecurityGroups']],
        )


def instance_exists(rds, instance_name: str) -> bool:
    """Return True if an instance exists named `instance_name`."""
    DB_NOT_FOUND_CODE = "DBInstanceNotFound"

    try:
        rds.describe_db_instances(DBInstanceIdentifier=instance_name)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == DB_NOT_FOUND_CODE:
            return False
        else:
            raise

    return True


def rename_instance(rds, instance_name: str, new_name: str) -> bool:
    """Rename an instance to a new identifier. Returns True if successful."""
    log.info("Renaming instance %r to %r", instance_name, new_name)
    try:
        rds.modify_db_instance(
            DBInstanceIdentifier=instance_name,
            NewDBInstanceIdentifier=new_name,
            ApplyImmediately=True)
    except Exception:
        log.exception(
            "Failed to rename RDS instance %r to %r", instance_name, new_name)
        return False

    # We have to manually sleep loop until the rename takes effect; boto3
    # doesn't provide a `waiter` for this.
    renamed_yet = False
    tries_left = 100

    while tries_left >= 0 and not renamed_yet:
        if instance_exists(rds, new_name):
            renamed_yet = True
        else:
            tries_left -= 1
            time.sleep(3)

    if not renamed_yet:
        log.fatal(
            "Waiting for %r rename timed out; "
            "the rename may happen regardless", new_name)
        return False

    return True


def change_password(rds, instance_name: str, new_password: str) -> bool:
    """
    Change the password on an instance.

    Don't block to ensure completion, since no other op in `rds_cp` depends
    on this change taking effect.

    Returns True if successful.

    """
    log.info("Changing password for %r", instance_name)
    try:
        rds.modify_db_instance(
            DBInstanceIdentifier=instance_name,
            MasterUserPassword=new_password,
            ApplyImmediately=True)
    except Exception:
        log.exception(
            "Failed to change password for RDS instance %r", instance_name)
        return False

    return True


def delete_instance(rds, instance_name: str) -> bool:
    """
    Delete an instance, blocking until deletion completes.

    Returns:
      True if an instance was deleted

    """
    if not instance_exists(rds, instance_name):
        log.info(
            "Instance %r doesn't exist, not attempting deletion",
            instance_name)
        return False

    log.info("Deleting instance %r", instance_name)

    try:
        rds.delete_db_instance(
            DBInstanceIdentifier=instance_name,
            SkipFinalSnapshot=True)
        waiter = rds.get_waiter('db_instance_deleted')

        waiter.wait(DBInstanceIdentifier=instance_name)
    except Exception:
        log.exception(
            "Unable to delete instance %r", instance_name)
        return False

    return True


def restore_instance(rds,
                     instance_name: str,
                     snapshot_name: str,
                     instance_class: str,
                     src_params: SrcParams,
                     ) -> bool:
    """
    Create an instance from a snapshot, blocking until creation is complete.

    Use `src_params` to merge in creation parameters that have been manually
    copied over from the src instance.

    """
    creation_kwargs = dict(
        DBInstanceIdentifier=instance_name,
        DBSnapshotIdentifier=snapshot_name,
        DBInstanceClass=instance_class,
        MultiAZ=False,
    )

    creation_kwargs.update(vars(src_params))

    log.info(
        "Creating new instance %r with kwargs: %s",
        instance_name, creation_kwargs)

    try:
        rds.restore_db_instance_from_db_snapshot(**creation_kwargs)
        waiter = rds.get_waiter('db_instance_available')
        waiter.wait(DBInstanceIdentifier=instance_name)
    except Exception:
        log.exception(
            "Unable to create instance %r", instance_name)
        return False

    return True


@contextmanager
def _temp_snapshot(rds, snapshot_name: str, src_instance_name: str):
    """
    Create a snapshot from the RDS instance `src_instance_name`,

    yield,

    then delete the snapshot.

    """
    log.info(
        "Creating snapshot %r from instance %r",
        snapshot_name, src_instance_name)

    try:
        rds.create_db_snapshot(
            DBSnapshotIdentifier=snapshot_name,
            DBInstanceIdentifier=src_instance_name)
    except Exception:
        log.exception("Unable to create snapshot %r", snapshot_name)
        exit(SNAPSHOT_FAILED_ERR)

    try:
        waiter = rds.get_waiter('db_snapshot_completed')
        waiter.wait(DBSnapshotIdentifier=snapshot_name)
    except Exception:
        log.exception(
            "Snapshot creation of %r didn't finish. "
            "Snapshot may or may not exist; manual intervention is needed.",
            snapshot_name)
        exit(SNAPSHOT_FAILED_ERR)

    try:
        yield
    finally:
        rds.delete_db_snapshot(DBSnapshotIdentifier=snapshot_name)
        log.debug("Deleted snapshot %r", snapshot_name)


def main():
    args = docopt.docopt(__doc__, version='rds_cp %s' % version)

    src_instance_name = os.environ.get(
        'RDSCP_SRC_NAME', args.get('--src'))
    dest_instance_name = os.environ.get(
        'RDSCP_DEST_NAME', args.get('--dest'))
    dest_instance_class = os.environ.get(
        'RDSCP_DEST_INSTANCE_CLASS', args.get('--dest-class'))
    new_password = os.environ.get(
        'RDSCP_NEW_PASSWORD', args.get('--new-password'))

    exit(cp(
        boto3.client('rds'),
        src_instance_name,
        dest_instance_name,
        dest_instance_class,
        new_password,
        args.get('--force'),
    ))


if __name__ == '__main__':
    main()
