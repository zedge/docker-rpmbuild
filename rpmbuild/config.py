from __future__ import unicode_literals

# Python 2/3 Compatibility
try:
    import ConfigParser as configparser
    from StringIO import StringIO
except ImportError:
    import configparser
    from io import StringIO

from collections import defaultdict
import os


DEFAULT_TIMEOUT = '600'


def read_section(section, valid_keys, config):
    """Extract and create a dict with config values

    :param section: section to retrieve.
    :param valid_keys: dictionary containing valid keys, where key is key in config and value represents data type
    :param config: config
    :return dict

    :type section: unicode
    :type valid_keys: dict
    """
    config_dict = {}
    if config.has_section(section):
        for key, data_type in valid_keys.items():
            if config.has_option(section, key):
                if data_type == 'getint':
                    config_dict.update({key: config.getint(section, key)})
                elif data_type == 'getboolean':
                    config_dict.update({key: config.getboolean(section, key)})
                elif data_type == 'multi-get':
                    config_dict.update({key: config.get(section, key).split('\n')})
                else:
                    config_dict.update({key: config.get(section, key)})
        # Remove None values.
        config_dict = dict((k, v) for k, v in config_dict.items() if v)
    return config_dict

def read_config(config_file):
    config = configparser.RawConfigParser()
    config.readfp(config_file)

    config_dict = read_section('docker', {
        'version': 'get',
        'timeout': 'getint',
        'base_url': 'get'
    }, config)
    config_dict.update(read_section('build', {
        'define': 'multi-get',
        'source': 'multi-get',
        'sources_dir': 'get',
        'spec': 'get',
        'macrofile': 'multi-get',
        'retrieve': 'getboolean',
        'output': 'get',
        'image': 'get'
    }, config))

    return defaultdict(None, config_dict)


def get_docker_config(docopt_args):
    docker_config = defaultdict(None)
    docker_config_overrides = defaultdict(None)
    docker_config_overrides.update(
        {'base_url': docopt_args['--docker-base_url'],
         'timeout': int(docopt_args['--docker-timeout'] or DEFAULT_TIMEOUT),
         'version': docopt_args['--docker-version']})

    if docopt_args['--config'] is not None and os.path.exists(docopt_args['--config']):
        docker_config = read_config(docopt_args['--config'])

    if docker_config.get('timeout') is None and docker_config_overrides.get('timeout') is None:
        # Since we want to allow --docker-timeout to override config values:
        # we cannot use the default property for docopt to automatically populate
        # docopt_args['--docker-timeout'], hence we insert default value here as
        # mentioned in __doc__ with normal text not being picked up by docopt.
        docker_config_overrides.update({'timeout': int(DEFAULT_TIMEOUT)})

    # Remove None values.
    docker_config_overrides = dict((k, v) for k, v in docker_config_overrides.items() if v)

    # Update docker config with overrides.
    docker_config.update(docker_config_overrides)
    return docker_config
