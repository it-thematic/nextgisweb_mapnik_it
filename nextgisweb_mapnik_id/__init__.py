# -*- coding: utf-8 -*-
import logging
import time
from Queue import Queue
from StringIO import StringIO
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
from .util import COMP_ID


class MapnikComponent(Component):
    identity = COMP_ID
    metadata = Base.metadata

    def initialize(self):
        super(MapnikComponent, self).initialize()
        # Количество потоков в которых будут рендериться тайлы/изображения
        if 'thread_count' not in self.settings:
            import multiprocessing  # noqa
            self.settings['thread_count'] = multiprocessing.cpu_count()
        else:
            try:
                self.settings['thread_count'] = int(self.settings['thread_count'])
            except ValueError:
                import multiprocessing  # noqa
                self.logger.error('Неверный формат `thread_count`. Значение по умолчанию установлено в cpu_count().')
                self.settings['thread_count'] = multiprocessing.cpu_count()

        # максимальный уровень для рендеринга тайлов
        if 'max_zoom' not in self.settings:
            self.settings['max_zoom'] = 23
        # Чтобы на раннем этапе отсечь ошибку задания уровня. Отрицательное число тоже нельзя
        try:
            self.settings['max_zoom'] = abs(int(self.settings['max_zoom']))
        except ValueError:
            self.logger.error('Неверный формат `max_zoom`. Значение по умолчанию установлено в 23.')
            self.settings['max_zoom'] = 23

        # максимальное время ожидания рендеринга
        if 'render_timeout' not in self.settings:
            self.settings['render_timeout'] = 30
        else:
            try:
                self.settings['render_timeout'] = int(self.settings['render_timeout'])
            except ValueError:
                self.logger.error('Неверный формат `render_timeout`. Значение по умолчанию установлено в 30 с.')
                self.settings['render_timeout'] = 30

        if has_mapnik:
            if 'custom_font_dir' in self.settings:
                mapnik.register_fonts(self.settings['custom_font_dir'].encode('utf-8'))

    def configure(self):
        super(MapnikComponent, self).configure()

    def setup_pyramid(self, config):
        super(MapnikComponent, self).setup_pyramid(config)

        # Отдельный поток в котором мы будем запускать весь рендеринг,
        # иначе все падает в segfault при конкурентной обработке запросов.
        self.queue = Queue()
        self.printLock = Lock()
        self.workers = {}

        for i in range(self.settings['thread_count']):
            worker = Thread(target=self.renderer)
            worker.daemon = True
            worker.start()
            self.workers[i] = worker

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
                mapnik.load_map(mapnik_map, xml_map, True)
            except Exception as e:
                self.logger.error('Ошибка загрузки mapnik-карты')
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
                self.logger.error('Время рендеринга больше, чем время ожидания ответа. {:0.2f}'.format(_t))
                return

            # Преобразование изображения из PNG в объект PIL
            data = mapnik_image.tostring('png')
            buf = StringIO()
            buf.write(data)
            buf.seek(0)
            res_img = Image.open(buf)
            result.put(res_img.crop(target_box))

    settings_info = (
        dict(key='thread_count', desc=u'Количество потоков для рендеринга. По умолчанию: multiprocessing.cpu_count()'),
        dict(key='max_zoom', desc=u'Максимальный уровень для запроса тайлов. По умолчанию: 23'),
        dict(key='render_timeout', desc=u'Таймаут отрисовки одного запроса mapnik\'ом в cек. По умолчанию 30'),
        dict(key='custom_font_dir', desc=u'Директория для хранения пользовательских шрифтов. По умолчанию: /usr/share/fonts')
    )


def pkginfo():
    return dict(components=dict(
        mapnik='nextgisweb_mapnik_id'))


def amd_packages():
    return ((
        'ngw-mapnik', 'nextgisweb_mapnik_id:amd/ngw-mapnik'
    ),)
