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
Forms for Images

"""
import wtforms
from wtforms import validators
from ..constants.images import EUCA_IMAGE_OWNER_ALIAS_CHOICES, AWS_IMAGE_OWNER_ALIAS_CHOICES

from ..i18n import _
from ..views import BaseView
from . import BaseSecureForm, TextEscapedField


class ImageForm(BaseSecureForm):
    """Image form
       Note: no need to add a 'tags' field.  Use the tag_editor panel (in a template) instead
       Only need to initialize as a secure form to generate CSRF token
    """
    desc_error_msg = _(u'Description is required')
    description = wtforms.TextAreaField(
        label=_(u'Description'),
        validators=[
            validators.Length(max=255, message=_(u'Description must be less than 255 characters'))
        ],
    )

    def __init__(self, request, image=None, conn=None, **kwargs):
        super(ImageForm, self).__init__(request, **kwargs)
        self.image = image
        self.conn = conn
        self.description.error_msg = self.desc_error_msg

        if image is not None:
            self.description.data = BaseView.escape_braces(image.description)


class DeregisterImageForm(BaseSecureForm):
    """
    Deregister image form
    Note: delete_snapshot option only applies to EBS-backed images
    """
    delete_snapshot = wtforms.BooleanField(label=_(u'Delete associated snapshot'))


class ImagesFiltersForm(BaseSecureForm):
    """Form class for filters on landing page"""
    owner_alias = wtforms.SelectField(label=_(u'Images owned by'))
    platform = wtforms.SelectMultipleField(label=_(u'Platform'))
    root_device_type = wtforms.SelectMultipleField(label=_(u'Root device type'))
    architecture = wtforms.SelectMultipleField(label=_(u'Architecture'))
    tags = TextEscapedField(label=_(u'Tags'))

    def __init__(self, request, cloud_type='euca', **kwargs):
        super(ImagesFiltersForm, self).__init__(request, **kwargs)
        self.request = request
        self.cloud_type = cloud_type
        self.owner_alias.choices = self.get_owner_choices()
        self.platform.choices = self.get_platform_choices()
        self.root_device_type.choices = self.get_root_device_type_choices()
        self.architecture.choices = self.get_architecture_choices()
        if cloud_type == 'aws' and not self.request.params.get('owner_alias'):
            self.owner_alias.data = 'amazon'  # Default to Amazon AMIs on AWS
        self.facets = [
            {'name': 'owner_alias', 'label': self.owner_alias.label.text, 'options': self.get_owner_choices()},
            {'name': 'platform', 'label': self.platform.label.text, 'options': self.get_platform_choices()},
            {'name': 'architecture', 'label': self.architecture.label.text, 'options': self.get_architecture_choices()},
            {
                'name': 'root_device_type',
                'label': self.root_device_type.label.text,
                'options': self.get_root_device_type_choices()
            },
        ]

    def get_owner_choices(self):
        owner_choices = EUCA_IMAGE_OWNER_ALIAS_CHOICES
        if self.cloud_type == 'aws':
            owner_choices = AWS_IMAGE_OWNER_ALIAS_CHOICES
        return owner_choices

    def get_platform_choices(self):
        if self.cloud_type == 'euca':
            return [
                {'key': 'linux', 'label': _(u'Linux')},
                {'key': 'windows', 'label': _(u'Windows')},
            ]
        else:
            return [{'key': 'windows', 'label': _(u'Windows')}]

    @staticmethod
    def get_root_device_type_choices():
        return [
            {'key': 'ebs', 'label': _(u'EBS')},
            {'key': 'instance-store', 'label': _(u'Instance-store')},
        ]

    @staticmethod
    def get_architecture_choices():
        return [
            {'key': 'x86_64', 'label': _(u'64-bit')},
            {'key': 'i386', 'label': _(u'32-bit')},
        ]

