import json
import time
import random
import logging
import requests
import os

logging.basicConfig(level=logging.INFO)

base_url = os.getenv('BASE_URL', 'http://localhost') + ':' + os.getenv(
                    'DAPR_HTTP_PORT', '3500')
PUBSUB_NAME = 'pubsub'
TOPIC = 'mytopic'
ACTORTYPE = 'ActorTyping'

logging.info('Publishing to baseURL: %s, Pubsub Name: %s, Topic: %s' % (
            base_url, PUBSUB_NAME, TOPIC))

for i in range(10, 100):
    order = {'orderId': random.randint(0,i)}
    actorid = f'Actor Number: {i}'

    # Publish an event/message using Dapr PubSub via HTTP Post
    result = requests.post(
        url='%s/v1.0/actors/%s/%s/publish/%s/%s' % (base_url, ACTORTYPE, actorid, PUBSUB_NAME, TOPIC),
        json=order
    )
    logging.info('Published data: ' + json.dumps(order))

    time.sleep(3)