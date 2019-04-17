import confluent_kafka
import inspect
import json

from pynetbox.core.endpoint import Endpoint
from pynetbox.core.response import Record

from urllib.parse import urlparse

class Client:
	def __init__(self, **kwargs):
		self.group   = kwargs['group']
		self.servers = kwargs['servers']

		self.api   = kwargs.get('api')
		self.topic = kwargs.get('topic', 'netbox')

		self.subscriptions = []

		# Although the Kafka consumer requires a string, a list is tidier.
		if isinstance(self.servers, list):
			self.servers = ','.join(self.servers)

	def poll(self):
		consumer = confluent_kafka.Consumer({
			'bootstrap.servers':       self.servers,
			'group.id':                self.group,
			'enable.auto.commit':      False,
			'enable.partition.eof':    False,
			'socket.keepalive.enable': True,
		})

		consumer.subscribe([self.topic])

		# Listen for messages.
		while True:
			message = consumer.poll()
		
			if message.error():
				raise confluent_kafka.KafkaException(message.error())
		
			# Decode the payload.
			values = json.loads(message.value().decode('utf-8'))

			# Build parameters. Start with a copy to avoid circular references.
			params = values.copy()

			params.update({
				'message': values,
				'sender':  values['class'],
			})

			# Build the pynetbox record from the model.
			if self.api:
				endpoint = None

				# The format of @url is:
				#   <scheme>://<hostname>:<port>/api/<app>/<endpoint>/<pk>/
				if '@url' in values:
					url = urlparse(values['@url'])
					url = url.path.split('/')

					# ['', 'api', '<app>', '<endpoint>', '<pk>', '']
					endpoint = Endpoint(self.api, getattr(self.api, url[2]), url[3])

				params['record'] = Record(values['model'], self.api, endpoint)

			# Retrieve the callback functions.
			for callback in self.callbacks(values):
				args = []

				# Build arguments according to the callback's signature.
				for name in inspect.signature(callback).parameters:
					args.append(params.get(name))

				callback(*args)

			consumer.commit(message)
	
		consumer.close()

	# Returns the callbacks that match the message.
	def callbacks(self, message):
		return [cb for (cb, fn) in self.subscriptions if fn(message)]

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

	def subscribe(self, cb, classes=True, events=True):
		filters = [
			self.matcher('class', classes),
			self.matcher('event', events),
		]

		fn = lambda m: all(map(lambda fn: fn(m), filters))

		self.subscriptions.append((cb, fn))
