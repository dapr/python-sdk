import json
from datetime import datetime, timedelta

from dapr.clients import DaprClient, Job
from google.protobuf.any_pb2 import Any as GrpcAny


def create_job_data(message: str):
    """Helper function to create job payload data."""
    data = GrpcAny()
    data.value = json.dumps({"message": message}).encode('utf-8')
    return data


def main():
    with DaprClient() as client:
        # Example 0: Simple job without data (works without protobuf)
        print("0. Scheduling a simple job without data...", flush=True)
        simple_job = Job(
            name="simple-job",
            schedule="@every 30s",
            overwrite=True
        )

        try:
            client.schedule_job_alpha1(simple_job)
            print(f"✓ Simple job scheduled successfully", flush=True)
        except Exception as e:
            print(f"✗ Failed to schedule simple job: {e}", flush=True)
            return

        # Example 1: Schedule a recurring job with cron schedule
        print("1. Scheduling a recurring job with cron schedule...", flush=True)
        job_data = create_job_data("Hello from recurring job!")
        recurring_job = Job(
            name="recurring-hello-job",
            schedule="@every 30s",
            data=job_data,
            ttl="5m",
            overwrite=True
        )

        try:
            client.schedule_job_alpha1(recurring_job)
            print(f"✓ Recurring job scheduled successfully", flush=True)
        except Exception as e:
            print(f"✗ Failed to schedule recurring job: {e}", flush=True)
            return

        # Example 2: Schedule a one-time job with due_time
        print("\n2. Scheduling a one-time job with due_time...", flush=True)
        due_time = (datetime.now() + timedelta(seconds=10)).isoformat() + "Z"
        one_time_job = Job(
            name="one-time-hello-job",
            due_time=due_time,
            data=create_job_data("Hello from one-time job!")
        )

        try:
            client.schedule_job_alpha1(one_time_job)
            print(f"✓ One-time job scheduled successfully", flush=True)
        except Exception as e:
            print(f"✗ Failed to schedule one-time job: {e}", flush=True)
            return

        # Example 3: Get job details
        print("\n3. Getting job details...", flush=True)
        try:
            job = client.get_job_alpha1("recurring-hello-job")
            print(f"✓ Retrieved job details:", flush=True)
            print(f"  - Name: {job.name}", flush=True)
            print(f"  - Schedule: {job.schedule}", flush=True)
            print(f"  - TTL: {job.ttl}", flush=True)
            if job.data:
                try:
                    payload = json.loads(job.data.value.decode('utf-8'))
                    print(f"  - Data: {payload}", flush=True)
                except Exception:
                    print(f"  - Data: <binary data, {len(job.data.value)} bytes>", flush=True)
            else:
                print(f"  - Data: None", flush=True)
        except Exception as e:
            print(f"✗ Failed to get job details: {e}", flush=True)

        # Example 4: Delete jobs
        print("\n4. Cleaning up - deleting jobs...", flush=True)
        for job_name in ["simple-job", "recurring-hello-job", "one-time-hello-job"]:
            try:
                client.delete_job_alpha1(job_name)
                print(f"✓ Deleted job: {job_name}", flush=True)
            except Exception as e:
                print(f"✗ Failed to delete job {job_name}: {e}", flush=True)



if __name__ == "__main__":
    main()
