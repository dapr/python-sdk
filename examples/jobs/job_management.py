import json
from datetime import datetime, timedelta

from google.protobuf.any_pb2 import Any as GrpcAny

from dapr.clients import ConstantFailurePolicy, DaprClient, DropFailurePolicy, Job


def create_job_data(message: str):
    """Helper function to create job payload data."""
    data = GrpcAny()
    data.value = json.dumps({'message': message}).encode('utf-8')
    return data


def main():
    with DaprClient() as client:
        # Example 0: Simple job without data (works without protobuf)
        print('0. Scheduling a simple job without data...', flush=True)
        simple_job = Job(name='simple-job', schedule='@every 30s')

        try:
            client.schedule_job_alpha1(job=simple_job, overwrite=True)
            print('✓ Simple job scheduled successfully', flush=True)
        except Exception as e:
            print(f'✗ Failed to schedule simple job: {e}', flush=True)
            return

        # Example 1: Schedule a recurring job with cron schedule
        print('1. Scheduling a recurring job with cron schedule...', flush=True)
        job_data = create_job_data('Hello from recurring job!')
        recurring_job = Job(
            name='recurring-hello-job',
            schedule='@every 30s',
            data=job_data,
            ttl='5m',
        )

        try:
            client.schedule_job_alpha1(job=recurring_job, overwrite=True)
            print('✓ Recurring job scheduled successfully', flush=True)
        except Exception as e:
            print(f'✗ Failed to schedule recurring job: {e}', flush=True)
            return

        # Example 2: Schedule a one-time job with due_time
        print('\n2. Scheduling a one-time job with due_time...', flush=True)
        due_time = (datetime.now() + timedelta(seconds=10)).isoformat() + 'Z'
        one_time_job = Job(
            name='one-time-hello-job',
            due_time=due_time,
            data=create_job_data('Hello from one-time job!'),
        )

        try:
            client.schedule_job_alpha1(one_time_job)
            print('✓ One-time job scheduled successfully', flush=True)
        except Exception as e:
            print(f'✗ Failed to schedule one-time job: {e}', flush=True)
            return

        # Example 3: Schedule jobs with failure policies
        print('\n3. Scheduling jobs with failure policies...', flush=True)

        # Job with drop failure policy (drops job if it fails to trigger)
        drop_policy_job = Job(
            name='drop-policy-job',
            schedule='@every 45s',
            data=create_job_data('Job with drop failure policy'),
            failure_policy=DropFailurePolicy(),
        )

        try:
            client.schedule_job_alpha1(job=drop_policy_job, overwrite=True)
            print('✓ Job with drop failure policy scheduled successfully', flush=True)
        except Exception as e:
            print(f'✗ Failed to schedule job with drop policy: {e}', flush=True)

        # Job with constant retry failure policy (retries with constant interval)
        constant_policy_job = Job(
            name='retry-policy-job',
            schedule='@every 60s',
            data=create_job_data('Job with constant retry policy'),
            failure_policy=ConstantFailurePolicy(max_retries=3, interval_seconds=10),
        )

        try:
            client.schedule_job_alpha1(job=constant_policy_job, overwrite=True)
            print('✓ Job with constant retry policy scheduled successfully', flush=True)
        except Exception as e:
            print(f'✗ Failed to schedule job with retry policy: {e}', flush=True)

        # Example 4: Get job details
        print('\n4. Getting job details...', flush=True)
        try:
            job = client.get_job_alpha1('recurring-hello-job')
            print('✓ Retrieved job details:', flush=True)
            print(f'  - Name: {job.name}', flush=True)
            print(f'  - Schedule: {job.schedule}', flush=True)
            print(f'  - TTL: {job.ttl}', flush=True)
            if job.data:
                try:
                    payload = json.loads(job.data.value.decode('utf-8'))
                    print(f'  - Data: {payload}', flush=True)
                except Exception:
                    print(f'  - Data: <binary data, {len(job.data.value)} bytes>', flush=True)
            else:
                print('  - Data: None', flush=True)
        except Exception as e:
            print(f'✗ Failed to get job details: {e}', flush=True)

        # Example 5: Delete jobs
        print('\n5. Cleaning up - deleting jobs...', flush=True)
        for job_name in [
            'simple-job',
            'recurring-hello-job',
            'one-time-hello-job',
            'drop-policy-job',
            'retry-policy-job',
        ]:
            try:
                client.delete_job_alpha1(job_name)
                print(f'✓ Deleted job: {job_name}', flush=True)
            except Exception as e:
                print(f'✗ Failed to delete job {job_name}: {e}', flush=True)


if __name__ == '__main__':
    main()
