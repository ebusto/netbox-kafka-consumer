import confluent_kafka
import inspect
import json
import logging
import pynetbox

from pynetbox.core.response import Record

class Client:
	def __init__(self, **kwargs):
		self.group   = kwargs['group']
		self.servers = kwargs['servers']

		self.api   = kwargs.get('api')
		self.topic = kwargs.get('topic', 'netbox')

		self.logger = logging.getLogger(__name__)

		self.subscriptions = []

	def poll(self, interval=1.0):
		consumer = confluent_kafka.Consumer({
			'bootstrap.servers':  self.servers,
			'group.id':           self.group,
			'enable.auto.commit': False,
		})

		consumer.subscribe([self.topic])

		# Listen for messages.
		while True:
			message = consumer.poll(interval)
		
			if message is None:
				continue
		
			if message.error():
				# _PARTITION_EOF = No more messages during this polling cycle.
				if message.error().code() != confluent_kafka.KafkaError._PARTITION_EOF:
					self.logger.error(message.error())

				continue
		
			# Decode the payload.
			data = json.loads(message.value().decode('utf-8'))

			# All possible parameters.
			params = data.copy()
			params.update({
				'message': data,
				'sender':  data['class'],
			})

			# Build the pynetbox record from the model.
			if self.api:
				params['record'] = Record(data['model'], self.api, None)

			# Retrieve the callback functions.
			for callback in self.callbacks(data):
				args = []

				# Build arguments according to the callback's signature.
				for name in inspect.signature(callback).parameters:
					args.append(params.get(name))

				callback(*args)

			consumer.commit(message)
	
		consumer.close()

	def callbacks(self, data):
		return [cb for (fn,cb) in self.subscriptions if fn(data['class'])]

	def matcher(self, arg):
		if callable(arg):
			return lambda v: arg(v)

		if isinstance(arg, bool):
			return lambda v: arg

		if isinstance(arg, list):
			return lambda v: v in arg

		if isinstance(arg, str):
			return lambda v: v == arg

		raise Exception('Unhandled match type: {}'.format(type(arg)))

	def subscribe(self, arg, cb):
		self.subscriptions.append((self.matcher(arg), cb))
