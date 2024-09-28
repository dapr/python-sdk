import time

from dapr.clients import DaprClient
from dapr.clients.grpc.subscription import StreamInactiveError


def process_message(message):
    # Process the message here
    print(f'Processing message: {message.data()} from {message.topic()}')
    return 'success'


def main():
    with DaprClient() as client:
        subscription = client.subscribe(
            pubsub_name='pubsub', topic='TOPIC_A', dead_letter_topic='TOPIC_A_DEAD'
        )

        try:
            i = 0
            while i < 5:
                i += 1
                try:
                    message = subscription.next_message(1)
                except StreamInactiveError as e:
                    print('Stream is inactive. Retrying...')
                    time.sleep(5)
                    continue
                if message is None:
                    print('No message received within timeout period.')
                    continue

                # Process the message
                response_status = process_message(message)

                if response_status == 'success':
                    subscription.respond_success(message)
                elif response_status == 'retry':
                    subscription.respond_retry(message)
                elif response_status == 'drop':
                    subscription.respond_drop(message)


        finally:
            subscription.close()


if __name__ == '__main__':
    main()
