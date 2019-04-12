import inspect
import json

from confluent_kafka import Consumer, KafkaError, KafkaException

from pynetbox.core.response import Record

class Client:
	def __init__(self, **kwargs):
		self.group   = kwargs['group']
		self.servers = kwargs['servers']

		self.api   = kwargs.get('api')
		self.topic = kwargs.get('topic', 'netbox')

		self.subscriptions = []

	def poll(self):
		consumer = Consumer({
			'bootstrap.servers':    self.servers,
			'group.id':             self.group,
			'enable.auto.commit':   False,
			'enable.partition.eof': False,
		})

		consumer.subscribe([self.topic])

		# Listen for messages.
		while True:
			message = consumer.poll()
		
			if message.error():
				raise KafkaException(message.error())
		
			# Decode the payload.
			data = json.loads(message.value().decode('utf-8'))

			# Build parameters. Start with a copy to avoid circular references.
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
