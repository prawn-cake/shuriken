from pip.req import parse_requirements
import os
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

current_dir = os.path.dirname(os.path.abspath(__file__))

install_reqs = parse_requirements('/'.join([current_dir, 'requirements.txt']))
reqs = [str(ir.req) for ir in install_reqs]

setup(
    name='shuriken',
    version='0.1.5',
    packages=['shuriken'],
    url='https://github.com/prawn-cake/shuriken.git',
    license='MIT',
    author='prawn-cake',
    author_email='ekimovsky.maksim@gmail.com',
    description='Shuriken is a monitoring agent which allows to do passive '
                'checks for Shinken monitoring system vie mod-ws-arbiter.',
    install_requires=reqs
)
