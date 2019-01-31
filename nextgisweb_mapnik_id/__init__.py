# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from threading import Thread
from Queue import Queue
from StringIO import StringIO

from nextgisweb.component import Component, require

from .model import Base
from .util import COMP_ID


class MapnikItComponent(Component):
    identity = COMP_ID
    metadata = Base.metadata

    def initialize(self):
        super(MapnikItComponent, self).initialize()

    def configure(self):
        super(MapnikItComponent, self).configure()


    @require('resource')
    def setup_pyramid(self, config):
        super(MapnikItComponent, self).setup_pyramid(config)

        # Отдельный поток в котором мы будем запускать весь рендеринг,
        # иначе все падает в segfault при конкурентной обработке запросов.
        self.queue = Queue()
        self.worker = Thread(target=self.renderer)
        self.worker.daemon = True
        self.worker.start()

        from . import view, api
        view.setup_pyramid(self, config)
        api.setup_pyramid(self, config)

    def renderer(self):

        while True:
            options = self.queue.get()

4

def pkginfo():
    return dict(components=dict(
        nextgisweb_mapnik_it='nextgisweb_mapnik_id'))


def amd_packages():
    return (
        ('ngw-manpik', 'nextgisweb_mapnik_id:amd/ngw-manpik'),
    )
