# -*- coding: utf-8 -*-
"""
Copyright 2025 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from dapr.ext.workflow import (  # noqa: E402
    AsyncWorkflowContext,
    DaprWorkflowClient,
    WorkflowActivityContext,
    WorkflowRuntime,
    WorkflowStatus,
)

"""Example demonstrating async activities with HTTP requests.

This example shows how to use async activities to perform I/O-bound operations
like HTTP requests without blocking the worker thread pool.
"""


wfr = WorkflowRuntime()


@wfr.activity(name='fetch_url')
async def fetch_url(ctx: WorkflowActivityContext, url: str) -> dict:
    """Async activity that fetches data from a URL.

    This demonstrates using aiohttp for non-blocking HTTP requests.
    In production, you would handle errors, timeouts, and retries.
    """
    try:
        import aiohttp
    except ImportError:
        # Fallback if aiohttp is not installed
        return {
            'url': url,
            'status': 'error',
            'message': 'aiohttp not installed. Install with: pip install aiohttp',
        }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                status = response.status
                if status == 200:
                    # For JSON responses
                    try:
                        data = await response.json()
                        return {'url': url, 'status': status, 'data': data}
                    except Exception:
                        # For text responses
                        text = await response.text()
                        return {
                            'url': url,
                            'status': status,
                            'length': len(text),
                            'preview': text[:100],
                        }
                else:
                    return {'url': url, 'status': status, 'error': 'HTTP error'}
    except Exception as e:
        return {'url': url, 'status': 'error', 'message': str(e)}


@wfr.activity(name='process_data')
def process_data(ctx: WorkflowActivityContext, data: dict) -> dict:
    """Sync activity that processes fetched data.

    This shows that sync and async activities can coexist in the same workflow.
    """
    return {
        'processed': True,
        'url_count': len([k for k in data if k.startswith('url_')]),
        'summary': f'Processed {len(data)} items',
    }


@wfr.async_workflow(name='fetch_multiple_urls_async')
async def fetch_multiple_urls(ctx: AsyncWorkflowContext, urls: list[str]) -> dict:
    """Orchestrator that fetches multiple URLs in parallel using async activities.

    This demonstrates:
    - Calling async activities from async workflows
    - Fan-out/fan-in pattern with async activities
    - Mixing async and sync activities
    """
    # Fan-out: Schedule all URL fetches in parallel
    fetch_tasks = [ctx.call_activity(fetch_url, input=url) for url in urls]

    # Fan-in: Wait for all to complete
    results = await ctx.when_all(fetch_tasks)

    # Create a dictionary of results
    data = {f'url_{i}': result for i, result in enumerate(results)}

    # Process the aggregated data with a sync activity
    summary = await ctx.call_activity(process_data, input=data)

    return {'results': data, 'summary': summary}


def main():
    """Run the example workflow."""
    # Example URLs to fetch (using httpbin.org for testing)
    test_urls = [
        'https://httpbin.org/json',
        'https://httpbin.org/uuid',
        'https://httpbin.org/user-agent',
    ]

    wfr.start()
    client = DaprWorkflowClient()

    try:
        instance_id = 'async_http_activity_example'
        print(f'Starting workflow {instance_id}...')

        # Schedule the workflow
        client.schedule_new_workflow(
            workflow=fetch_multiple_urls, instance_id=instance_id, input=test_urls
        )

        # Wait for completion
        wf_state = client.wait_for_workflow_completion(instance_id, timeout_in_seconds=60)

        print(f'\nWorkflow status: {wf_state.runtime_status}')

        if wf_state.runtime_status == WorkflowStatus.COMPLETED:
            print(f'Workflow output: {wf_state.serialized_output}')
            print('\n✓ Workflow completed successfully!')
        else:
            print('✗ Workflow did not complete successfully')
            return 1

    finally:
        wfr.shutdown()

    return 0


if __name__ == '__main__':
    import sys

    sys.exit(main())
