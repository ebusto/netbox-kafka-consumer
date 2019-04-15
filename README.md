# Introduction
This library is the companion to [netbox-kafka-producer](https://github.com/ebusto/netbox-kafka-producer), making it easy to consume [NetBox](https://github.com/digitalocean/netbox/) changes from [Kafka](https://kafka.apache.org/).

# Synopsis

```
import netbox_kafka_consumer
import pynetbox

api = pynetbox.api('https://netbox', token='<token>')

client = netbox_kafka_consumer.Client(
    api     = api,
    group   = '<kafka_consumer_group>',
    servers = '<kafka_servers>',
)

@client.match(['Device', 'VirtualMachine'], 'delete')
def system_delete(record, request):
    print('System {} has been deleted by {}.'.format(record.name, request['user']))

client.poll()
```

# Subscriptions
Messages are matched by the class of record and type of event. In Django
signal terms, the class is equivalent to the signal sender. As `class` is a
reserved keyword, `sender` is used instead.

Callbacks are registered with the client, and the callback is called for each
matching message. Either the `subscribe` method can be called directly, or
the `match` decorator may be used.

Filters may be one of the following types:
  * boolean  - when true, matches all
  * callable - should return true on match
  * list     - a list membership match
  * string   - a simple string match

For each matching callback, the function signature is inspected, and the name
of each parameter determines the value of each argument. The following parameter
names are allowed:

  * detail   - in the case of an update, the specific changes
  * event    - create, update, or delete
  * message  - the raw message
  * model    - the serialized instance
  * record   - the model as a pynetbox response record
  * request  - username and source address
  * response - responding hostname
  * sender   - the record class / sender
