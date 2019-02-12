# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from collections import namedtuple
from Queue import Empty, Queue
from shutil import copyfileobj
try:
    import mapnik
except ImportError:
    import mapnik2 as mapnik

from zope.interface import implements

from nextgisweb import db
from nextgisweb.env import env
from nextgisweb.feature_layer import IFeatureLayer
from nextgisweb.file_storage import FileObj
from nextgisweb.models import declarative_base
from nextgisweb.resource import (
    Resource,
    ResourceScope,
    DataScope,
    Serializer,
    SerializedProperty)
from nextgisweb.render import (
    IRenderableStyle,
    IExtentRenderRequest,
    ITileRenderRequest,
    ILegendableStyle)
from nextgisweb.spatial_ref_sys import SRS
from .util import _

Base = declarative_base()

ImageOptions = namedtuple('ImageOptions', ['fndata', 'srs', 'render_size', 'extended', 'target_box', 'result'])
LegendOptions = namedtuple('LegendOptions', ['xml', 'geometry_type', 'layer_name', 'result'])


class MapnikVectorStyle(Base, Resource):
    identity = 'mapnik_vector_style'
    cls_display_name = _("Mapnik style")

    implements(IRenderableStyle, ILegendableStyle)

    __scope__ = DataScope

    xml_fileobj_id = db.Column(db.ForeignKey(FileObj.id), nullable=True)
    xml_fileobj = db.relationship(FileObj, cascade='all')

    @classmethod
    def check_parent(cls, parent):
        return IFeatureLayer.providedBy(parent)

    @property
    def feature_layer(self):
        return self.parent

    @property
    def srs(self):
        return self.parent.srs

    def render_request(self, srs, cond=None):
        return RenderRequest(self, srs, cond)

    def _render_image(self, srs, extent, size, cond, padding=0):
        """
        Рендеринг отдельного изображения(картинки, тайла)

        :param SRS srs: модель системы координат
        :param tuple[float] extent: ограничивающий прямоугольник в единицах измерения проекции (метры псевдомеркатора)
        :param tuple[integer] size: размер изображения (256 * 256)
        :param dict cond: дополнительное уловие отбора из модели
        :param float padding: отступ от картинки
        :return:
        """
        # Разрешение. Сколько в одном пикселе единиц сетки
        res_x = (extent[2] - extent[0]) / size[0]
        res_y = (extent[3] - extent[1]) / size[1]

        # Экстент с учетом отступов ( в единицах измерения карты)
        extended = (
            extent[0] - res_x * padding,
            extent[1] - res_y * padding,
            extent[2] + res_x * padding,
            extent[3] + res_y * padding,
        )

        # Размер изображения с учетом отступов
        render_size = (
            size[0] + 2 * padding,
            size[1] + 2 * padding
        )

        # Фрагмент изображения размера size
        target_box = (
            padding,
            padding,
            size[0] + padding,
            size[1] + padding
        )

        res_img = None
        try:
            result = Queue()
            options = ImageOptions(
                env.file_storage.filename(self.xml_fileobj), self.srs, render_size, extended, target_box, result
            )
            env.mapnik.queue.put(options)
            render_timeout = env.mapnik.settings['render_timeout']
            try:
                res_img = result.get(block=True, timeout=render_timeout)
            except Empty:
                pass
        finally:
            pass
        return res_img

    def render_legend(self):
        result = Queue()
        options = LegendOptions(env.file_storage.filename(self.xml_fileobj),
                                self.parent.geometry_type,
                                self.parent.display_name, result)
        env.mapnik.queue.put(options)
        return result.get()


class RenderRequest(object):
    implements(IExtentRenderRequest, ITileRenderRequest)

    def __init__(self, style, srs, cond=None):
        self.style = style
        self.srs = srs
        self.cond = cond

    def render_extent(self, extent, size):
        return self.style._render_image(self.srs, extent, size, self.cond)

    def render_tile(self, tile, size):
        extent = self.srs.tile_extent(tile)
        return self.style._render_image(self.srs, extent, (size, size), self.cond, padding=size / 2)


class _file_upload_attr(SerializedProperty):  # NOQA

    def setter(self, srlzr, value):
        srcfile, _ = env.file_upload.get_filename(value['id'])
        fileobj = env.file_storage.fileobj(component='nextgisweb_mapnik_it')
        srlzr.obj.xml_fileobj = fileobj
        dstfile = env.file_storage.filename(fileobj, makedirs=True)

        with open(srcfile, 'r') as fs, open(dstfile, 'w') as fd:
            copyfileobj(fs, fd)


class QgisVectorStyleSerializer(Serializer):
    identity = MapnikVectorStyle.identity
    resclass = MapnikVectorStyle

    file_upload = _file_upload_attr(read=None, write=ResourceScope.update)
