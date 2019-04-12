#!/usr/bin/env python3

import os
import pynetbox
import ruamel.yaml
import stat
import sys
import tempfile

sys.path.insert(0, '..')

import netbox_kafka_consumer

class Prometheus(object):
	def __init__(self, config, group, token):
		api = pynetbox.api('https://netbox.nvidia.com', ssl_verify=False, token=token)

		self.config = config

		self.client = netbox_kafka_consumer.Client(
			api     = api,
			group   = group,
			servers = 'sc-it-mq-prd-01,sc-it-mq-prd-02,sc-it-mq-prd-03',
		)

	def event_service_device(self, event, record):
		labels = None

		if event == 'create':
			labels = self.labels_for_device(record.device)

		self.update_jobs(info['event'], record.service, record.device, labels)

	def event_service_vm(self, event, record):
		labels = None

		if event == 'create':
			labels = self.labels_for_vm(record.virtual_machine)

		self.update_jobs(event, record.service, record.virtual_machine, labels)

	def event_service_group(self, event, record):
		print('[{}] {}/{}: {}'.format(event, record.service.name, record.group.name, record.roles))

	def event_service_user(self, event, record):
		print('[{}] {}/{}: {}'.format(event, record.service.name, record.user.name, record.roles))

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

		# Create a temporary file in the same directory.
		tmp = tempfile.mkstemp(dir=os.path.dirname(self.config))[1]

		info = os.stat(self.config)

		# Mirror the source configuration mode and ownership.
		os.chmod(tmp, info.st_mode)
		os.chown(tmp, info.st_uid, info.st_gid)

		# Write the updated configuration.
		with open(tmp, 'w') as fh:
			ruamel.yaml.round_trip_dump(data, fh)

			fh.flush()

		os.rename(tmp, self.config)

	def update_jobs(self, event, service, host, labels):
		print('{}: {}/{} [{}]'.format(event, service, host, labels))

		if labels:
			labels.update({
				'environment': service.environment.label,
				'importance':  service.importance.label,
			})

		exporter_ports = {
			'docker':        ':8080', # cadvisor
			'elasticsearch': ':9108', # prometheus-elasticsearch-exporter
			'kafka':         ':9308', # prometheus-kafka-exporter
		}

		# node_exporter port is 9100.
		target = host.name + ':9100'

		config = {
			'labels':  labels,
			'targets': [target],
		}

		if event == 'create':
			for application in service.applications:
				if application.name in exporter_ports:
					port = exporter_ports[application.name]

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
		# Service and host relationships.
		self.client.subscribe(self.event_service_device, 'ServiceDevice')
		self.client.subscribe(self.event_service_vm,     'ServiceVirtualMachine')

		# Service and contact relationships.
		self.client.subscribe(self.event_service_group, 'ServiceGroup')
		self.client.subscribe(self.event_service_user, 'ServiceUser')

		self.client.poll()

config = '/var/lib/prometheus/prometheus.yml'
group  = 'prometheus-netbox-sync'
token  = '34249d96ba149f0fbbf280fe2454b81a0dc3fca8'

if len(sys.argv) > 1:
	config = sys.argv[1]

Prometheus(config, group, token).run()
