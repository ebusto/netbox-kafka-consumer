from confluent_kafka        import Consumer, KafkaError
from pynetbox.core.response import Record

import json
import logging
import pynetbox
import uuid
import warnings

from netbox_events import env

# Silence urllib3 SSL warnings.
warnings.simplefilter("ignore")

log = logging.getLogger(__name__)

class Client(object):
	def __init__(self, **kwargs):
		self.classes = dict()

		self.group   = kwargs['group']
		self.servers = kwargs['servers']
		self.token   = kwargs['token']

		self.api = pynetbox.api(self.servers['netbox'], ssl_verify=False, token=self.token)

	def ignore(self, *args):
		pass

	def poll(self, interval=1.0):
		servers = ','.join(self.servers['kafka'])

		consumer = Consumer({
			'bootstrap.servers':  servers,
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
					log.error(message.error())

				continue
		
			# Extract the payload, then unmarshal from JSON.
			data = message.value().decode('utf-8')
			data = json.loads(data)

			# Retrieve the callback function, with a default to ignore.
			fn = self.classes.get(data['class'], self.ignore)

			# Build the pynetbox record from the model.
			record = Record(data['model'], api=self.api, endpoint=None)

			try:
				fn(data, record)
			except Exception as e:
				log.exception(e)
			else:
				consumer.commit(message)
	
		consumer.close()

	def subscribe(self, classes, fn):
		for c in classes:
			self.classes[c] = fn
