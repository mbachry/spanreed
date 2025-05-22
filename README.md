# spanreed

Message bus and task manager using redis streams.

## Install

`pip install spanreed`

## Configuration

Django configuration is supported. Alternatively, create a settings
module and point `SPANREED_SETTINGS_MOUDULE` env variable to it.

Set `SPANREED_REDIS_URL` to your redis dsn.

Set `SPANREED_MODELS` to a list of import strings with your pydantic
classes (see below), eg. `SPANREED_MODELS = ('app.models.User',
'app.models.Permission')`.

Set `SPANREED_PUBLISHER` to your app name.

Set `SPANREED_QUEUE` to your environment name (eg. `staging`, `prod`).

Make sure all modules with tasks are imported at startup.

## Message bus usage

Messages are broadcast to all listening apps. Use them to synchronize
app state and implement "event sourcing" flows.

Create a message pydantic class by inheriting from `spanreed.models.BaseMessage`:

```
from spanreed.models import BaseMessage, Metadata

class UserCreated(BaseMessage):
    user_id: str

    def handle(self):
        print('got message', self)


user = UserCreated(user_id='id')
user.publish()
```

`publish` sends a message to the bus, `handle` is called by a daemon when a message is received.

Run the daemon with `spanreed-consumer --queue-type message` or
`manage.py spanreed_worker --queue-type message` if using Django.

## Task manager usage

Tasks are delivered only once inside a single app. Use them as celery
replacement.

Create a task:

```
from spanreed import task

@task
def frobnicate_user(user_id):
    frobnicate(user_id)

frobnicate_user.dispatch('uid')
```

`dispatch` sends a task to the bus, which will be invoked by a daemon.

Run the daemon with `spanreed-consumer --queue-type task` or
`manage.py spanreed_worker --queue-type task` if using Django.
