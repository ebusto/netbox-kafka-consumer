# Introduction
This library is the companion to [netbox-kafka-producer](https://github.com/ebusto/netbox-kafka-producer), making it easy to consume [NetBox](https://github.com/digitalocean/netbox/) changes from [Kafka](https://kafka.apache.org/).

# Installation
`pip install netbox-kafka-consumer`

# Synopsis

```
import netbox_kafka_consumer
import pynetbox

api = pynetbox.api('https://netbox', token='<token>')

bus = netbox_kafka_consumer.Client(
    api     = api,
    group   = '<kafka_consumer_group>',
    servers = '<kafka_servers>',
)

@bus.match(['Device', 'VirtualMachine'], 'delete')
def system_delete(record, request):
    print('System {} has been deleted by {}.'.format(record.name, request['user']))

bus.poll()
```

# Subscriptions
Messages are matched by the class of record and type of event. In Django
signal terms, the class is equivalent to the signal sender. As `class` is a
reserved keyword, `sender` is used instead.

Callbacks are registered with the client, and the callback is called for each
matching message. Either the `subscribe` method can be called directly, or
the `match` decorator may be used.

Filters may be one of the following types.

| Type       | Description                      |
| ----       | -----------                      |
| `bool`     | When `True`, matches everything. |
| `callable` | Must return `True` on match.     |
| `list`     | List membership.                 |
| `str`      | String comparison.               |

For each matching callback, the function signature is inspected, and the name
of each parameter determines the value of each argument. The following parameter
names are supported.

| Name       | Description                                          |
| ----       | -----------                                          |
| `detail`   | On `update`, the specific changes, otherwise `None`. |
| `event`    | One of: `create`, `update`, or `delete`.             |
| `message`  | Entire message.                                      |
| `model`    | Most recent instance of the object.                  |
| `record`   | Model as a `pynetbox` response record.               |
| `request`  | Username and source address.                         |
| `response` | Responding hostname.                                 |
| `sender`   | Record class.                                        |
