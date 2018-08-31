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
		labels = {
			'manufacturer': model.device.device_type.manufacturer.name,
			'model':        model.device.device_type.model,
			'platform':     model.device.platform.name,
			'site':         model.device.site.name,
		}

		if model.device.rack:
			labels.update({
				'position': model.device.position,
				'rack':     model.device.rack.name,
			})

		return self.update_job(event['event'], model.service, model.device, labels)
	
	def event_service_vm(self, event, model):
		labels = {
			'cluster': model.virtual_machine.cluster.name,
			'site':    model.virtual_machine.cluster.site.name,
		}

		return self.update_job(event['event'], model.service, model.virtual_machine, labels)
	
	def update_config(self, fn):
		# This should acquire a lock first.
		with open(self.config, 'r') as fh:
			data = ruamel.yaml.round_trip_load(fh)
	
		fn(data)
	
		# This should write to a temporary file, then rename.
		with open(self.config, 'w') as fh:
			ruamel.yaml.round_trip_dump(data, fh)

			fh.flush()

	def update_job(self, operation, service, host, labels):
		print('update_job: operation = {}, service = {}, host = {}'.format(
			operation, service, host
		))

		# node_exporter port is 9100.
		hostname = host.name + ':9100'
	
		def fn(data):
			job = { 'job_name': service.name, 'static_configs': [] }

			# Existing job for this service?
			for item in data['scrape_configs']:
				if item['job_name'] == service.name:
					job = item
					break
			else:
				data['scrape_configs'].append(job)

			# Existing config for this target?
			for i, static in enumerate(job['static_configs']):
				if hostname in static['targets']:
					del job['static_configs'][i]

			if operation == 'create':
				job['static_configs'].append({
					'labels':  labels,
					'targets': [hostname],
				})

		return self.update_config(fn)

	def run(self):
		self.client.subscribe([ 'ServiceDevice'         ], self.event_service_device)
		self.client.subscribe([ 'ServiceVirtualMachine' ], self.event_service_vm) 

		self.client.poll()

config = '/var/lib/prometheus/prometheus.yml'

if len(sys.argv) > 1:
	config = sys.argv[1]

PrometheusConfig(config).run()
