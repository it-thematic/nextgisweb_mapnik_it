from .component import MapnikComponent
from .model import MapnikStyle

def pkginfo():
    return dict(
        components=dict(
        mapnik='nextgisweb_mapnik'))


def amd_packages():
    return ((
                'ngw-mapnik', 'nextgisweb_mapnik:amd/ngw-mapnik'
            ),)
