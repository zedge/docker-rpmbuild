#!/usr/bin/env python

import os.path
import shutil
import tempfile

from jinja2 import Template
import docker

client = docker.Client()


class PackagerContext(object):
    template = Template("""
    FROM {{ image }}

    RUN yum -y install rpmdevtools yum-utils
    RUN rpmdev-setuptree

    {% for source in sources %}
    ADD {{ source }} /rpmbuild/SOURCES/{{ source }}
    {% endfor %}
    ADD {{ spec }} /rpmbuild/SPECS/{{ spec }}
    RUN chown -R root:root /rpmbuild
    RUN yum-builddep -y /rpmbuild/SPECS/{{ spec }}
    """)

    def __init__(self, image, sources, spec):
        self.image = image
        self.sources = sources
        self.spec = spec

    def __str__(self):
        return self.path

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

        shutil.copy(self.spec, self.path)
        with open(self.dockerfile, 'w') as f:
            content = self.template.render(
                image=self.image,
                sources=self.sources,
                spec=self.spec
            )
            f.write(content)

    def teardown(self):
        shutil.rmtree(self.path)


class PackagerException(Exception):
    pass


class Packager(object):

    def __init__(self, context):
        self.context = context

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
        for diff in client.diff(self.container):
            if diff['Path'].startswith('/rpmbuild'):
                if diff['Path'].endswith('.rpm'):
                    directory, name = os.path.split(diff['Path'])
                    res = client.copy(self.container['Id'], diff['Path'])
                    with open(os.path.join(output, name), 'w') as f:
                        f.write(res.read()[512:])

    def build_image(self):
        logs = client.build(
            self.context.path,
            tag=self.image_name,
            stream=True
        )

        images = client.images(name=self.image_name)

        if not images:
            raise PackagerException

        image = images[0]

        return (image, logs)

    @property
    def image_name(self):
        return 'rpmbuild-%s' % self.context.spec

    def build_package(self, image):
        """
        Build the RPM package on top of the provided image.
        """
        specfile = os.path.join('/rpmbuild/SPECS', self.context.spec)
        rpmbuild = 'rpmbuild -ba %s' % specfile
        self.container = client.create_container(image['Id'], rpmbuild)

        client.start(self.container)
        return self.container, client.logs(self.container, stream=True)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
