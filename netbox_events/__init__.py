from confluent_kafka import Consumer, KafkaError

import json
import logging
import uuid

# Development and production Kafka servers.
KAFKA_DEV = ['sc-it-mq-dev-01', 'sc-it-mq-dev-02', 'sc-it-mq-dev-03']
KAFKA_PRD = ['sc-it-mq-prd-01', 'sc-it-mq-prd-02', 'sc-it-mq-prd-03']

DEFAULT_SERVERS = KAFKA_PRD

# Most Kafka errors are warnings, so simply display them.
DEFAULT_ERROR = lambda error: logging.getLogger(__name__).warning(error)

# Kafka consumer group.
DEFAULT_GROUP = uuid.uuid4().hex

class Client(object):
	def __init__(self, **kwargs):
		self.classes = dict()

		self.error   = kwargs.get('error',   DEFAULT_ERROR)
		self.group   = kwargs.get('group',   DEFAULT_GROUP)
		self.servers = kwargs.get('servers', DEFAULT_SERVERS)

	def poll(self, interval=1.0):
		self.servers = ','.join(self.servers)

		options = {
			'bootstrap.servers':  self.servers,
			'group.id':           self.group,
			'enable.auto.commit': False,
		}

		consumer = Consumer(options)
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
			event = json.loads(message.value().decode('utf-8'))
	
			# Is there a callback for this class?
			if event['class'] in self.classes:
				try:
					self.classes[event['class']](event)
				except Exception as e:
					self.error(e)
				else:
					consumer.commit(message)
	
		consumer.close()

	def subscribe(self, classes, fn):
		for c in classes:
			self.classes[c] = fn
