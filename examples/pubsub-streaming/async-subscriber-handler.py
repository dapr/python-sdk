import asyncio
from dapr.aio.clients import DaprClient
from dapr.clients.grpc._response import TopicEventResponse

counter = 0


async def process_message(message) -> TopicEventResponse:
    """
    Asynchronously processes the message and returns a TopicEventResponse.
    """

    print(f'Processing message: {message.data()} from {message.topic()}...')
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
            topic='TOPIC_A',
            handler_fn=process_message,
            dead_letter_topic='TOPIC_A_DEAD',
        )

        # Wait until 5 messages are processed
        global counter
        while counter < 5:
            print('Counter: ', counter)
            await asyncio.sleep(1)

        print('Closing subscription...')
        await close_fn()


if __name__ == '__main__':
    asyncio.run(main())
