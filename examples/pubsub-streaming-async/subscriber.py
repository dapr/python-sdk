import argparse
import asyncio

from dapr.aio.clients import DaprClient
from dapr.clients.grpc.subscription import StreamInactiveError
from dapr.common.pubsub.subscription import StreamCancelledError

parser = argparse.ArgumentParser(description='Publish events to a Dapr pub/sub topic.')
parser.add_argument('--topic', type=str, required=True, help='The topic name to publish to.')
args = parser.parse_args()

topic_name = args.topic
dlq_topic_name = topic_name + '_DEAD'

counter = 0


def process_message(message):
    global counter
    counter += 1
    # Process the message here
    print(f'Processing message: {message.data()} from {message.topic()}...', flush=True)
    return 'success'


async def main():
    async with DaprClient() as client:
        global counter
        subscription = await client.subscribe(
            pubsub_name='pubsub', topic=topic_name, dead_letter_topic=dlq_topic_name
        )

        try:
            async for message in subscription:
                if message is None:
                    print(
                        'No message received within timeout period. '
                        'The stream might have been cancelled.'
                    )
                    continue

                try:
                    # Process the message
                    response_status = process_message(message)

                    # Respond based on the processing result
                    if response_status == 'success':
                        await subscription.respond_success(message)
                    elif response_status == 'retry':
                        await subscription.respond_retry(message)
                    elif response_status == 'drop':
                        await subscription.respond_drop(message)

                    if counter >= 5:
                        break

                except StreamInactiveError:
                    print('Stream is inactive. Retrying...')
                    await asyncio.sleep(1)
                    continue
                except StreamCancelledError:
                    print('Stream was cancelled')
                    break

        finally:
            print('Closing subscription...')
            await subscription.close()


if __name__ == '__main__':
    asyncio.run(main())
