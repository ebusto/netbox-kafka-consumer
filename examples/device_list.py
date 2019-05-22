#!/usr/bin/env python3

import netbox_kafka_consumer
import pynetbox

nb = pynetbox.api('https://netbox', ssl_verify=False, token='<token>')

cn = netbox_kafka_consumer.Client(
	api     = nb,
	group   = 'netbox-device-list-demo',
	servers = [
		'sc-it-mq-prd-01',
		'sc-it-mq-prd-02',
		'sc-it-mq-prd-03',
	]
)

devices = nb.dcim.devices.filter(role='pdu')
devices = {device.name:device for device in devices}

@cn.match('Device', ['create', 'delete'])
def device_event(event, record):
	if record.role.slug != 'pdu':
		return

	if event == 'create':
		devices[record.name] = record

	if event == 'delete':
		del devices[record.name]

cn.poll()
