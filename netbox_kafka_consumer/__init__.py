import atexit
import confluent_kafka
import inspect
import json
import socket
import sys

import pynetbox.core.endpoint
import pynetbox.core.response

if (sys.version_info < (3, 0)):
    from future.moves.urllib.parse import urlparse
    import funcsigs

    signature = funcsigs.signature
else:
    from urllib.parse import urlparse

    signature = inspect.signature


class DispatchException(Exception):
    pass


class Client:
    def __init__(self, **kwargs):
        self.group   = kwargs['group']
        self.servers = kwargs['servers']

        self.api   = kwargs.get('api')
        self.topic = kwargs.get('topic', 'netbox')

        self.subscriptions = []

        # Expand the hostname into all IP addresses.
        # gethostbyname_ex returns a tuple: (hostname, aliases, ip_addresses)
        if isinstance(self.servers, str):
            self.servers = socket.gethostbyname_ex(self.servers)[2]

        # The Kafka consumer requires a comma delimited string of brokers.
        if isinstance(self.servers, list):
            self.servers = ','.join(self.servers)

    def poll(self, on_error=None, on_idle=None, timeout=1.0):
        consumer = confluent_kafka.Consumer({
            'bootstrap.servers':       self.servers,
            'group.id':                self.group,
            'enable.auto.commit':      False,
            'enable.partition.eof':    False,
            'socket.keepalive.enable': True,
        })

        consumer.subscribe([self.topic])

        atexit.register(consumer.close)

        # Listen for messages.
        while True:
            # Without a timeout, KeyboardInterrupt is ignored.
            message = consumer.poll(timeout=timeout)

            # No message was received before the timeout.
            if not message:
                if callable(on_idle):
                    on_idle()

                continue

            if message.error():
                raise confluent_kafka.KafkaException(message.error())

            try:
                self.dispatch(message)
            except Exception as err:
                if not callable(on_error):
                    raise DispatchException(err)

                on_error(err)

            consumer.commit(message)

    # Returns the callbacks that match the message payload.
    def callbacks(self, values):
        return [cb for (cb, fn) in self.subscriptions if fn(values)]

    # Calls matching callbacks for the message.
    def dispatch(self, message):
        # Decode the payload.
        values = message.value().decode('utf-8')
        values = json.loads(values)

        callbacks = self.callbacks(values)

        # No matching callbacks.
        if not callbacks:
            return

        # Start with a copy to avoid circular references.
        params = values.copy()

        params.update({
            'message': values,
            'sender':  values['class'],
            'record':  self.record(values),
        })

        # Call each callback.
        for cb in callbacks:
            args = []

            # Build arguments according to the callback's signature.
            for name in signature(cb).parameters:
                args.append(params.get(name))

            cb(*args)

    # Simple decorator for subscribing.
    def match(self, classes=True, events=True):
        def decorate(cb):
            self.subscribe(cb, classes, events)

            return cb

        return decorate

    # Returns a matching function for the message key, based on the value type.
    def matcher(self, key, value):
        if callable(value):
            return lambda m: value(m[key])

        if isinstance(value, bool):
            return lambda m: value

        if isinstance(value, list):
            return lambda m: m[key] in value

        if isinstance(value, str):
            return lambda m: m[key] == value

        raise Exception('Unmatchable: key = {}, value = {}'.format(key, value))

    # Returns a pynetbox record from the payload, if possible.
    def record(self, values):
        if not self.api:
            return None

        end = None

        # The format of @url is: <base_url>/api/<app>/<endpoint>/<pk>/
        if '@url' in values:
            url = urlparse(values['@url'])
            url = url.path.split('/')

            # url: ['', 'api', '<app>', '<endpoint>', '<pk>', '']
            (app, endpoint) = (url[2], url[3])

            # Is the app registered with pynetbox?
            if hasattr(self.api, app):
                app = getattr(self.api, app)
                end = pynetbox.core.endpoint.Endpoint(self.api, app, endpoint)

        return pynetbox.core.response.Record(values['model'], self.api, end)

    def subscribe(self, cb, classes=True, events=True):
        filters = [
            self.matcher('class', classes),
            self.matcher('event', events),
        ]

        fn = lambda m: all(map(lambda fn: fn(m), filters))

        self.subscriptions.append((cb, fn))
