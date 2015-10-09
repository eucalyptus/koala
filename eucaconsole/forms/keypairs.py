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
Forms for Key Pairs

"""
import wtforms
from wtforms import validators

from ..i18n import _
from . import BaseSecureForm


class KeyPairForm(BaseSecureForm):
    """Key Pair Create form
    """
    name_error_msg = _(u'Keypair name must be between 1 and 255 ASCII characters long')
    name = wtforms.TextField(
        id=u'key-name',
        label=_(u'Name'),
        validators=[validators.InputRequired(message=name_error_msg), validators.Length(min=1, max=255)],
    )

    def __init__(self, request, keypair=None, **kwargs):
        super(KeyPairForm, self).__init__(request, **kwargs)
        self.request = request
        self.name.error_msg = self.name_error_msg  # Used for Foundation Abide error message
        if keypair is not None:
            self.name.data = keypair.name


class KeyPairImportForm(BaseSecureForm):
    """Key Pair Import form
    """
    name_error_msg = _(u'Name is required')
    key_material_error_msg = _(u'Public Key Contents are required')
    name = wtforms.TextField(
        id=u'key-name',
        label=_(u'Name'),
        validators=[validators.InputRequired(message=name_error_msg), validators.Length(min=1, max=255)],
    )
    key_material = wtforms.TextAreaField(
        id=u'key-import-contents',
        label=_(u'Public SSH Key Contents'),
        validators=[validators.InputRequired(message=key_material_error_msg), validators.Length(min=1)],
    )

    def __init__(self, request, keypair=None, **kwargs):
        super(KeyPairImportForm, self).__init__(request, **kwargs)
        self.request = request
        self.name.error_msg = self.name_error_msg  # Used for Foundation Abide error message
        self.key_material.error_msg = self.key_material_error_msg
        if keypair is not None:
            self.name.data = keypair.name


class KeyPairDeleteForm(BaseSecureForm):
    """KeyPair deletion form.
       Only need to initialize as a secure form to generate CSRF token
    """
    pass


