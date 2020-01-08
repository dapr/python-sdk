from flask import Flask, jsonify
from flask_dapr.actor import DaprActor
import demo_actor

app = Flask(__name__)
actor = DaprActor(app)

# register DemoActor
actor.actor_runtime.register_actor(demo_actor.DemoActor)

@app.route('/')
def index():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run()