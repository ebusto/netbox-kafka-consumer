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

		self.subscriptions = collections.defaultdict(list)

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
			data = message.value().decode('utf-8')
			data = json.loads(data)

			# Build the pynetbox record from the model.
			record = pynetbox.core.response.Record(data['model'], api=self.api, endpoint=None)

			# Retrieve the callback functions.
			for callback in self.callbacks(data):
				data.update({
					'record': record,
					'sender': data['class'],
				})

				# Build the arguments per the callback's signature.
				args = dict()

				for name in inspect.signature(callback).parameters:
					args[name] = data.get(name, None)

				callback(**args)

			consumer.commit(message)
	
		consumer.close()

	def callbacks(self, data):
		return self.subscriptions[data['class']]

	def subscribe(self, fn, *classes):
		for c in classes:
			self.subscriptions[c].append(fn)
