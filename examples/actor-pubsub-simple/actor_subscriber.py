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

from flask import Flask, request, jsonify
from flask_dapr import DaprApp

app = Flask(__name__)
dapr = DaprApp(app)

@dapr.subscribe(pubsub='pubsub', topic='mytopic')
def event_handler():
  body = request.get_json()
  print('Subscriber received ActorID: %s' % body["actorid"], flush=True)
  print('Subscriber received ActorType: %s' % body["actortype"], flush=True)
  print('Subscriber received Message: %s' % body["data"]["message"], flush=True)
  return jsonify({'success': True})

if __name__ == '__main__':
  app.run(host='0.0.0.0', port=5000)

