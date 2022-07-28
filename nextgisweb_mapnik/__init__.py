# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import logging
import time
from threading import Thread
from PIL import Image
from nextgisweb.component import Component
from nextgisweb.lib.config import Option
from nextgisweb.lib.logging import logger
from nextgisweb.render import on_style_change
from nextgisweb.resource import Resource


from .model import Base, ImageOptions, LegendOptions
from .util import COMP_ID, DEFAULT_IMAGE_FORMAT, _

from six import BytesIO
from six.moves.queue import Queue

has_mapnik = False
try:
    import mapnik

    has_mapnik = True
except ImportError as e:
    logging.error(e)
    try:
        import mapnik2 as mapnik

        has_mapnik = True
    except ImportError as e:
        logging.error(e)

MANPIK_MAPS = dict()
# The dictionary of the loaded maps


@on_style_change.connect
def on_style_change_handler(resource):
    """
    Функция которая срабатывает по изменению стиля

    :param Resource resource: ресурс стиля
    :return:
    """
    if resource.id in MANPIK_MAPS.keys():
        del MANPIK_MAPS[resource.id]


class MapnikComponent(Component):
    identity = COMP_ID
    metadata = Base.metadata

    def initialize(self):
        super(MapnikComponent, self).initialize()

        self.thread_count = self.options['thread_count']
        self.max_zoom = self.options['max_zoom']
        self.render_timeout = self.options['render_timeout']
        self.font_path = self.options['fontpath'] if (has_mapnik and 'fontpath' in self.options) else ''
        if self.font_path:
            mapnik.register_fonts(self.font_path)

        self.workers = dict()
        self.queue = Queue()
        for i in range(self.thread_count):
            worker = Thread(target=self.renderer)
            worker.daemon = True
            worker.start()
            self.workers[i] = worker

    def configure(self):
        super(MapnikComponent, self).configure()

    def setup_pyramid(self, config):
        super(MapnikComponent, self).setup_pyramid(config)

        from . import view, api
        api.setup_pyramid(self, config)
        view.setup_pyramid(self, config)

    def client_settings(self, request):
        return dict(
            thread_count=self.thread_count,
            max_zoom=self.max_zoom,
            render_timeout=self.render_timeout,
            fontpath=self.fontpath
        )

    @staticmethod
    def _create_empty_image():
        return Image.new('RGBA', (256, 256), (0, 0, 0, 0))

    def renderer_job(self, options):
        result_queue = Queue()
        self.queue.put((options, result_queue))

        result = result_queue.get(block=True, timeout=self.render_timeout)

        if isinstance(result, Exception):
            raise result
        return result

    def renderer(self):

        while True:
            options, result = self.queue.get()
            if isinstance(options, LegendOptions):
                logger.error(_('Not supported yet'))
            else:
                style_id, xml_map, render_size, extended, target_box = options
                if not has_mapnik:
                    logger.warning(_('Mapnik don\'t supported'))
                    result.put(self._create_empty_image())
                    continue

                mapnik_map = MANPIK_MAPS.setdefault(style_id, mapnik.Map(0, 0))
                if len([style for style in mapnik_map.styles]) == 0:
                    try:
                        mapnik.load_map_from_string(mapnik_map, xml_map)
                    except Exception as e:
                        logger.error(_('Error of loading mapnik map'))
                        logger.exception(e)
                        mapnik_map = None
                        del MANPIK_MAPS[style_id]
                        result.put(self._create_empty_image())
                        continue

                width, height = render_size
                width, height = int(width), int(height)
                mapnik_map.resize(width, height)

                x1, y1, x2, y2 = extended
                box = mapnik.Box2d(x1, y1, x2, y2)
                mapnik_map.zoom_to_box(box)

                mapnik_image = mapnik.Image(width, height)

                _t = time.time()
                mapnik.render(mapnik_map, mapnik_image)
                _t = time.time() - _t
                logger.info('Time of rendering %0.2f' % _t)
                if _t > self.render_timeout:
                    logger.error(_('Time of rendering bigger that timeout. {:0.2f}'.format(_t)))
                    continue

                # Преобразование изображения из PNG в объект PIL
                data = mapnik_image.tostring(DEFAULT_IMAGE_FORMAT)
                buf = BytesIO()
                buf.write(data)
                buf.seek(0)
                res_img = Image.open(buf)
                result.put(res_img.crop(target_box))

    option_annotations = (
        Option('thread_count', int, default=1, doc='Count of thread for rendering.'),
        Option('max_zoom', int, default=19, doc='Max zoom level for rendering.'),
        Option('render_timeout', float, default=60.0, doc='Mapnik rendering timeout for one request.'),
        Option('fontpath', str, doc='Folder for custom fonts')
    )


def pkginfo():
    return dict(components=dict(
        mapnik='nextgisweb_mapnik'))


def amd_packages():
    return ((
                'ngw-mapnik', 'nextgisweb_mapnik:amd/ngw-mapnik'
            ),)
