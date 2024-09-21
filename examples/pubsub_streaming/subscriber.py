from dapr.clients import DaprClient
from dapr.clients.grpc._response import TopicEventResponse
from dapr.clients.grpc.subscription import success, retry, drop


def process_message(message):
    # Process the message here
    print(f"Processing message: {message.data}")
    return  TopicEventResponse('success').status


def main():
    with DaprClient() as client:

        subscription = client.subscribe(pubsub_name="pubsub", topic="TOPIC_A", dead_letter_topic="TOPIC_A_DEAD")

        try:
            while True:
                try:
                    try:
                        message = subscription.next_message(timeout=5)
                    except Exception as e:
                        print(f"An error occurred: {e}")

                    if message is None:
                        print("No message received within timeout period.")
                        continue

                    print(f"Received message with ID: {message.id}")

                    # Process the message
                    try:
                        subscription.respond(message, process_message(message))
                    except Exception as e:
                        print(f"An error occurred while sending the message: {e}")
                except KeyboardInterrupt:
                    print("Received interrupt, shutting down...")
                    break

        finally:
            subscription.close()


if __name__ == "__main__":
    main()
