# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from pyramid.response import FileResponse

from nextgisweb.env import env
from nextgisweb.resource import resource_factory, ResourceScope

from .model import MapnikStyle


def style_xml(request):
    request.resource_permission(ResourceScope.read)

    fn = env.file_storage.filename(request.context.xml_fileobj)

    response = FileResponse(fn, request=request)
    response.content_disposition = ('attachment; filename=%d.xml' % request.context.id)

    return response


def setup_pyramid(comp, config):
    config.add_route(
        'mapnik.style_xml', '/api/resource/{id}/xml',
        factory=resource_factory
    ).add_view(style_xml, context=MapnikStyle, request_method='GET')
