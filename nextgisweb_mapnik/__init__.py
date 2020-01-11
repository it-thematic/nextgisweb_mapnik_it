# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
import time
from threading import Thread
from PIL import Image
from nextgisweb.component import Component

from .model import Base, ImageOptions, LegendOptions
from .util import COMP_ID, DEFAULT_IMAGE_FORMAT, _

try:
    import Queue as queue
    from StringIO import StringIO as StringIO
except ImportError:
    import queue as queue
    from io import StringIO as StringIO

has_mapnik = False
try:
    import mapnik

    has_mapnik = True
except ImportError as e:
    logging.error(e.message)
    try:
        import mapnik2 as mapnik

        has_mapnik = True
    except ImportError as e:
        logging.error(e.message)


class MapnikComponent(Component):
    identity = COMP_ID
    metadata = Base.metadata

    default_thread_count = 1
    default_max_zoom = 19
    default_render_timeout = 60.0

    def initialize(self):
        super(MapnikComponent, self).initialize()

        if 'thread_count' not in self.settings:
            self.settings['thread_count'] = self.__class__.default_thread_count
        else:
            try:
                self.settings['thread_count'] = int(self.settings['thread_count'])
            except ValueError:
                self.logger.error(_('Invalid value of "%s". The default value is %s.') % (
                    self.__class__.default_thread_count.__class__.__name__, self.__class__.default_thread_count))
                self.settings['thread_count'] = self.__class__.default_thread_count

        if 'max_zoom' not in self.settings:
            self.settings['max_zoom'] = self.__class__.default_max_zoom
        else:
            try:
                self.settings['max_zoom'] = abs(int(self.settings['max_zoom']))
            except ValueError:
                self.logger.error(_('Invalid value of "%s". The default value is %s.') % (
                    self.__class__.default_max_zoom.__class__.__name__, self.__class__.default_max_zoom))
                self.settings['max_zoom'] = self.__class__.default_max_zoom

        try:
            self._render_timeout = float(self.settings.get('render_timeout', self.__class__.default_render_timeout))
        except ValueError:
            self.logger.error(_('Invalid value of "%s". The default value is %s.') % (
                self.__class__.default_render_timeout.__class__.__name__, self.__class__.default_render_timeout))
            self._render_timeout = self.__class__.default_render_timeout

        if has_mapnik:
            mapnik.register_fonts(self.settings['fontpath'].encode('utf-8') if 'fontpath' in self.settings else None)

        self.workers = {}
        self.queue = queue.Queue()
        for i in range(self.settings['thread_count']):
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

    @staticmethod
    def _create_empty_image():
        return Image.new('RGBA', (256, 256), (0, 0, 0, 0))

    def renderer_job(self, options):
        result_queue = queue.Queue()
        self.queue.put((options, result_queue))

        result = result_queue.get(block=True, timeout=self._render_timeout)

        if isinstance(result, Exception):
            raise result
        return result

    def renderer(self):

        maps = dict()
        while True:
            options, result = self.queue.get()
            if isinstance(options, LegendOptions):
                self.logger.error(_('Not supported yet'))
            else:
                style_id, xml_map, render_size, extended, target_box = options
                if not has_mapnik:
                    self.logger.warning(_('Mapnik don\'t supported'))
                    result.put(self._create_empty_image())
                    return

                mapnik_map = maps.setdefault(style_id, mapnik.Map(0,0))
                if len([style for style in mapnik_map.styles]) == 0:
                    try:
                        mapnik.load_map_from_string(mapnik_map, xml_map)
                    except Exception as e:
                        self.logger.error(_('Error load mapnik map'))
                        self.logger.exception(e.message)
                        result.put(self._create_empty_image())
                        mapnik_map = None
                        del maps[style_id]
                        continue

                width, height = render_size
                mapnik_map.resize(width, height)

                x1, y1, x2, y2 = extended
                box = mapnik.Box2d(x1, y1, x2, y2)
                mapnik_map.zoom_to_box(box)

                mapnik_image = mapnik.Image(width, height)

                _t = time.time()
                mapnik.render(mapnik_map, mapnik_image)
                _t = time.time() - _t
                self.logger.info('Time of rendering %0.2f' % _t)
                if _t > self._render_timeout:
                    self.logger.error(_('Time of rendering bigger that timeout. {:0.2f}'.format(_t)))
                    return

                # Преобразование изображения из PNG в объект PIL
                data = mapnik_image.tostring(DEFAULT_IMAGE_FORMAT)
                buf = StringIO()
                buf.write(data)
                buf.seek(0)
                res_img = Image.open(buf)
                result.put(res_img.crop(target_box))

    settings_info = (
        dict(key='thread_count', desc=_('Count of thread for rendering.')),
        dict(key='max_zoom', desc='Max zoom level for rendering.'),
        dict(key='render_timeout', desc='Mapnik rendering timeout for one request.'),
        dict(key='fontpath', desc='Font search folder')
    )


def pkginfo():
    return dict(components=dict(
        mapnik='nextgisweb_mapnik'))


def amd_packages():
    return ((
                'ngw-mapnik', 'nextgisweb_mapnik:amd/ngw-mapnik'
            ),)
