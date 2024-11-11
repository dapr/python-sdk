import argparse
import time

from dapr.clients import DaprClient
from dapr.clients.grpc._response import TopicEventResponse

counter = 0

parser = argparse.ArgumentParser(description='Publish events to a Dapr pub/sub topic.')
parser.add_argument('--topic', type=str, required=True, help='The topic name to publish to.')
args = parser.parse_args()

topic_name = args.topic
dlq_topic_name = topic_name + '_DEAD'


def process_message(message):
    # Process the message here
    global counter
    counter += 1
    print(f'Processing message: {message.data()} from {message.topic()}...', flush=True)
    return TopicEventResponse('success')


def main():
    with DaprClient() as client:
        # This will start a new thread that will listen for messages
        # and process them in the `process_message` function
        close_fn = client.subscribe_with_handler(
            pubsub_name='pubsub',
            topic=topic_name,
            handler_fn=process_message,
            dead_letter_topic=dlq_topic_name,
        )

        while counter < 5:
            time.sleep(1)

        print('Closing subscription...')
        close_fn()


if __name__ == '__main__':
    main()
