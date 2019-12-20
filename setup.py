import os
import sys

from setuptools import setup, find_packages


version = '0.0'

requires = (
    'nextgisweb',
    'Pillow'
)

entry_points = {
    'nextgisweb.packages': [
        'nextgisweb_mapnik_it = nextgisweb_mapnik_it:pkginfo',
    ],

    'nextgisweb.amd_packages': [
        'nextgisweb_mapnik_it = nextgisweb_mapnik_it:amd_packages',
    ],

}

setup(
    name='nextgisweb_mapnik_it',
    version=version,
    description="",
    long_description="",
    classifiers=[],
    keywords='',
    author='',
    author_email='',
    url='',
    license='',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    include_package_data=True,
    zip_safe=False,
    install_requires=requires,
    entry_points=entry_points,
)
