from dapr.clients import DaprClient
from dapr.clients.grpc._response import TopicEventResponse
from dapr.clients.grpc.subscription import success, retry, drop


def process_message(message):
    # Process the message here
    print(f"Processing message: {message}")
    return "success"


def main():
    with DaprClient() as client:

        subscription = client.subscribe(pubsub_name="pubsub", topic="TOPIC_A", dead_letter_topic="TOPIC_A_DEAD")

        try:
            for i in range(5):
                try:
                    message = subscription.next_message(timeout=0.1)
                    if message is None:
                        print("No message received within timeout period.")
                        continue

                    # Process the message
                    response_status = process_message(message)

                    if response_status == "success":
                        subscription.respond_success(message)
                    elif response_status == "retry":
                        subscription.respond_retry(message)
                    elif response_status == "drop":
                        subscription.respond_drop(message)

                except Exception as e:
                    print(f"Error getting message: {e}")
                    break

        finally:
            subscription.close()


if __name__ == "__main__":
    main()
