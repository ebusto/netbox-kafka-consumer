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
			token   = '2a699ea0f9195ad345088059c5c6ca748af7563e',
		)

	def event_service_device(self, event, model):
		labels = None

		if event['event'] == 'create':
			labels = self.labels_for_device(model.device)

		self.update_jobs(event['event'], model.service, model.device, labels)

	def event_service_vm(self, event, model):
		labels = None

		if event['event'] == 'create':
			labels = self.labels_for_vm(model.virtual_machine)

		self.update_jobs(event['event'], model.service, model.virtual_machine, labels)

	def labels_for_device(self, device):
		labels = {
			'manufacturer': device.device_type.manufacturer.name,
			'model':        device.device_type.model,
			'site':         device.site.name,
		}

		if device.platform:
			labels.update({
				'platform': device.platform.name,
			})

		if device.rack:
			labels.update({
				'face':     device.face,
				'position': device.position,
				'rack':     device.rack.name,
			})

		return labels

	def labels_for_vm(self, vm):
		labels = {
			'cluster': vm.cluster.name,
			'site':    vm.cluster.site.name,
		}

		return labels

	def update_config(self, fn):
		# This should acquire a lock first.
		with open(self.config, 'r') as fh:
			data = ruamel.yaml.round_trip_load(fh)
	
		fn(data)
	
		# This should write to a temporary file, then rename.
		with open(self.config, 'w') as fh:
			ruamel.yaml.round_trip_dump(data, fh)

			fh.flush()

	def update_jobs(self, event, service, host, labels):
		print('{}: {}/{} [{}]'.format(event, service, host, labels))

		if labels:
			labels.update({
				'environment': service.environment.label,
				'importance':  service.importance.label,
			})

		# node_exporter port is 9100.
		target = host.name + ':9100'
		config = {'labels': labels, 'targets': [target]}

		exporter_ports = {
			'docker':        ':8080', # cadvisor
			'elasticsearch': ':9108', # prometheus-elasticsearch-exporter
			'kafka':         ':9308', # prometheus-kafka-exporter
		}

		if event == 'create':
			for application in service.applications:
				if application['name'] in exporter_ports:
					port = exporter_ports[application['name']]

					config['targets'].append(host.name + port)
	
		def fn(data):
			job = { 'job_name': service.name, 'static_configs': [] }

			# Existing job for this service?
			for item in data['scrape_configs']:
				if item['job_name'] == service.name:
					job = item
					break

			# Job not found, so create it.
			else:
				data['scrape_configs'].append(job)

			# Existing config for this target?
			for i, static in enumerate(job['static_configs']):
				if target in static['targets']:
					if event == 'create':
						job['static_configs'][i] = config

					if event == 'delete':
						job['static_configs'].pop(i)

					break

			# Config containing target not found.
			else:
				if event == 'create':
					job['static_configs'].append(config)

		return self.update_config(fn)

	def run(self):
		#self.client.subscribe([ 'ServiceApplication'    ], self.event_service_application)
		self.client.subscribe([ 'ServiceDevice'         ], self.event_service_device)
		self.client.subscribe([ 'ServiceVirtualMachine' ], self.event_service_vm) 

		self.client.poll()

config = '/var/lib/prometheus/prometheus.yml'

if len(sys.argv) > 1:
	config = sys.argv[1]

PrometheusConfig(config).run()
