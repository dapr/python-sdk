import argparse
import asyncio
from dapr.aio.clients import DaprClient
from dapr.clients.grpc._response import TopicEventResponse

parser = argparse.ArgumentParser(description='Publish events to a Dapr pub/sub topic.')
parser.add_argument('--topic', type=str, required=True, help='The topic name to publish to.')
args = parser.parse_args()

topic_name = args.topic
dlq_topic_name = topic_name + '_DEAD'

counter = 0


async def process_message(message) -> TopicEventResponse:
    """
    Asynchronously processes the message and returns a TopicEventResponse.
    """

    print(f'Processing message: {message.data()} from {message.topic()}...', flush=True)
    global counter
    counter += 1
    return TopicEventResponse('success')


async def main():
    """
    Main function to subscribe to a pubsub topic and handle messages asynchronously.
    """
    async with DaprClient() as client:
        # Subscribe to the pubsub topic with the message handler
        close_fn = await client.subscribe_with_handler(
            pubsub_name='pubsub',
            topic=topic_name,
            handler_fn=process_message,
            dead_letter_topic=dlq_topic_name,
        )

        # Wait until 5 messages are processed
        global counter
        while counter < 5:
            await asyncio.sleep(1)

        print('Closing subscription...')
        await close_fn()


if __name__ == '__main__':
    asyncio.run(main())
