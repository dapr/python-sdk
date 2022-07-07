# ------------------------------------------------------------
# Copyright 2022 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------

import logging
from flask_dapr import DaprApp
import json
from flask import Flask, request, jsonify
from cloudevents.http import from_http


app = Flask(__name__)
# dapr = DaprApp(app)

# Register Dapr pub/sub subscriptions
@app.route('/dapr/subscribe', methods=['GET'])
def subscribe():
    subscriptions = [{
        'pubsubname': 'pubsub',
        'topic': 'mytopic',
        'route': 'endpoint'
    }]
    print('Dapr pub/sub is subscribed to: ' + json.dumps(subscriptions))
    return jsonify(subscriptions)

# Dapr subscription in /dapr/subscribe sets up this route
@app.route('/endpoint', methods=['POST'])
def event_subscriber():
    event = from_http(request.headers, request.get_data())
    print('Subscriber received ActorID: %s' % event._attributes['actorid'], flush=True)
    print('Subscriber received ActorType: %s' % event._attributes['actortype'], flush=True)
    print('Subscriber received Order: %s' % event.data['orderId'], flush=True)
    return json.dumps({'success': True}), 200, {
        'ContentType': 'application/json'}


app.run(port=5001)

# @dapr.subscribe(pubsub='pubsub', topic='mytopic',route="/endpoint")
# def handlethis():
#   logging.INFO(request)
#   return "test", 200

# if __name__ == '__main__':
#   app.run(host='0.0.0.0', port=5000)