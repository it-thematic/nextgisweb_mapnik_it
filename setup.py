import io
from setuptools import setup, find_packages

with io.open("VERSION", mode="r") as fd:
    VERSION = fd.read().rstrip()

requires = (
    # 'mapnik',
    'nextgisweb>=4.7.0.dev14',
    'Pillow',
)

entry_points = {
    'nextgisweb.packages': [
        'nextgisweb_mapnik = nextgisweb:single_component',
    ],

    'nextgisweb.amd_packages': [
        'nextgisweb_mapnik = nextgisweb_mapnik:amd_packages',
    ],

}

setup(
    name='nextgisweb_mapnik',
    version=VERSION,
    description="Mapnik renderer for NextGIS Web",
    author="IT-Thematic",
    author_email="inbox@it-thematic.ru",
    license='MIT',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    include_package_data=True,
    zip_safe=False,
    python_requires='>=3.8,<4',
    install_requires=requires,
    entry_points=entry_points,
)
