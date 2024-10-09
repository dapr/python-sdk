import asyncio

from dapr.aio.clients import DaprClient
from dapr.clients.grpc.subscription import StreamInactiveError

counter = 0


def process_message(message):
    global counter
    counter += 1
    # Process the message here
    print(f'Processing message: {message.data()} from {message.topic()}...')
    return 'success'


async def main():
    async with DaprClient() as client:
        global counter
        subscription = await client.subscribe(
            pubsub_name='pubsub', topic='TOPIC_A', dead_letter_topic='TOPIC_A_DEAD'
        )

        try:
            while counter < 5:
                try:
                    message = await subscription.next_message()

                except StreamInactiveError:
                    print('Stream is inactive. Retrying...')
                    await asyncio.sleep(1)
                    continue
                if message is None:
                    print('No message received within timeout period.')
                    continue

                # Process the message
                response_status = process_message(message)

                if response_status == 'success':
                    await subscription.respond_success(message)
                elif response_status == 'retry':
                    await subscription.respond_retry(message)
                elif response_status == 'drop':
                    await subscription.respond_drop(message)

        finally:
            print('Closing subscription...')
            await subscription.close()



if __name__ == '__main__':
    asyncio.run(main())
