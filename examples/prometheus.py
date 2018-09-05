#!/usr/bin/env python3

import grp
import os
import ruamel.yaml
import stat
import sys
import tempfile

sys.path.insert(0, '..')

import netbox_events

class PrometheusConfig(object):
	def __init__(self, config, group):
		self.config = config
		self.group  = group

		self.client = netbox_events.Client(
			group   = 'prometheus-config-sync',
			servers = netbox_events.SERVERS_DEV,
			token   = '2a699ea0f9195ad345088059c5c6ca748af7563e',
		)

	def event_service_device(self, info, model):
		labels = None

		if info['event'] == 'create':
			labels = self.labels_for_device(model.device)

		self.update_jobs(info['event'], model.service, model.device, labels)

	def event_service_vm(self, info, model):
		labels = None

		if info['event'] == 'create':
			labels = self.labels_for_vm(model.virtual_machine)

		self.update_jobs(info['event'], model.service, model.virtual_machine, labels)

	def event_service_group(self, info, model):
		print('{}: {}/{} [{}]'.format(info['event'], model.service.name, model.group.name, model.roles))

	def event_service_user(self, info, model):
		print('{}: {}/{} [{}]'.format(info['event'], model.service.name, model.user.name, model.roles))

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

		# Write the updated configuration.
		with open(tmp, 'w') as fh:
			ruamel.yaml.round_trip_dump(data, fh)

			fh.flush()

		# Build GID and mode bits.
		gid = grp.getgrnam(group).gr_gid
		mod = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP

		os.chmod(tmp, mod)
		os.chown(tmp, -1, gid)

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
		# Service and host relationships.
		self.client.subscribe([ 'ServiceDevice'         ], self.event_service_device)
		self.client.subscribe([ 'ServiceVirtualMachine' ], self.event_service_vm) 

		# Service and contact relationships.
		self.client.subscribe([ 'ServiceGroup' ], self.event_service_group)
		self.client.subscribe([ 'ServiceUser'  ], self.event_service_user)

		self.client.poll()

config = '/var/lib/prometheus/prometheus.yml'
group  = 'prometheus'

if len(sys.argv) > 1:
	config = sys.argv[1]

PrometheusConfig(config, group).run()
