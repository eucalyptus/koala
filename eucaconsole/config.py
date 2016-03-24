# -*- coding: utf-8 -*-
# Copyright 2013-2015 Hewlett Packard Enterprise Development LP
#
# Redistribution and use of this software in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
# Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Pyramid configuration helpers

"""

import boto
import json
import logging
import os
import sys

from pyramid.config import Configurator
from pyramid.authentication import SessionAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.events import BeforeRender
from pyramid.settings import asbool

from .i18n import custom_locale_negotiator
from .models import SiteRootFactory
from .models.auth import groupfinder, User
from .routes import urls
from .tweens import setup_tweens
from .keymgt import ensure_session_keys
from .mime import check_types
from .caches import short_term
from .caches import default_term
from .caches import long_term
from .caches import extra_long_term
from .views import escape_braces


try:
    from version import __version__
except ImportError:
    __version__ = 'DEVELOPMENT'

REQUIRED_CONFIG = {
    # 'use': 'egg:eucaconsole',  # can't test for this since container strips it
    'pyramid.includes': ['pyramid_beaker', 'pyramid_chameleon', 'pyramid_layout'],
    'session.type': 'cookie',
    'cache.memory': 'dogpile.cache.pylibmc'
}


def check_config(settings):
    # check for required config first
    for key in REQUIRED_CONFIG.keys():
        value = REQUIRED_CONFIG[key]
        list_failed = False
        is_list = isinstance(value, list)
        if is_list:
            try:
                for item in value:
                    settings.get(key).index(item)
            except ValueError:
                list_failed = True
        if list_failed or (not is_list and settings.get(key) != value):
            if is_list:
                value = '\n'.join(value)
            logging.error("*****************************************************************")
            logging.error(u" Required configuration value {0} = {1} not found in console.ini".format(key, value))
            logging.error(" Please correct this and restart eucaconsole.")
            logging.error("*****************************************************************")
            sys.exit(1)
    if not settings.get('ufshost'):
        logging.warn(
            "'clchost' and 'clcport' are deprecated in Eucalyptus version 4.2.0 and "
            "will be removed in version 4.3.0. Use 'ufshost' and 'ufsport' instead."
        )
    bad_hosts = ['localhost', '127.0.0.1']
    if settings.get('ufshost') in bad_hosts or settings.get('clchost') in bad_hosts:
        logging.warn(
            "'ufshost' needs to be set to something externally resolvable."
            "Stack creation and object download will not work properly until this is fixed."
        )


def write_routes_json(path):
    url_dict = {}
    for url in urls:
        url_dict[url.name] = url.pattern.replace('{', '{{').replace('}', '}}')
    with open(os.path.join(path, 'routes.json'), 'w') as outfile:
        json.dump(url_dict, outfile)


def get_configurator(settings, enable_auth=True):
    check_config(settings)
    connection_debug = asbool(settings.get('connection.debug'))
    boto.set_stream_logger('boto', level=(logging.DEBUG if connection_debug else logging.CRITICAL))
    ensure_session_keys(settings)
    check_types()
    config = Configurator(root_factory=SiteRootFactory, settings=settings)
    if enable_auth:
        authn_policy = SessionAuthenticationPolicy(callback=groupfinder)
        authz_policy = ACLAuthorizationPolicy()
        config.set_authentication_policy(authn_policy)
        config.set_authorization_policy(authz_policy)
        config.set_default_permission('view')
    config.add_request_method(User.get_auth_user, 'user', reify=True)
    config.add_subscriber(escape_braces, BeforeRender)
    cache_duration = int(settings.get('static.cache.duration', 43200))
    config.add_static_view(name='static/' + __version__, path='static', cache_max_age=cache_duration)
    config.add_layout('eucaconsole.layout.MasterLayout',
                      'eucaconsole.layout:templates/master_layout.pt')

    route_dir = os.path.join(os.getcwd(), 'run')
    if not os.path.exists(route_dir) and os.path.exists('/var/run/eucaconsole'):
        route_dir = '/var/run/eucaconsole'
    write_routes_json(route_dir)
    config.add_static_view(name='static/json', path=route_dir, cache_max_age=cache_duration)

    locale_dir = os.path.join(os.getcwd(), 'locale')
    # use local locale directory over system one
    if not os.path.exists(locale_dir) and os.path.exists('/usr/share/locale'):
        locale_dir = '/usr/share/locale'
    config.add_translation_dirs(locale_dir)
    config.set_locale_negotiator(custom_locale_negotiator)

    for route in urls:
        config.add_route(route.name, route.pattern)

    setup_tweens(config, settings)
    config.scan('.views')

    if not boto.config.has_section('Boto'):
        boto.config.add_section('Boto')
    boto.config.set('Boto', 'num_retries', settings.get('connection.retries', '2'))

    memory_cache = settings.get('cache.memory')
    memory_cache_url = settings.get('cache.memory.url')
    username = settings.get('cache.username', None)
    password = settings.get('cache.password', None)
    short_term.configure(
        memory_cache,
        expiration_time=int(settings.get('cache.short_term.expire')),
        arguments={
            'url': [memory_cache_url],
            'binary': True,
            'min_compress_len': 1024,
            'behaviors': {"tcp_nodelay": True, "ketama": True},
            'username': username,
            'password': password
        },
    )
    default_term.configure(
        memory_cache,
        expiration_time=int(settings.get('cache.default_term.expire')),
        arguments={
            'url': [memory_cache_url],
            'binary': True,
            'min_compress_len': 1024,
            'behaviors': {"tcp_nodelay": True, "ketama": True},
            'username': username,
            'password': password
        },
    )
    long_term.configure(
        memory_cache,
        expiration_time=int(settings.get('cache.long_term.expire')),
        arguments={
            'url': [memory_cache_url],
            'binary': True,
            'min_compress_len': 1024,
            'behaviors': {"tcp_nodelay": True, "ketama": True},
            'username': username,
            'password': password
        },
    )
    extra_long_term.configure(
        memory_cache,
        expiration_time=int(settings.get('cache.extra_long_term.expire')),
        arguments={
            'url': [memory_cache_url],
            'binary': True,
            'min_compress_len': 1024,
            'behaviors': {"tcp_nodelay": True, "ketama": True},
            'username': username,
            'password': password
        },
    )
    return config


def main(global_config, **settings):
    """
    Main WSGI app

    The WSGI app object returned from main() is invoked from the following section in the console.ini config file...

    [app:main]
    use = egg:eucaconsole

    ...which points to eucaconsole.egg-info/entry_points.txt
    [paste.app_factory]
    main = eucaconsole.config:main

    Returns a Pyramid WSGI application"""
    app_config = get_configurator(settings)
    return app_config.make_wsgi_app()

