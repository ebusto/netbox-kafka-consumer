import setuptools

long_description = \
"""
This library is the companion to [netbox-kafka-producer](https://github.com/ebusto/netbox-kafka-producer), making it easy to consume [NetBox](https://github.com/digitalocean/netbox/) changes from [Kafka](https://kafka.apache.org/).
"""

with open('requirements.txt', 'r') as fh:
	packages = fh.read().splitlines()

setuptools.setup(
    name='netbox-kafka-consumer',
    version='1.0.3',
    author='Eric Busto',
    author_email='ebusto@nvidia.com',
    description='Easily consume NetBox changes from Kafka',
	long_description=long_description,
	long_description_content_type='text/markdown',
    url='https://github.com/ebusto/netbox-kafka-consumer',
    packages=setuptools.find_packages(),
	install_requires=packages,
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ],
)