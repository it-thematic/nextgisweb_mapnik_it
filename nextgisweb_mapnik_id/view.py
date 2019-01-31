# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import

from nextgisweb.resource import Widget, Resource
import nextgisweb.dynmenu as dm

from .model import MapnikVectorStyle
from .util import _


class Widget(Widget):
    resource = MapnikVectorStyle
    operation = ('create', 'update')
    amdmod = 'ngw-mapnik/MapnikStyleWidget'


def setup_pyramid(comp, config):
    # Расширения меню слоя
    class LayerMenuExt(dm.DynItem):

        def build(self, args):
            if isinstance(args.obj, MapnikVectorStyle):
                yield dm.Label('mapnik_vector_style', _(u"Mapnik style"))

                if args.obj.xml_fileobj is not None:
                    yield dm.Link(
                        'mapnik_vector_style/xml', _(u"XML file"),
                        lambda args: args.request.route_url(
                            "mapnik.vector_style_xml", id=args.obj.id))

    Resource.__dynmenu__.add(LayerMenuExt())
