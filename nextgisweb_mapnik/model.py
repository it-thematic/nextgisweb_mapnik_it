# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
from collections import namedtuple
from shutil import copyfileobj

try:
    import Queue as queue
    from StringIO import StringIO as StringIO
except ImportError:
    import queue as queue
    from io import StringIO as StringIO
try:
    import mapnik
except ImportError:
    import mapnik2 as mapnik

from zope.interface import implements

from nextgisweb import db
from nextgisweb.env import env
from nextgisweb.feature_layer import IFeatureLayer, on_data_change as on_data_change_feature_layer
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
    ILegendableStyle,
    on_style_change,
    on_data_change as on_data_change_renderable
)
from nextgisweb.spatial_ref_sys import SRS
from .util import _

Base = declarative_base()

ImageOptions = namedtuple('ImageOptions', ['style_id', 'map_xml', 'render_size', 'extended', 'target_box'])
LegendOptions = namedtuple('LegendOptions', ['xml', 'geometry_type', 'layer_name'])


def _render_bounds(extent, size, padding):
    res_x = (extent[2] - extent[0]) / size[0]
    res_y = (extent[3] - extent[1]) / size[1]

    # Bounding box with padding
    extended = (
        extent[0] - res_x * padding,
        extent[1] - res_y * padding,
        extent[2] + res_x * padding,
        extent[3] + res_y * padding,
    )

    # Image dimensions
    render_size = (
        size[0] + 2 * padding,
        size[1] + 2 * padding
    )

    # Crop box
    target_box = (
        padding,
        padding,
        size[0] + padding,
        size[1] + padding
    )

    return extended, render_size, target_box


class MapnikStyle(Base, Resource):
    identity = 'mapnik_style'
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
        extended, render_size, target_box = _render_bounds(extent, size, padding)

        with open(env.file_storage.filename(self.xml_fileobj), mode='r') as f:
            map_xml = f.read()
        options = ImageOptions(self.id, map_xml, render_size, extended, target_box)
        return env.mapnik.renderer_job(options)

    def render_legend(self):
        with open(env.file_storage.filename(self.xml_fileobj), mode='r') as f:
            map_xml = f.read()
        options = LegendOptions(map_xml, self.parent.geometry_type, self.parent.display_name)
        return env.mapnik.renderer_job(options)


@on_data_change_feature_layer.connect
def on_data_change_feature_layer(resource, geom):
    for child in resource.children:
        if isinstance(child, MapnikStyle):
            on_data_change_renderable.fire(child, geom)


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
        fileobj = env.file_storage.fileobj(component='nextgisweb_mapnik')
        srlzr.obj.xml_fileobj = fileobj
        dstfile = env.file_storage.filename(fileobj, makedirs=True)

        with open(srcfile, 'r') as fs, open(dstfile, 'w') as fd:
            copyfileobj(fs, fd)
        on_style_change.fire(srlzr.obj)


class MapnikVectorStyleSerializer(Serializer):
    identity = MapnikStyle.identity
    resclass = MapnikStyle

    file_upload = _file_upload_attr(read=None, write=ResourceScope.update)
