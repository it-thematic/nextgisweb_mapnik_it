# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import PIL
from threading import Thread, Lock
from Queue import Queue
has_mapnik = False
try:
    import mapnik
except ImportError:
    try:
        import mapnik2 as mapnik
    except ImportError:
        has_mapnik = False
from nextgisweb.component import Component, require

from .model import Base
from .util import COMP_ID


class MapnikComponent(Component):
    identity = COMP_ID
    metadata = Base.metadata

    def initialize(self):
        super(MapnikComponent, self).initialize()
        if 'mapnikThreadCount' not in self.settings:
            import multiprocessing  # noqa
            self.settings['mapnikThreadCount'] = multiprocessing.cpu_count()

        if 'mapnikTilePath' not in self.settings:
            from tempfile import gettempdir  # noqa
            self.settings['mapnikTilePath'] = gettempdir()

        if 'mapnikMaxZoom' not in self.settings:
            self.settings['mapnikMaxZoom'] = 23
        # Чтобы на раннем этапе отсечь ошибку задания уровня. Отрицательное число тоже нельзя
        try:
            self.settings['mapnikMaxZoom'] = abs(int(self.settings['mapnikMaxZoom']))
        except Exception as e:
            self.logger.error(e.message)
            self.settings['mapnikMaxZoom'] = 23

    def configure(self):
        super(MapnikComponent, self).configure()

    def setup_pyramid(self, config):
        super(MapnikComponent, self).setup_pyramid(config)

        # Отдельный поток в котором мы будем запускать весь рендеринг,
        # иначе все падает в segfault при конкурентной обработке запросов.
        self.queue = Queue()
        self.printLock = Lock()
        self.workers = {}

        for i in range(self.settings['mapnikThreadCount']):
            worker = Thread(target=self.renderer)
            worker.daemon = True
            worker.start()
            self.workers[i] = worker

        if not os.path.isdir(self.settings['mapnikTilePath']):
            os.mkdir(self.settings['mapnikTilePath'])

        from . import view, api
        api.setup_pyramid(self, config)
        view.setup_pyramid(self, config)

    def renderer(self):
        while True:
            options = self.queue.get()
            xml_map, srs, render_size, extended, target_box, result = options
            res_img = PIL.Image.new('RGBA', (0, 0))
            if not has_mapnik:
                result.put(res_img)
            else:
                mapnik_map = mapnik.Map(0, 0)
                mapnik.load_map(mapnik_map, xml_map, True)
                mapnik_map.resize(render_size, render_size)
                mapnik_map.zoom_to_box(extended)
                im = mapnik.Image(render_size, render_size)
                res_img = PIL.Image.open(im)
                result.put(res_img)
            self.logger.info('Запрос тайла из Mapnik')


def pkginfo():
    return dict(components=dict(
        mapnik='nextgisweb_mapnik_id'))


def amd_packages():
    return ((
        'ngw-mapnik', 'nextgisweb_mapnik_id:amd/ngw-mapnik'
    ),)
