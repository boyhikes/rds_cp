
import unittest
from unittest import mock

from rds_cp import rds_cp
from .data import describe_response


class TestCp(unittest.TestCase):
    """
    Test the main functionality of rds_cp in a very mocky way.

    """

    class Client(mock.MagicMock):
        describe_db_instances = mock.MagicMock(
            return_value=describe_response.response)

    def test_allgood(self):
        """
        Test that when everything returns as expected, there're no
        errors.

        """
        client = self.Client()
        call_to_count = {
            # Listed in order of occurrence
            'create_db_snapshot': 1,
            'modify_db_instance': 2,
            'restore_db_instance_from_db_snapshot': 1,
            'delete_db_instance': 1,
            'delete_db_snapshot': 1,
        }

        self.assertEquals(
            rds_cp.cp(client, 'src', 'dest', 'db.m3.medium', 'newpass', True),
            0,
        )

        self._check_call_counts(client, call_to_count)

        client.restore_db_instance_from_db_snapshot.assert_called_with(
            AvailabilityZone='us-west-1a',
            DBSecurityGroups=[],
            VpcSecurityGroupIds=['sg-bbbbbdd'],
            DBSubnetGroupName='rds',
            DBSnapshotIdentifier='src' + rds_cp.SNAPSHOT_SUFFIX,
            DBInstanceClass='db.m3.medium',
            MultiAZ=False,
            DBInstanceIdentifier='dest',
        )

    def test_no_dest(self):
        """
        Ensure that when no destination exists, nothing is deleted or renamed.

        """
        client = self.Client()
        call_to_count = {
            # Listed in order of occurrence
            'create_db_snapshot': 1,
            'modify_db_instance': 0,
            'restore_db_instance_from_db_snapshot': 1,
            'delete_db_instance': 0,
            'delete_db_snapshot': 1,
        }

        def fake_instance_exists(rds, name):
            return name != 'dest'

        with mock.patch('rds_cp.rds_cp.instance_exists', fake_instance_exists):
            rds_cp.cp(client, 'src', 'dest', 'db.m3.medium', None, True)

        self._check_call_counts(client, call_to_count)

    def test_failed_snapshot(self):
        """
        Ensure that when a snapshot fails, nothing else happens and
        we exit with the right code.

        """
        call_to_count = {
            # Listed in order of occurrence
            'create_db_snapshot': 1,
            'modify_db_instance': 0,
            'restore_db_instance_from_db_snapshot': 0,
            'delete_db_instance': 0,
            'delete_db_snapshot': 0,
        }

        class BadClient(self.Client):
            create_db_snapshot = mock.MagicMock(side_effect=Exception)

        client = BadClient()

        try:
            rds_cp.cp(client, 'src', 'dest', 'db.m3.medium', None, True)
        except SystemExit as e:
            self.assertTrue(isinstance(e, SystemExit))
            self.assertEquals(e.code, rds_cp.SNAPSHOT_FAILED_ERR)
        else:
            assert False, "Should've raised an exit error."

        self._check_call_counts(client, call_to_count)

    def test_failed_restore(self):
        """
        Failure to restore from a snapshot => roll back to the old instance.

        """
        call_to_count = {
            # Listed in order of occurrence
            'create_db_snapshot': 1,
            'modify_db_instance': 2,
            'restore_db_instance_from_db_snapshot': 1,
            'delete_db_instance': 0,
            'delete_db_snapshot': 1,
        }

        class BadClient(self.Client):
            restore_db_instance_from_db_snapshot = mock.MagicMock(
                side_effect=Exception)

        client = BadClient()

        exit_code = rds_cp.cp(
            client, 'src', 'dest', 'db.m3.medium', None, True)
        self.assertEquals(exit_code, rds_cp.DEST_CREATION_ERR)

        self._check_call_counts(client, call_to_count)

    def test_failed_dest_rename(self):
        """
        Failure to rename the existing dest cleans up with proper exit code.

        """
        call_to_count = {
            # Listed in order of occurrence
            'create_db_snapshot': 1,
            'modify_db_instance': 1,
            'restore_db_instance_from_db_snapshot': 0,
            'delete_db_instance': 0,
            'delete_db_snapshot': 1,
        }

        class BadClient(self.Client):
            modify_db_instance = mock.MagicMock(side_effect=Exception)

        client = BadClient()

        exit_code = rds_cp.cp(
            client, 'src', 'dest', 'db.m3.medium', force=True)
        self.assertEquals(exit_code, rds_cp.DEST_RENAME_ERR)

        self._check_call_counts(client, call_to_count)

    def test_failed_restore_without_rollback(self):
        """
        Failure to restore from a snapshot without an existing destination
        means no rollback.

        """
        call_to_count = {
            # Listed in order of occurrence
            'create_db_snapshot': 1,
            'modify_db_instance': 0,
            'restore_db_instance_from_db_snapshot': 1,
            'delete_db_instance': 0,
            'delete_db_snapshot': 1,
        }

        class BadClient(self.Client):
            restore_db_instance_from_db_snapshot = mock.MagicMock(
                side_effect=Exception)

        client = BadClient()

        def fake_instance_exists(rds, name):
            return name != 'dest'

        with mock.patch('rds_cp.rds_cp.instance_exists', fake_instance_exists):
            exit_code = rds_cp.cp(
                client, 'src', 'dest', 'db.m3.medium', force=True)

        self.assertEquals(exit_code, rds_cp.DEST_CREATION_ERR)

        self._check_call_counts(client, call_to_count)

    def test_cant_describe(self):
        """
        Test that we exit early when we can't describe SRC.

        """
        call_to_count = {
            # Listed in order of occurrence
            'create_db_snapshot': 0,
            'modify_db_instance': 0,
            'restore_db_instance_from_db_snapshot': 0,
            'delete_db_instance': 0,
            'delete_db_snapshot': 0,
        }

        class BadClient(self.Client):
            describe_db_instances = mock.MagicMock(side_effect=Exception)

        client = BadClient()
        exit_code = rds_cp.cp(client, 'src', 'dest', 'db.m3.medium')

        self.assertEquals(exit_code, rds_cp.SRC_EXISTS_ERR)
        self._check_call_counts(client, call_to_count)

    def test_cant_change_password(self):
        """
        Test that we rollback to original dest if we can't change password.

        """
        client = self.Client()
        call_to_count = {
            'create_db_snapshot': 1,

            # one for initial rename, one for dest rollback
            'modify_db_instance': 2,

            'restore_db_instance_from_db_snapshot': 1,
            'delete_db_instance': 1,
            'delete_db_snapshot': 1,
        }

        def fake_change_pass(rds, name, new_pass):
            return name != 'dest'

        with mock.patch('rds_cp.rds_cp.change_password', fake_change_pass):
            exit_code = rds_cp.cp(
                client, 'src', 'dest', 'db.m3.medium', 'pass', True)

        self.assertEquals(exit_code, rds_cp.DEST_CREATION_ERR)

        self._check_call_counts(client, call_to_count)

    def _check_call_counts(self,
                           client: mock.MagicMock,
                           call_to_count: {str: int}):
        """
        Ensure that the client was called according to the number of calls
        listed for each method name.

        """
        for method_name, exp_call_count in call_to_count.items():
            print(getattr(client, method_name))
            self.assertEquals(
                getattr(client, method_name).call_count,
                exp_call_count,
                "%r should have been called %d times." %
                (method_name, exp_call_count)
            )


class TestSrcParams(unittest.TestCase):

    def test_from_describe_dict(self):
        src_params = rds_cp.SrcParams.from_describe_dict(
            describe_response.response)

        self.assertEquals(
            src_params.AvailabilityZone,
            'us-west-1a',
        )

        self.assertEquals(
            src_params.DBSubnetGroupName,
            'rds'
        )

        self.assertEquals(
            src_params.VpcSecurityGroupIds,
            ['sg-bbbbbdd'],
        )

        self.assertEquals(
            src_params.DBSecurityGroups,
            []
        )
