#!/usr/bin/env python3

import netbox_kafka_consumer
import pynetbox

nb = pynetbox.api('https://netbox.nvidia.com', token='<token>')

cn = netbox_kafka_consumer.Client(
	api     = nb,
	group   = 'netbox-device-list-demo',
	servers = 'netbox-kafka-prd',
)

devices = nb.dcim.devices.filter(role='pdu')
devices = {device.name:device for device in devices}

@cn.match('Device', ['create', 'update', 'delete'])
def device_event(event, record, detail):
	if record.device_role.slug != 'pdu':
		return

	# Device created or updated: store the latest record.
	if event == 'create' or event == 'update':
		devices[record.name] = record
	
	# Device renamed: remove the old record.
	if event == 'update' and 'model.name' in detail:
		del devices[detail['model.name']]

	# Device deleted: remove the record.
	if event == 'delete':
		del devices[record.name]

cn.poll()
