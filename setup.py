#!/usr/bin/env python
from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

setup(
    name='datajoint-dashboard',
    version='0.0.1',
    description='Toolbox for dash GUI development for DataJoint pipelines',
    author='Vathes',
    author_email='support@vathes.com',
    packages=find_packages(exclude=[]),
    install_requires=['datajoint==0.12.8', 'dash', 'dash-bootstrap-components'],
)
