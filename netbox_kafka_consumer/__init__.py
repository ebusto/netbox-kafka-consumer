import confluent_kafka
import collections
import inspect
import json
import logging
import pynetbox
import pynetbox.core.response

class Client:
	def __init__(self, **kwargs):
		self.api     = kwargs['api']
		self.group   = kwargs['group']
		self.servers = kwargs['servers']
		self.topic   = kwargs.get('topic', 'netbox')

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
		
			# Extract the payload, then unmarshal from JSON.
			data = json.loads(message.value().decode('utf-8'))

			# Build the pynetbox record from the model.
			record = pynetbox.core.response.Record(data['model'], self.api, None)

			# Retrieve the callback functions.
			for callback in self.callbacks(data):
				param = {}
				extra = {'raw': data, 'record': record, 'sender': data['class']}

				# Build arguments according to the callback's signature.
				for name in inspect.signature(callback).parameters:
					param[name] = data.get(name, extra.get(name, None))

				callback(**param)

			consumer.commit(message)
	
		consumer.close()

	def callbacks(self, data):
		return [cb for (fn,cb) in self.subscriptions if fn(data['class'])]

	def matcher(self, spec):
		if callable(spec):
			return lambda v: spec(v)

		if isinstance(spec, bool):
			return lambda v: spec

		if isinstance(spec, list):
			return lambda v: v in spec

		if isinstance(spec, str):
			return lambda v: v == spec

		raise Exception('Unhandled match type: {}'.format(type(match)))

	def subscribe(self, spec, cb):
		self.subscriptions.append((self.matcher(spec), cb))
