# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import lxml.etree.ElementTree as ET
from collections import namedtuple
from Queue import Queue
from shutil import copyfileobj
from StringIO import StringIO
try:
    import mapnik
except ImportError:
    import mapnik2 as mapnik
from PIL import Image
from zope.interface import implements


from nextgisweb import db
from nextgisweb.env import env
from nextgisweb.feature_layer import IFeatureLayer
from nextgisweb.file_storage import FileObj
from nextgisweb.geometry import box
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
from .util import _

Base = declarative_base()

ImageOptions = namedtuple('ImageOptions', [
    'fndata', 'srs', 'render_size', 'extended', 'target_box', 'result'])
LegendOptions = namedtuple('LegendOptions', [
    'qml', 'geometry_type', 'layer_name', 'result'])


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
        res_x = (extent[2] - extent[0]) / size[0]
        res_y = (extent[3] - extent[1]) / size[1]

        # Экстент с учетом отступов
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

        # Выбираем объекты по экстенту
        feature_query = self.parent.feature_query()
        if cond is not None:
            feature_query.filter_by(**cond)

        if hasattr(feature_query, 'srs'):
            feature_query.srs(srs)
        feature_query.intersects(box(*extent, srid=srs.id))
        feature_query.geom()
        features = feature_query()

        res_im = None
        ds = mapnik.MemoryDatasource()
        try:
            for (fid, f) in enumerate(features):
                if mapnik.mapnik_version() < 200100:
                    feature = mapnik.Feature(fid)
                else:
                    feature = mapnik.Feature(mapnik.Context(), fid)
                feature.add_geometries_from_wkb(f.geom.wkb)
                ds.add_feature(feature)

            style_content = str(self.style_content)

            m = mapnik.Map(size[0], size[1])
            mapnik.load_map_from_string(m, style_content)
            m.zoom_to_box(mapnik.Box2d(*extent))

            layer = mapnik.Layer('main')
            layer.datasource = ds

            root = ET.fromstring(style_content)
            styles = [s.attrib.get('name') for s in root.iter('Style')]
            for s in styles:
                layer.styles.append(s)
            m.layers.append(layer)

            img = mapnik.Image(size[0], size[1])
            mapnik.render(m, img)
            data = img.tostring('png')

            # Преобразуем изображение из PNG в объект PIL
            buf = StringIO()
            buf.write(data)
            buf.seek(0)

            res_im = Image.open(buf)
        except Exception as e:
            self.logger.error(e.message)

        return res_im

    def render_legend(self):
        result = Queue()
        options = LegendOptions(env.file_storage.filename(self.xml_fileobj),
                                self.parent.geometry_type,
                                self.parent.display_name, result)
        env.qgis.queue.put(options)
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