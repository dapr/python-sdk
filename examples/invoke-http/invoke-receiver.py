# from dapr.ext.grpc import App, InvokeMethodRequest, InvokeMethodResponse
import json

from flask import Flask, request

app = Flask(__name__)


@app.route('/my-method', methods=['POST'])
def getOrder():
    data = request.json
    print('Order received : ' + json.dumps(data), flush=True)
    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}


@app.route('/my-method-err', methods=['POST'])
def getOrderErr():
    data = request.json
    print('Order error : ' + json.dumps(data), flush=True)
    resp = {'message': 'error occurred', 'errorCode': 'MY_CODE'}
    return json.dumps(resp), 503, {'ContentType': 'application/json'}


print('Starting Flask app on port 8088...', flush=True)
app.run(port=8088)
