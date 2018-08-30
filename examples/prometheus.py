#!/usr/bin/env python

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
			token   = '2a699ea0f9195ad345088059c5c6ca748af7563e',
		)
		
	def event_service_device(self, event, model):
		return self.update_job(event['event'], model.service, model.device)
	
	def event_service_vm(self, event, model):
		return self.update_job(event['event'], model.service, model.virtual_machine)
	
	def update_config(self, fn):
		# This should acquire a lock first.
		with open(self.config, 'r') as fh:
			data = ruamel.yaml.round_trip_load(fh)
	
		fn(data)
	
		# This should write to a temporary file, then rename.
		with open(self.config, 'w') as fh:
			ruamel.yaml.round_trip_dump(data, fh)

			fh.flush()

	def update_job(self, operation, service, host):
		print('update_job: operation = {}, service = {}, host = {}'.format(
			operation, service, host
		))

		# node_exporter port is 9100.
		hostname = host.name + ':9100'
	
		def fn(data):
			job = {
				'job_name': service.name,
				'static_configs': [
					{ 'labels':  {} },
					{ 'targets': [] },
			]}

			for j in data['scrape_configs']:
				if j['job_name'] == service.name:
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

config = '/var/lib/prometheus/prometheus.yml'

if len(sys.argv) > 1:
	config = sys.argv[1]

PrometheusConfig(config).run()
