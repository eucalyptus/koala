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

import unittest


class Mock(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class MockConfig(Mock):
    def __init__(self):
        self.tweens = []

    def add_tween(self, mpath):
        self.tweens.append(mpath)


class MockHandler(object):
    def __init__(self, content_type=None):
        self.headers = {}
        self.content_type = content_type

    def __call__(self, request):
        return Mock(content_type=self.content_type,
                    headers=self.headers)


class MockRequest(object):
    def __init__(self):
        self.environ = {}


class TestSetup(unittest.TestCase):
    def test_it(self):
        from eucaconsole.tweens import setup_tweens

        config = MockConfig()
        self.assertTrue(len(config.tweens) == 0)
        settings = {'log.useractions': 'true'}
        setup_tweens(config, settings)
        self.assertTrue(len(config.tweens) > 1)


class TestCTHeaders(unittest.TestCase):
    def test_factory(self):
        from eucaconsole.tweens import \
            CTHeadersTweenFactory as factory
        tween = factory(None, None)
        self.assertTrue(callable(tween))

    def test_tween(self):
        from eucaconsole.tweens import \
            CTHeadersTweenFactory as factory

        tween = factory(MockHandler('image/jpeg'), None)
        res = tween(None)
        for name, value in factory.header_map['text/html'].items():
            # make sure html resources *are* getting header
            self.assertFalse(name in res.headers)

        tween = factory(MockHandler('text/html'), None)
        res = tween(None)
        for name, value in factory.header_map['text/html'].items():
            # make sure html resources *are* getting header
            self.assertTrue(name in res.headers)
            self.assertTrue(res.headers[name] == value)

    def test_csp_header(self):
        """Determine if CSP headers are properly set"""
        from eucaconsole.tweens import CTHeadersTweenFactory as CTFactory
        headers = CTFactory.header_map['text/html']
        self.assertTrue('CONTENT-SECURITY-POLICY' in headers.keys())
        self.assertTrue('X-CONTENT-SECURITY-POLICY' in headers.keys())  # IE requires header prefix
        self.assertEquals(headers.get('CONTENT-SECURITY-POLICY'), "script-src 'self'; form-action 'self';")
        self.assertEquals(headers.get('X-CONTENT-SECURITY-POLICY'), "script-src 'self'; form-action 'self';")


class TestHTTPSTween(unittest.TestCase):
    def test_it(self):
        from eucaconsole.tweens import \
            https_tween_factory as factory
        tween = factory(MockHandler(), None)

        request = Mock(scheme=None, environ={})
        tween(request)
        self.assertTrue(request.scheme is None)

        request = Mock(scheme=None,
                       environ={'HTTP_X_FORWARDED_PROTO': 'https'})
        tween(request)
        self.assertEqual(request.scheme, 'https')


class TestRequestIDTween(unittest.TestCase):
    def test_it(self):
        from eucaconsole.tweens import request_id_tween_factory as factory
        tween = factory(MockHandler(), None)

        request = Mock(id=None)
        request.session = dict(account='foo')
        tween(request)
        self.assertFalse(request.id is None)

