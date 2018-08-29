#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, '..')

import netbox_events
import ruamel.yaml

class PrometheusConfig(object):
	def __init__(self, config):
		self.config = config

		self.client = netbox_events.Client(
			group   = 'prometheus-config-sync',
			servers = netbox_events.SERVERS_DEV,
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
		# This should acquire a lock first.
		with open(self.config, 'r') as fh:
			data = ruamel.yaml.round_trip_load(fh)
	
		fn(data)
	
		# This should write to a temporary file, then rename.
		with open(self.config, 'w') as fh:
			ruamel.yaml.round_trip_dump(data, fh)

			fh.flush()

		# Ugly, but functional.
		os.system('pkill -HUP prometheus')
	
	def update_scrape_job(self, operation, service, hostname):
		hostname = hostname + ':9090'
	
		def fn(data):
			job = {
				'job_name': service,
				'static_configs': [{ 'targets': [] }],  
			}

			for j in data['scrape_configs']:
				if j['job_name'] == service:
					job = j

					break
			else:
				data['scrape_configs'].append(job)

			targets = set(job['static_configs'][0]['targets'])

			if operation == 'create':
				targets.add(hostname)

			if operation == 'delete':
				targets.discard(hostname)

			targets = list(targets)
			targets.sort()

			job['static_configs'][0]['targets'] = targets

		return self.update_config(fn)

	def run(self):
		self.client.subscribe([ 'ServiceDevice'         ], self.event_service_device)
		self.client.subscribe([ 'ServiceVirtualMachine' ], self.event_service_vm) 

		self.client.poll()

if len(sys.argv) < 2:
	print('Usage: %s <config.yml>' % sys.argv[0])
	sys.exit(1)

PrometheusConfig(sys.argv[1]).run()
