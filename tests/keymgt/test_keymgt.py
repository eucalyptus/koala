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
import tempfile
import os
import ConfigParser


class TestKeyMgt(unittest.TestCase):
    def test_generate_keyini(self):
        from eucaconsole.keymgt import generate_keyini
        ignored, filename = tempfile.mkstemp()
        try:
            # ensure temp file has bad perms
            os.chmod(filename, 0o664)
            generate_keyini(filename)
            config = ConfigParser.ConfigParser()
            config.read(filename)
            self.assertTrue(config.has_section('general'))
            perms = oct(os.stat(filename).st_mode)[4:]
            self.assertEqual(perms, '600')
        finally:
            os.remove(filename)

    def test_ensure_session_keys(self):
        from eucaconsole.keymgt import ensure_session_keys
        ignored, filename = tempfile.mkstemp()
        os.remove(filename)
        settings = {'session.keyini': filename}

        ensure_session_keys(settings)
        key = settings.get('session.validate_key', None)
        self.assertTrue(key is not None)

        ensure_session_keys(settings)
        self.assertEqual(key, settings['session.validate_key'])

        os.remove(filename)
