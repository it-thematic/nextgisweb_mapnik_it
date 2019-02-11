# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import PIL
import tempfile
import StringIO
from threading import Thread, Lock
from Queue import Queue
import logging

has_mapnik = False
try:
    import mapnik
    has_mapnik = True
except ImportError as e:
    logging.error(e.message)
    logging.debug('NOT IMPORT MAPNIK!!!. Try import mapnik2')
    try:
        import mapnik2 as mapnik
        has_mapnik = True
    except ImportError as e:
        logging.error(e.message)
        logging.debug('NOT IMPORT MAPNIK2!!! Mapnik not supported.')
logging.info('Has_mapnik: {}'.format(has_mapnik))

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
            if not has_mapnik:
                result.put(PIL.Image.new('RGBA', (0, 0)))
            else:
                mapnik_map = mapnik.Map(0, 0)
                mapnik.load_map(mapnik_map, xml_map, True)

                width, height = render_size
                mapnik_map.resize(width, height)

                x1, y1, x2, y2 = extended
                box = mapnik.Box2d(x1, y1, x2, y2)
                mapnik_map.zoom_to_box(box)

                mapnik_image = mapnik.Image(render_size, render_size)
                mapnik.render(mapnik_map, mapnik_image)

                filename = tempfile.mktemp()
                mapnik_image.save(filename, b'png256')

                with open(filename, mode='rb') as f:
                    buf = StringIO(f.read())
                    buf.seek(0)
                    res_img = PIL.Image.open(buf)
                    result.put(res_img.crop(target_box))

            self.logger.info('Запрос тайла из Mapnik')


def pkginfo():
    return dict(components=dict(
        mapnik='nextgisweb_mapnik_id'))


def amd_packages():
    return ((
        'ngw-mapnik', 'nextgisweb_mapnik_id:amd/ngw-mapnik'
    ),)
