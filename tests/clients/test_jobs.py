#!/usr/bin/env python3

"""
Unit tests for the Job class and its proto conversion methods.
"""

import unittest
from google.protobuf.any_pb2 import Any as GrpcAny

from dapr.clients.grpc._jobs import Job, DropFailurePolicy, ConstantFailurePolicy
from dapr.proto.runtime.v1 import dapr_pb2 as api_v1


class TestJobClass(unittest.TestCase):
    """Test cases for the Job class and its proto conversion methods."""

    def test_job_creation(self):
        """Test Job dataclass creation."""
        # Test minimal job
        job = Job(name='test-job', schedule='@every 1m')
        self.assertEqual(job.name, 'test-job')
        self.assertEqual(job.schedule, '@every 1m')
        self.assertIsNone(job.repeats)
        self.assertIsNone(job.due_time)
        self.assertIsNone(job.ttl)
        self.assertIsNone(job.data)
        self.assertEqual(job.overwrite, False)

        # Test job with all fields
        data = GrpcAny()
        data.value = b'{"message": "test"}'

        job_full = Job(
            name='full-job',
            schedule='0 0 * * *',
            repeats=5,
            due_time='2024-01-01T00:00:00Z',
            ttl='1h',
            data=data,
            overwrite=True,
        )
        self.assertEqual(job_full.name, 'full-job')
        self.assertEqual(job_full.schedule, '0 0 * * *')
        self.assertEqual(job_full.repeats, 5)
        self.assertEqual(job_full.due_time, '2024-01-01T00:00:00Z')
        self.assertEqual(job_full.ttl, '1h')
        self.assertEqual(job_full.data, data)
        self.assertEqual(job_full.overwrite, True)

    def test_job_get_proto_full(self):
        """Test _get_proto() method with all fields."""
        data = GrpcAny()
        data.value = b'{"message": "test"}'

        job = Job(
            name='full-job',
            schedule='0 0 * * *',
            repeats=5,
            due_time='2024-01-01T00:00:00Z',
            ttl='1h',
            data=data,
            overwrite=True,
        )
        job_proto = job._get_proto()

        # Verify all proto fields
        self.assertIsInstance(job_proto, api_v1.Job)
        self.assertEqual(job_proto.name, 'full-job')
        self.assertEqual(job_proto.schedule, '0 0 * * *')
        self.assertEqual(job_proto.repeats, 5)
        self.assertEqual(job_proto.due_time, '2024-01-01T00:00:00Z')
        self.assertEqual(job_proto.ttl, '1h')
        self.assertTrue(job_proto.overwrite)

        # Verify data field
        self.assertTrue(job_proto.HasField('data'))
        self.assertEqual(job_proto.data.value, b'{"message": "test"}')

    def test_job_get_proto_no_data(self):
        """Test _get_proto() method when data is None."""
        job = Job(name='no-data-job', schedule='@every 1m', data=None)
        job_proto = job._get_proto()

        # Verify data field is set to empty Any
        self.assertTrue(job_proto.HasField('data'))
        self.assertEqual(job_proto.data.value, b'')

    def test_job_from_proto_no_data(self):
        """Test _from_proto() method with minimal proto."""
        # Create minimal proto
        job_proto = api_v1.Job(name='test-job', overwrite=False)
        job_proto.data.CopyFrom(GrpcAny())  # Empty data

        # Convert to Job
        job = Job._from_proto(job_proto)

        # Verify Job fields
        self.assertEqual(job.name, 'test-job')
        self.assertIsNone(job.schedule)
        self.assertIsNone(job.repeats)
        self.assertIsNone(job.due_time)
        self.assertIsNone(job.ttl)
        self.assertIsNone(job.data)  # Empty data becomes None
        self.assertEqual(job.overwrite, False)

    def test_job_from_proto_full(self):
        """Test _from_proto() method with all fields."""
        # Create full proto
        data = GrpcAny()
        data.value = b'{"message": "test"}'

        job_proto = api_v1.Job(
            name='full-job',
            schedule='0 0 * * *',
            repeats=5,
            due_time='2024-01-01T00:00:00Z',
            ttl='1h',
            overwrite=True,
        )
        job_proto.data.CopyFrom(data)

        # Convert to Job
        job = Job._from_proto(job_proto)

        # Verify all Job fields
        self.assertEqual(job.name, 'full-job')
        self.assertEqual(job.schedule, '0 0 * * *')
        self.assertEqual(job.repeats, 5)
        self.assertEqual(job.due_time, '2024-01-01T00:00:00Z')
        self.assertEqual(job.ttl, '1h')
        self.assertEqual(job.data.value, b'{"message": "test"}')
        self.assertTrue(job.overwrite)

    def test_job_with_drop_failure_policy(self):
        """Test Job with DropFailurePolicy."""
        drop_policy = DropFailurePolicy()
        job = Job(name='drop-job', schedule='@every 1m', failure_policy=drop_policy)

        # Convert to proto and back
        job_proto = job._get_proto()
        self.assertTrue(job_proto.HasField('failure_policy'))
        self.assertTrue(job_proto.failure_policy.HasField('drop'))

        # Convert back to Job
        job_from_proto = Job._from_proto(job_proto)
        self.assertIsInstance(job_from_proto.failure_policy, DropFailurePolicy)

    def test_job_with_constant_failure_policy(self):
        """Test Job with ConstantFailurePolicy."""
        constant_policy = ConstantFailurePolicy(max_retries=3, interval_seconds=10)
        job = Job(name='retry-job', schedule='@every 1m', failure_policy=constant_policy)

        # Convert to proto and back
        job_proto = job._get_proto()
        self.assertTrue(job_proto.HasField('failure_policy'))
        self.assertTrue(job_proto.failure_policy.HasField('constant'))
        self.assertEqual(job_proto.failure_policy.constant.max_retries, 3)
        self.assertEqual(job_proto.failure_policy.constant.interval.seconds, 10)

        # Convert back to Job
        job_from_proto = Job._from_proto(job_proto)
        self.assertIsInstance(job_from_proto.failure_policy, ConstantFailurePolicy)
        self.assertEqual(job_from_proto.failure_policy.max_retries, 3)
        self.assertEqual(job_from_proto.failure_policy.interval_seconds, 10)

    def test_job_with_constant_failure_policy_no_max_retries(self):
        """Test Job with ConstantFailurePolicy without max_retries."""
        constant_policy = ConstantFailurePolicy(interval_seconds=5)
        job = Job(name='retry-job', schedule='@every 1m', failure_policy=constant_policy)

        # Convert to proto and back
        job_proto = job._get_proto()
        self.assertTrue(job_proto.HasField('failure_policy'))
        self.assertTrue(job_proto.failure_policy.HasField('constant'))
        self.assertFalse(job_proto.failure_policy.constant.HasField('max_retries'))
        self.assertEqual(job_proto.failure_policy.constant.interval.seconds, 5)

        # Convert back to Job
        job_from_proto = Job._from_proto(job_proto)
        self.assertIsInstance(job_from_proto.failure_policy, ConstantFailurePolicy)
        self.assertIsNone(job_from_proto.failure_policy.max_retries)
        self.assertEqual(job_from_proto.failure_policy.interval_seconds, 5)

    def test_job_without_failure_policy(self):
        """Test Job without failure policy."""
        job = Job(name='no-policy-job', schedule='@every 1m')

        # Convert to proto and back
        job_proto = job._get_proto()
        self.assertFalse(job_proto.HasField('failure_policy'))

        # Convert back to Job
        job_from_proto = Job._from_proto(job_proto)
        self.assertIsNone(job_from_proto.failure_policy)


if __name__ == '__main__':
    unittest.main()
