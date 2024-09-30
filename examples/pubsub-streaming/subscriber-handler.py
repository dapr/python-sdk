import time

from dapr.clients import DaprClient
from dapr.clients.grpc.subscription import Subscription

counter = 0


def process_message(message):
    # Process the message here
    global counter
    counter += 1
    print(f'Processing message: {message.data()} from {message.topic()}...')
    return Subscription.SUCCESS


def main():
    with DaprClient() as client:
        # This will start a new thread that will listen for messages
        # and process them in the `process_message` function
        close_fn = client.subscribe_with_handler(
            pubsub_name='pubsub',
            topic='TOPIC_A',
            handler_fn=process_message,
            dead_letter_topic='TOPIC_A_DEAD',
        )

        while counter < 5:
            time.sleep(1)

        print('Closing subscription...')
        close_fn()


if __name__ == '__main__':
    main()
