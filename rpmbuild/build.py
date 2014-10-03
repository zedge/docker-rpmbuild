#!/usr/bin/env python

"""Docker rpmbuild.

Usage:
    docker-rpmbuild build --spec=<file>
    docker-rpmbuild build [--docker-base_url=<url>]
                          [--docker-timeout=<seconds>]
                          [--docker-version=<version>]
                          [--define=<option>...]
                          (--source=<tarball>...|--sources-dir=<dir>)
                          (--spec=<file> [--macrofile=<file>...] [--retrieve] [--output=<path>])
                          <image>
    docker-rpmbuild rebuild --srpm=<file>
    docker-rpmbuild rebuild [--docker-base_url=<url>]
                            [--docker-timeout=<seconds>]
                            [--docker-version=<version>]
                            (--srpm=<file> [--output=<path>])
                            <image>

Options:
    -h --help            Show this screen.
    --config=<file>      Configuration file
    --define=<option>    Pass a macro to rpmbuild.
    --output=<path>      Output directory for RPMs [default: .].
    --source=<tarball>   Tarball containing package sources.
    --sources-dir=<dir>  Directory containing resources required for spec.
    -r --retrieve        Fetch defined resources in spec file with spectool inside container
    --spec=<file>        RPM Spec file to build.
    --macrofile=<file>   Defines added in a file, will reside together with SPECS/
    --srpm=<file>        SRPM to rebuild.

Docker Options:
    --docker-base_url=<url>     protocol+hostname+port towards docker
                                (example: unix://var/run/docker.sock)
    --docker-timeout=<seconds>  HTTP request timeout in seconds towards docker API. (default: 600)
    --docker-version=<version>  API version the docker client will use towards
                                docker (example: 1.12)
"""

from __future__ import print_function, unicode_literals

import json
import sys

from docopt import docopt, DocoptExit
from rpmbuild import Packager, PackagerContext, PackagerException
from rpmbuild.config import get_docker_config, get_parsed_config


def log(message, file=None):
    if file is not None:
        print(message, file)
    else:
        print(message)


def get_context(args, config):
    context = None
    if args['build'] or config.get('build'):
        context = PackagerContext(
            args['<image>'] or config.get('image'),
            defines=args['--define'] or config.get('define'),
            sources=args['--source'] or config.get('source'),
            sources_dir=args['--sources-dir'] or config.get('sources_dir'),
            spec=args['--spec'] or config.get('spec'),
            macrofiles=args['--macrofile'] or config.get('macrofile'),
            retrieve=args['--retrieve'] or config.get('retrieve'),
        )

    if args['rebuild'] or config.get('rebuild'):
        context = PackagerContext(
            args['<image>'] or config.get('image'),
            srpm=args['--srpm'] or config.get('srpm')
        )
    if context is None:
        raise DocoptExit('Could not create context, missing configuration')
    return context

def main():
    args = docopt(__doc__, version='Docker Packager 0.0.1')
    config = get_parsed_config(args)
    context = get_context(args, config)

    try:
        with Packager(context,  get_docker_config(args, config)) as p:
            for line in p.build_image():
                parsed = json.loads(line.decode('utf-8'))
                if 'stream' not in parsed:
                    log(parsed)
                    if 'error' in parsed:
                        if 'errorDetail' in parsed:
                            raise PackagerException(
                                "{0} : {1}".format(
                                    parsed['error'],
                                    parsed['errorDetail']))
                        raise PackagerException(parsed['error'])
                else:
                    log(parsed['stream'].strip())

            container, logs = p.build_package()

            for line in logs:
                log(line.decode('utf-8').strip())

            for path in p.export_package(args['--output']):
                log('Wrote: %s' % path)

    except PackagerException:
        log('Container build failed!', file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4