import argparse
import time

from dapr.clients import DaprClient
from dapr.clients.grpc.subscription import StreamInactiveError
from dapr.common.pubsub.subscription import StreamCancelledError

counter = 0

parser = argparse.ArgumentParser(description='Publish events to a Dapr pub/sub topic.')
parser.add_argument('--topic', type=str, required=True, help='The topic name to publish to.')
args = parser.parse_args()

topic_name = args.topic
dlq_topic_name = topic_name + '_DEAD'


def process_message(message):
    global counter
    counter += 1
    # Process the message here
    print(f'Processing message: {message.data()} from {message.topic()}...', flush=True)
    return 'success'


def main():
    with DaprClient() as client:
        global counter

        try:
            subscription = client.subscribe(
                pubsub_name='pubsub', topic=topic_name, dead_letter_topic=dlq_topic_name
            )
        except Exception as e:
            print(f'Error occurred: {e}')
            return

        try:
            for message in subscription:
                if message is None:
                    print('No message received. The stream might have been cancelled.')
                    continue

                try:
                    response_status = process_message(message)

                    if response_status == 'success':
                        subscription.respond_success(message)
                    elif response_status == 'retry':
                        subscription.respond_retry(message)
                    elif response_status == 'drop':
                        subscription.respond_drop(message)

                    if counter >= 5:
                        break
                except StreamInactiveError:
                    print('Stream is inactive. Retrying...')
                    time.sleep(1)
                    continue
                except StreamCancelledError:
                    print('Stream was cancelled')
                    break
                except Exception as e:
                    print(f'Error occurred during message processing: {e}')

        finally:
            print('Closing subscription...')
            subscription.close()


if __name__ == '__main__':
    main()
