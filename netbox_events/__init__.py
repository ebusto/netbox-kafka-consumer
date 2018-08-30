from confluent_kafka import Consumer, KafkaError

import json
import logging
import uuid
import warnings

from pynetbox.lib.response import Record

# Silence useless urllib3 warnings.
warnings.simplefilter("ignore")

# Development and production Kafka servers.
SERVERS_DEV = ['sc-it-mq-dev-01', 'sc-it-mq-dev-02', 'sc-it-mq-dev-03']
SERVERS_PRD = ['sc-it-mq-prd-01', 'sc-it-mq-prd-02', 'sc-it-mq-prd-03']

DEFAULT_SERVERS = SERVERS_PRD

# Most Kafka errors are warnings, so simply display them.
DEFAULT_ERROR = lambda e: logging.getLogger(__name__).warning(e)

# Kafka consumer group.
DEFAULT_GROUP = uuid.uuid4().hex

# NetBox access token.
DEFAULT_TOKEN = None

class Client(object):
	def __init__(self, **kwargs):
		self.classes = dict()

		self.error   = kwargs.get('error',   DEFAULT_ERROR)
		self.group   = kwargs.get('group',   DEFAULT_GROUP)
		self.servers = kwargs.get('servers', DEFAULT_SERVERS)
		self.token   = kwargs.get('token',   DEFAULT_TOKEN)

	def ignore(self, *args):
		print(args)

	def poll(self, interval=1.0):
		self.servers = ','.join(self.servers)

		consumer = Consumer({
			'bootstrap.servers':  self.servers,
			'group.id':           self.group,
			'enable.auto.commit': False,
		})

		consumer.subscribe(['netbox'])

		# Listen for messages.
		while True:
			message = consumer.poll(interval)
		
			if message is None:
				continue
		
			if message.error():
				# _PARTITION_EOF = No more messages during this polling cycle.
				if message.error().code() != KafkaError._PARTITION_EOF:
					self.error(message.error())

				continue
		
			# Extract the payload, then unmarshal from JSON.
			data = message.value().decode('utf-8')
			data = json.loads(data)

			# Retrieve the callback function, with a default to ignore.
			fn = self.classes.get(data['class'], self.ignore)

			# Build the NetBox API arguments.
			api = { 'ssl_verify': False, 'token': self.token }

			# Build the pynetbox record from the model.
			model = Record(data['model'], api_kwargs=api)
	
			try:
				fn(data, model)
			except Exception as e:
				print(e)
			else:
				consumer.commit(message)
	
		consumer.close()

	def subscribe(self, classes, fn):
		for c in classes:
			self.classes[c] = fn
