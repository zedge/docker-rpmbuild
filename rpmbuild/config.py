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

CONFIG_OPTIONS_DOCKER = {
    'version': 'get',
    'timeout': 'getint',
    'base_url': 'get'
}

CONFIG_OPTIONS_RPMBUILD = {
    'define': 'multi-get',
    'source': 'multi-get',
    'sources_dir': 'get',
    'macrofile': 'multi-get',
    'retrieve': 'getboolean',
    'output': 'get',
    'image': 'get'
}

SECTION_CONFIG_MAP = {
    'docker': CONFIG_OPTIONS_DOCKER,
    'rpmbuild': CONFIG_OPTIONS_RPMBUILD
}


def _read_section(section, valid_keys, config):
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

def _read_config(config_file):
    config = configparser.RawConfigParser()
    config.readfp(config_file)
    config_dict = {}

    for section, config_options in SECTION_CONFIG_MAP.items():
        config_dict.update(_read_section(section, config_options, config))

    return defaultdict(None, config_dict)


def _open_and_read_config(path):
    with open(path) as config_filehandle:
        return _read_config(config_filehandle)

def _read_config_if_exists(spec_or_srpm):


    def path_to_config(file):
        base_name = os.path.basename(file)

        # foo.spec  where foo is firstname, spec is lastname
        first_name = base_name[:base_name.rfind('.')]

        config_base_name = "{0}.dockerrpm".format(first_name)
        return os.path.join(os.path.dirname(os.path.realpath(file)), config_base_name)

    full_path_config = path_to_config(spec_or_srpm)
    if os.path.exists(full_path_config):
        return (_open_and_read_config(full_path_config), full_path_config)
    else:
        return (defaultdict(None, {}), None)


def get_parsed_config(args):
    if args['--spec'] is not None:
        return _read_config_if_exists(args['--spec'])
    elif args['--srpm'] is not None:
        return _read_config_if_exists(args['--srpm'])
    else:
        return (defaultdict(None, {}), None)




def get_docker_config(docopt_args, config):
    args_overriden_docker_config = {
        'base_url': docopt_args['--docker-base_url'] or config.get('base_url'),
         'timeout': int(docopt_args['--docker-timeout'] or config.get('timeout') or DEFAULT_TIMEOUT),
         'version': docopt_args['--docker-version'] or config.get('version')}

    # Remove None values and convert to default dict
    return defaultdict(None, dict((k, v) for k, v in args_overriden_docker_config.items() if v))
