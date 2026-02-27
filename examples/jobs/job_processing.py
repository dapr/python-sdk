# ------------------------------------------------------------
# Copyright 2024 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------

import json
import threading
import time

from dapr.ext.grpc import App, JobEvent

from dapr.clients import ConstantFailurePolicy, DaprClient, Job

try:
    from google.protobuf.any_pb2 import Any as GrpcAny

    PROTOBUF_AVAILABLE = True
except ImportError:
    PROTOBUF_AVAILABLE = False
    print(
        'Warning: protobuf not available, jobs with data will be scheduled without data', flush=True
    )

app = App()


def create_job_data(data_dict):
    """Create job data from a dictionary."""
    if not PROTOBUF_AVAILABLE:
        return None

    data = GrpcAny()
    data.value = json.dumps(data_dict).encode('utf-8')
    return data


# Job event handlers
@app.job_event('hello-job')
def handle_hello_job(job_event: JobEvent) -> None:
    """Handle the 'hello-job' job event."""
    print(f'Job event received: {job_event.name}', flush=True)

    if job_event.data:
        data_str = job_event.get_data_as_string()
        print(f'Job data: {data_str}', flush=True)
    else:
        print('Job data: None', flush=True)

    print('Hello job processing completed!', flush=True)


@app.job_event('data-job')
def handle_data_job(job_event: JobEvent) -> None:
    """Handle the 'data-job' job event with structured data."""
    print(f'Data job event received: {job_event.name}', flush=True)

    if job_event.data:
        try:
            data_str = job_event.get_data_as_string()
            job_data = json.loads(data_str)

            task_type = job_data.get('task_type', 'unknown')
            priority = job_data.get('priority', 'normal')
            items = job_data.get('items', 0)

            print(f'Processing {task_type} task with priority {priority}', flush=True)
            print(f'Processing {items} items...', flush=True)
            print('Data job processing completed!', flush=True)

        except json.JSONDecodeError as e:
            print(f'Failed to parse job data: {e}', flush=True)
    else:
        print('No data provided for data job', flush=True)


def schedule_jobs():
    """Schedule test jobs after the server starts."""
    # Wait for the server to fully start
    time.sleep(5)

    print('Scheduling jobs...', flush=True)

    try:
        # Create Dapr client
        with DaprClient() as client:
            # Calculate due times
            due_time_1 = '1s'
            due_time_2 = '3s'

            # Job 1: Simple hello job (no data)
            print(f'Scheduling hello-job for {due_time_1}...', flush=True)
            hello_job = Job(name='hello-job', due_time=due_time_1)
            client.schedule_job_alpha1(hello_job)
            print('✓ hello-job scheduled', flush=True)

            # Job 2: Data processing job (with JSON data)
            print(f'Scheduling data-job for {due_time_2}...', flush=True)
            job_data = {
                'task_type': 'data_processing',
                'priority': 'high',
                'items': 42,
                'source': 'test_data',
            }

            data_job = Job(
                name='data-job',
                due_time=due_time_2,
                data=create_job_data(job_data),
                failure_policy=ConstantFailurePolicy(max_retries=2, interval_seconds=5),
            )
            client.schedule_job_alpha1(data_job)
            print('✓ data-job scheduled', flush=True)

            print('Jobs scheduled! Waiting for execution...', flush=True)

    except Exception as e:
        print(f'✗ Failed to schedule jobs: {e}', flush=True)


if __name__ == '__main__':
    print('Dapr Jobs Example', flush=True)
    print('This server will:', flush=True)
    print('1. Register job event handlers', flush=True)
    print('2. Schedule test jobs', flush=True)
    print('3. Process job events when they trigger', flush=True)

    # Schedule jobs in a background thread after server starts
    threading.Thread(target=schedule_jobs, daemon=True).start()

    print('Starting gRPC server on port 50051...', flush=True)
    app.run(51054)
