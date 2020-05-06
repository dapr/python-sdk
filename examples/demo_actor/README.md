# DemoActor

## Prerequisites

* [Install Dapr standalone mode](https://github.com/dapr/cli#install-dapr-on-your-local-machine-standalone)
* [Install Python 3.8+](https://www.python.org/downloads/)

## Try DemoActor example

1. Run Demo Actor service in new terminal window
```bash
$ cd python-sdk
$ pip3 install -r ./tests/test-requirement.txt
$ export PYTHONPATH=`pwd`
$ cd examples/demo_actor/service
$ dapr run --app-id demo-actor --app-port 3000 python3 app.py
...
== APP ==  * Serving Flask app "DemoActorService" (lazy loading)
== APP ==  * Environment: production
== APP ==    WARNING: This is a development server. Do not use it in a production deployment.
== APP ==    Use a production WSGI server instead.
== APP ==  * Debug mode: off
== APP ==  * Running on http://127.0.0.1:3000/ (Press CTRL+C to quit)
== DAPR == time="2020-02-29T13:52:15-08:00" level=info msg="application discovered on port 3000"
== APP == 127.0.0.1 - - [29/Feb/2020 13:52:15] "GET /dapr/config HTTP/1.1" 200 -
...
== APP == Activate DemoActor actor!
== APP == 127.0.0.1 - - [01/Mar/2020 18:50:27] "POST /actors/DemoActor/1 HTTP/1.1" 200 -
== APP == 127.0.0.1 - - [01/Mar/2020 18:50:27] "PUT /actors/DemoActor/1/method/GetMyData HTTP/1.1" 200 -
== APP == 127.0.0.1 - - [01/Mar/2020 18:50:27] "PUT /actors/DemoActor/1/method/GetMyData HTTP/1.1" 200 -
== APP == 127.0.0.1 - - [01/Mar/2020 18:50:27] "PUT /actors/DemoActor/1/method/SetMyData HTTP/1.1" 200 -
== APP == 127.0.0.1 - - [01/Mar/2020 18:50:27] "PUT /actors/DemoActor/1/method/GetMyData HTTP/1.1" 200 -
...
```
2. Run Demo client in new terminal window
```bash
$ cd python-sdk
$ export PYTHONPATH=`pwd`
$ cd examples/demo_actor/client
# Run actor client
$ dapr run --app-id demo-client python3 demo_actor_client.py
...
== APP == b'{"data":"default","ts":"2020-03-02T02:50:27.381Z"}'
== APP == {'data': 'default', 'ts': datetime.datetime(2020, 3, 2, 2, 50, 27, 386000, tzinfo=tzutc())}
== APP == {'data': 'new_data', 'ts': datetime.datetime(2020, 3, 2, 2, 50, 27, 395000, tzinfo=tzutc())}
...
```
