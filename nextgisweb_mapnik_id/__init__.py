# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import logging
import time
try:
    import Queue as queue
    from StringIO import StringIO as StringIO
except ImportError:
    import queue as queue
    from io import StringIO as StringIO
from threading import Thread, Lock
from PIL import Image

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

from nextgisweb.component import Component

from .model import Base
from .util import COMP_ID, _


class MapnikComponent(Component):
    identity = COMP_ID
    metadata = Base.metadata

    default_thread_count = 1
    default_max_zoom = 19
    default_render_timeout = 19

    def initialize(self):
        super(MapnikComponent, self).initialize()
        # Количество потоков в которых будут рендериться тайлы/изображения
        if 'thread_count' not in self.settings:
            self.settings['thread_count'] = self.__class__.default_thread_count
        else:
            try:
                self.settings['thread_count'] = int(self.settings['thread_count'])
            except ValueError:
                self.logger.error(_('Invalid value of "%s". The default value is %s.') % (
                self.__class__.default_thread_count.__class__.__name__, self.__class__.default_thread_count))
                self.settings['thread_count'] = self.__class__.default_thread_count

        # максимальный уровень для рендеринга тайлов
        # Чтобы на раннем этапе отсечь ошибку задания уровня. Отрицательное число тоже нельзя
        if 'max_zoom' not in self.settings:
            self.settings['max_zoom'] = self.__class__.default_max_zoom
        else:
            try:
                self.settings['max_zoom'] = abs(int(self.settings['max_zoom']))
            except ValueError:
                self.logger.error(_('Invalid value of "%s". The default value is %s.') % (
                    self.__class__.default_max_zoom.__class__.__name__, self.__class__.default_max_zoom))
                self.settings['max_zoom'] = self.__class__.default_max_zoom

        # максимальное время ожидания рендеринга
        if 'render_timeout' not in self.settings:
            self.settings['render_timeout'] = self.__class__.default_render_timeout
        else:
            try:
                self.settings['render_timeout'] = int(self.settings['render_timeout'])
            except ValueError:
                self.logger.error(_('Invalid value of "%s". The default value is %s.') % (
                    self.__class__.default_render_timeout.__class__.__name__, self.__class__.default_render_timeout))
                self.settings['render_timeout'] = self.__class__.default_render_timeout

        if has_mapnik:
            if 'custom_font_dir' in self.settings:
                mapnik.register_fonts(self.settings['custom_font_dir'].encode('utf-8'))

        # Отдельный поток в котором мы будем запускать весь рендеринг,
        # иначе все падает в segfault при конкурентной обработке запросов.
        self.queue = queue.Queue()
        self.printLock = Lock()
        self.workers = {}

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

    def renderer(self):
        while True:
            options = self.queue.get()
            xml_map, srs, render_size, extended, target_box, result = options
            if not has_mapnik:
                result.put(self._create_empty_image())
                return

            mapnik_map = mapnik.Map(0, 0)
            try:
                mapnik.load_map_from_string(mapnik_map, xml_map, True)
            except Exception as e:
                self.logger.error(_('Error load mapnik map'))
                self.logger.exception(e.message)
                result.put(self._create_empty_image())
                return

            width, height = render_size
            mapnik_map.resize(width, height)

            x1, y1, x2, y2 = extended
            box = mapnik.Box2d(x1, y1, x2, y2)
            mapnik_map.zoom_to_box(box)

            mapnik_image = mapnik.Image(width, height)

            # Вычисляем время рендеринга. Если прошло больше чем `render_timeout`, то не возвращаем результат
            #     т.к. в модели время ожидания из очереди уже истекло
            _t = time.time()
            mapnik.render(mapnik_map, mapnik_image)
            _t = time.time() - _t
            if _t > self.settings['render_timeout']:
                self.logger.error(_('Time of rendering bigger that timeout. {:0.2f}'.format(_t)))
                return

            # Преобразование изображения из PNG в объект PIL
            data = mapnik_image.tostring('png')
            buf = StringIO()
            buf.write(data)
            buf.seek(0)
            res_img = Image.open(buf)
            result.put(res_img.crop(target_box))

    settings_info = (
        dict(key='thread_count', desc=_('Count of thread for rendering.')),
        dict(key='max_zoom', desc='Max zoom level for rendering.'),
        dict(key='render_timeout', desc='Mapnik rendering timeout for one request.'),
        dict(key='fontpath',   desc='Font search folder')
    )


def pkginfo():
    return dict(components=dict(
        mapnik='nextgisweb_mapnik_it'))


def amd_packages():
    return ((
                'ngw-mapnik', 'nextgisweb_mapnik_it:amd/ngw-mapnik'
            ),)
