#!/usr/bin/env python3

import sys

sys.path.insert(0, '..')

import netbox_events
import ruamel.yaml

class PrometheusConfig(object):
	def __init__(self, config):
		self.config = config

		self.client = netbox_events.Client(
			group   = 'prometheus-config-sync',
			servers = netbox_events.KAFKA_DEV,
		)
		
	def event_service_device(self, event):
		return self.update_scrape_job(
			event['event'],
			event['model']['service']['name'],
			event['model']['device']['name'],
		)
	
	def event_service_vm(self, event):
		return self.update_scrape_job(
			event['event'],
			event['model']['service']['name'],
			event['model']['virtual_machine']['name'],
		)
	
	def update_config(self, fn):
		with open(self.config, 'r') as fh:
			data = ruamel.yaml.round_trip_load(fh)
	
		fn(data)
	
		with open(self.config, 'w') as fh:
			ruamel.yaml.round_trip_dump(data, fh)
	
	def update_scrape_job(self, operation, service, hostname):
		hostname = hostname + ':9090'
	
		def fn(data):
			for job in data['scrape_configs']:
				if job['job_name'] == service:
					print('Found existing job: %s' % service)

					targets = set()

					if job['static_configs']['targets']:
						targets.update(set(job['static_configs']['targets']))
	
					if operation == 'create':
						targets.add(hostname)

					if operation == 'delete':
						targets.discard(hostname)

					job['static_configs']['targets'] = list(targets)
					job['static_configs']['targets'].sort()

					return
			
			print('New job: %s' % service)
	
			job = {
				'job_name': service,
				'static_configs': {
					'targets': [hostname],
				},
			}
	
			data['scrape_configs'].append(job)
	
		return self.update_config(fn)

	def run(self):
		self.client.subscribe([ 'ServiceDevice'         ], self.event_service_device)
		self.client.subscribe([ 'ServiceVirtualMachine' ], self.event_service_vm) 

		self.client.poll()

if len(sys.argv) < 2:
	print('Usage: %s <config.yml>' % sys.argv[0])
	sys.exit(1)

PrometheusConfig(sys.argv[1]).run()
