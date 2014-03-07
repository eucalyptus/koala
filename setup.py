import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.rst')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.txt')) as f:
    CHANGES = f.read()

requires = [
    'beaker >= 1.5.4',
    'boto >= 2.23.0',
    'chameleon >= 2.5.3',
    'gevent >= 0.13.8',  # gevent 1.0 no longer requires libevent, it bundles libev instead
    'greenlet >= 0.3.1',
    'gunicorn >= 18.0',
    'M2Crypto >= 0.20.2',
    'ordereddict == 1.1',  # Required by Chameleon for Python 2.6 compatibility
    'pycrypto >= 2.6',
    'Paste >= 1.5',
    'pyramid >= 1.4',
    'pyramid_beaker >= 0.8',
    'pyramid_chameleon >= 0.1',
    'pyramid_layout >= 0.8',
    'pyramid_mailer >= 0.13',
    'pyramid_tm >= 0.7',
    'python-dateutil <= 1.5',  # Don't use 2.x series unless on Python 3
    'simplejson >= 2.0.9',
    # 'SQLAlchemy == 0.8.3',
    'waitress >= 0.8.8',
    'WTForms >= 1.0.2',
]

message_extractors = {'.': [
    ('**.py', 'lingua_python', None),
    ('**.pt', 'lingua_xml', None),
]}

setup(
    name='koala',
    version='4.0.0-prealpha',
    description='Koala, the Eucalyptus Management Console',
    long_description=README + '\n\n' + CHANGES,
    classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
    ],
    author='Eucalyptus Systems',
    author_email='info@eucalyptus.com',
    url='http://www.eucalyptus.com',
    keywords='web pyramid pylons',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=requires,
    tests_require=[],
    message_extractors=message_extractors,
    test_suite="tests",
    entry_points="""\
    [paste.app_factory]
    main = koala:main
    """,
)
