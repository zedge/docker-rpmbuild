#!/usr/bin/env python

import os
import re
import ntpath
import shutil
import tempfile

from jinja2 import Template
import docker

INVALID_DOCKER_TAGNAME = '[^a-z0-9_.]'

def path_leaf(path):
    if path is None:
        return None
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)

def replace_invalid_chars(value):
    if value is None:
        return None
    return re.sub(INVALID_DOCKER_TAGNAME, '_', value)


class PackagerContext(object):

    def __init__(self, image, defines=None, sources=None, sources_dir=None,
                 spec=None, macrofiles=None, retrieve=None, srpm=None):
        self.image = image
        self.defines = defines
        self.sources = sources
        self.macrofiles = macrofiles
        self.spec = spec
        self.srpm = srpm
        self.retrieve = retrieve

        if not defines:
            self.defines = []

        if not sources:
            self.sources = []

        if not macrofiles:
            self.macrofiles = []

        if sources_dir and os.path.exists(sources_dir):
            self.sources_dir = sources_dir
        else:
            self.sources_dir = None

        if image is None:
            raise PackagerException("Must provide base docker <image>")
        if spec is None and srpm is None:
            raise PackagerException("Must provide <spec> or <srpm>. See -h")

        # We do this so it's always easy to referrer to the generated Dockerfile in sphinx.
        self.template = Template(self._dockerfile())

    def __str__(self):
        return replace_invalid_chars(path_leaf(self.spec)) or replace_invalid_chars(path_leaf(self.srpm))

    def _dockerfile(self):
        """Hacking up the unintentional tarball unpack
        https://github.com/dotcloud/docker/issues/3050"""
        return """
            FROM {{ image }}

            RUN yum -y install rpmdevtools yum-utils tar
            RUN rpmdev-setuptree
            
            RUN sed -i 's/%_topdir.*/%_topdir \/rpmbuild\/build/g' $HOME/.rpmmacros

            {% if sources_dir is not none %}
            ADD SOURCES /rpmbuild/build/SOURCES
            {% endif %}
            {% for source in sources %}
            ADD {{ source }} /rpmbuild/build/SOURCES/{{ source }}
            RUN cd /rpmbuild/build/SOURCES; if [ -d {{ source }} ]; then mv {{ source }} {{ source }}.tmp; tar -C {{ source }}.tmp -czvf {{ source }} .; rm -r {{ source }}.tmp; fi
            RUN chown -R root:root /rpmbuild/build/SOURCES
            {% endfor %}

            {% if spec %}
            {% for macrofile in macrofiles %}
            ADD {{ macrofile }} /rpmbuild/build/SPECS/{{ macrofile }}
            {% endfor %}
            ADD {{ spec }} /rpmbuild/build/SPECS/{{ spec }}
            RUN chown -R root:root /rpmbuild/build/SPECS
            {% if retrieve %}
            RUN spectool -g -R -A /rpmbuild/build/SPECS/{{ spec }}
            {% endif %}
            RUN yum-builddep -y /rpmbuild/build/SPECS/{{ spec }}
            CMD rpmbuild {% for define in defines %} --define '{{ define }}' {% endfor %} -ba /rpmbuild/build/SPECS/{{ spec }}
            {% endif %}

            {% if srpm %}
            ADD {{ srpm }} /rpmbuild/build/SRPMS/{{ srpm }}
            RUN chown -R root:root /rpmbuild/build/SRPMS
            CMD rpmbuild --rebuild /rpmbuild/build/SRPMS/{{ srpm }}
            {% endif %}

            """

    def setup(self):
        """
        Setup context for docker container build.  Copies the source tarball
        and SPEC file to the context directory.  Writes a Dockerfile from the
        template above.
        """
        self.path = tempfile.mkdtemp()
        self.dockerfile = os.path.join(self.path, 'Dockerfile')

        for source in self.sources:
            shutil.copy(source, self.path)

        for macrofile in self.macrofiles:
            shutil.copy(macrofile, self.path)

        if self.spec:
            shutil.copy(self.spec, self.path)

        if self.srpm:
            shutil.copy(self.srpm, self.path)

        if self.sources_dir:
            shutil.copytree(self.sources_dir,
                            os.path.join(self.path, 'SOURCES'))

        with open(self.dockerfile, 'w') as f:
            content = self.template.render(
                image=self.image,
                defines=self.defines,
                sources=[os.path.basename(s) for s in self.sources],
                sources_dir=self.sources_dir,
                spec=self.spec and os.path.basename(self.spec),
                macrofiles=[os.path.basename(s) for s in self.macrofiles],
                retrieve=self.retrieve,
                srpm=self.srpm and os.path.basename(self.srpm),
            )
            f.write(content)

    def teardown(self):
        shutil.rmtree(self.path)


class PackagerException(Exception):
    pass


class Packager(object):

    def __init__(self, context, docker_config):
        self.context = context
        self.client = docker.Client(**dict(docker_config))

    def __enter__(self):
        self.context.setup()
        return self

    def __exit__(self, type, value, traceback):
        self.context.teardown()

    def __str__(self):
        return self.context.image

    def export_package(self, output):
        """
        Finds RPMs build in the container and copies to host output directory.
        """
        exported = []

        for diff in self.client.diff(self.container):
            if diff['Path'].startswith('/rpmbuild'):
                if diff['Path'].endswith('.rpm'):
                    directory, name = os.path.split(diff['Path'])
                    res = self.client.copy(self.container['Id'], diff['Path'])
                    with open(os.path.join(output, name), 'wb') as f:
                        f.write(res.read()[512:])
                        exported.append(f.name)

        return exported

    @property
    def image_name(self):
        return 'rpmbuild_%s' % self.context

    @property
    def image(self):
        images = self.client.images(name=self.image_name)

        if not images:
            raise PackagerException

        return images[0]

    def build_image(self):
        return self.client.build(
            self.context.path,
            tag=self.image_name,
            stream=True
        )

    def build_package(self):
        """
        Build the RPM package on top of the provided image.
        """
        self.container = self.client.create_container(self.image['Id'])
        self.client.start(self.container)
        return self.container, self.client.logs(self.container, stream=True)


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
