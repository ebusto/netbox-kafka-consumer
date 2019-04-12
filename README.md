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

# Subscriptions are matched on the class of record. In Django signal terms,
# this is generally the signal sender. As "class" is a reserved keyword,
# "sender" is used instead.

# The first argument to 'subscribe' is the match specification, which can be
# one of the following types:
#
#   boolean  - when true, matches all
#   callable - should return true on match
#   list     - a list membership match
#   string   - a simple string match

# The second argument to 'subscribe' is the callback. The function signature
# is inspected, and the name of each parameter determines the value of each
# argument. The following parameter names are allowed:
#
#   detail   - in the case of an update, the specific changes
#   event    - create, update, or delete
#   message  - the raw message
#   model    - the serialized instance
#   record   - the model as a pynetbox response record
#   request  - username and source address
#   response - responding hostname
#   sender   - the record class / sender

# The 'record' parameter is the pynetbox response record.
def vm_record(record):
    print(record.cluster.site.name)

client.subscribe('VirtualMachine', vm_record)

def all_messages(message):
    print(message)

client.subscribe(True, all_messages)

def user_device(request, event, model, detail):
    if event == 'update':
        print('user {} updated {}: {}'.format(
            request['username'], model.get('name', 'unknown'), detail))

client.subscribe(re.compile('^Device').match, user_device)

client.poll()
```
