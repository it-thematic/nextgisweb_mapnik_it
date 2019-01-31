# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from pyramid.response import FileResponse

from nextgisweb.env import env
from nextgisweb.resource import resource_factory, ResourceScope

from .model import MapnikVectorStyle


def vector_style_xml(request):
    request.resource_permission(ResourceScope.read)

    fn = env.file_storage.filename(request.context.xml_fileobj)

    response = FileResponse(fn, request=request)
    response.content_disposition = (b'attachment; filename=%d.xml'
                                    % request.context.id)

    return response


def setup_pyramid(comp, config):
    config.add_route(
        'mapnik_it.vector_style_xml', '/api/resource/{id}/xml',
        factory=resource_factory
    ).add_view(vector_style_xml, context=MapnikVectorStyle, request_method='GET')
