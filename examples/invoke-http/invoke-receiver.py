# from dapr.ext.grpc import App, InvokeMethodRequest, InvokeMethodResponse
from flask import Flask, request
import json

app = Flask(__name__)


@app.route('/my-method', methods=['POST'])
def getOrder():
    data = request.json
    print('Order received : ' + json.dumps(data), flush=True)
    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}


app.run(port=8088)
