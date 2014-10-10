# -*- coding: utf-8 -*-
# Copyright 2013-2014 Eucalyptus Systems, Inc.
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
Forms for Volumes

"""
import wtforms
from wtforms import validators

from ..i18n import _
from . import BaseSecureForm, ChoicesManager, TextEscapedField, BLANK_CHOICE


class VolumeForm(BaseSecureForm):
    """Volume form
       Note: no need to add a 'tags' field.  Use the tag_editor panel (in a template) instead
    """
    name_error_msg = _(u'Not a valid name')
    name = TextEscapedField(label=_(u'Name'))
    snapshot_id = wtforms.SelectField(label=_(u'Create from snapshot?'))
    size_error_msg = _(u'Volume size is required and must be an integer')
    size = wtforms.TextField(
        label=_(u'Volume size (GB)'),
        validators=[validators.DataRequired(message=size_error_msg)],
    )
    zone_error_msg = _(u'Availability zone is required')
    zone = wtforms.SelectField(
        label=_(u'Availability zone'),
        validators=[validators.DataRequired(message=zone_error_msg)],
    )

    def __init__(self, request, conn=None, volume=None, snapshots=None, zones=None, **kwargs):
        """
        :param snapshots: list of snapshot objects
        :param zones: list of availability zones

        """
        super(VolumeForm, self).__init__(request, **kwargs)
        self.cloud_type = request.session.get('cloud_type', 'euca')
        self.conn = conn
        self.volume = volume
        self.snapshots = snapshots or []
        self.zones = zones or []
        self.name.error_msg = self.name_error_msg
        self.size.error_msg = self.size_error_msg
        self.zone.error_msg = self.zone_error_msg
        self.choices_manager = ChoicesManager(conn=conn)
        region = request.session.get('region')
        self.set_choices(region)

        if volume is not None:
            self.name.data = volume.tags.get('Name', '')
            self.size.data = volume.size
            self.snapshot_id.data = volume.snapshot_id if volume.snapshot_id else ''
            self.zone.data = volume.zone

    def set_choices(self, region):
        self.set_volume_snapshot_choices()
        self.zone.choices = self.choices_manager.availability_zones(region, zones=self.zones, add_blank=False)

        # default to first zone if new volume, and at least one zone in list
        if self.volume is None and len(self.zones) > 0:
            self.zone.data = self.zones[0].name

    def set_volume_snapshot_choices(self):
        choices = self.choices_manager.snapshots()
        # Need to insert current choice since the source snapshot may have been removed after this volume was created
        if self.volume and self.volume.snapshot_id:
            snap_id = self.volume.snapshot_id
            choices.append((snap_id, snap_id))
        self.snapshot_id.choices = sorted(choices)


class DeleteVolumeForm(BaseSecureForm):
    """CSRF-protected form to delete a volume"""
    pass


class CreateSnapshotForm(BaseSecureForm):
    """CSRF-protected form to create a snapshot from a volume"""
    name = wtforms.TextField(label=_(u'Name'))
    description = wtforms.TextAreaField(
        label=_(u'Description'),
        validators=[
            validators.Length(max=255, message=_(u'Description must be less than 255 characters'))
        ],
    )

    def __init__(self, request, **kwargs):
        super(CreateSnapshotForm, self).__init__(request, **kwargs)
        self.request = request


class DeleteSnapshotForm(BaseSecureForm):
    """CSRF-protected form to delete a snapshot from a volume"""
    pass


class RegisterSnapshotForm(BaseSecureForm):
    """CSRF-protected form to delete a snapshot"""
    name = wtforms.TextField(label=_(u'Name'),
        validators=[validators.InputRequired(message=_(u'Image name is required'))])
    description = wtforms.TextAreaField(
        label=_(u'Description'),
        validators=[
            validators.Length(max=255, message=_(u'Description must be less than 255 characters'))
        ],
    )
    dot = wtforms.BooleanField(label=_(u'Delete on terminate'))
    reg_as_windows = wtforms.BooleanField(label=_(u'Register as Windows OS image'))


class AttachForm(BaseSecureForm):
    """CSRF-protected form to attach a volume to a selected instance
       Note: This is for attaching a volume to a choice of instances on the volume detail page
             The form to attach a volume to an instance at the instance page is at forms.instances.AttachVolumeForm
    """
    instance_error_msg = _(u'Instance is required')
    instance_id = wtforms.SelectField(
        label=_(u'Instance'),
        validators=[validators.InputRequired(message=instance_error_msg)],
    )
    device_error_msg = _(u'Device is required')
    device = wtforms.TextField(
        label=_(u'Device'),
        validators=[validators.InputRequired(message=device_error_msg)],
    )

    # requires instances which comes from: self.conn.get_only_instances()
    def __init__(self, request, volume=None, instances=None, **kwargs):
        super(AttachForm, self).__init__(request, **kwargs)
        self.request = request
        self.volume = volume
        self.instances = instances or []
        self.instance_id.error_msg = self.instance_error_msg
        self.device.error_msg = self.device_error_msg
        self.set_instance_choices()

    def set_instance_choices(self):
        """Populate instance field with instances available to attach volume to"""
        if self.volume:
            from ..views import BaseView
            choices = [BLANK_CHOICE]
            for instance in self.instances:
                if instance.state in ["running", "stopped"] and self.volume.zone == instance.placement:
                    name_tag = instance.tags.get('Name')
                    extra = ' ({name})'.format(name=name_tag) if name_tag else ''
                    inst_name = '{id}{extra}'.format(id=instance.id, extra=extra)
                    choices.append((instance.id, BaseView.escape_braces(inst_name)))
            if len(choices) == 1:
                prefix = _(u'No available instances in availability zone')
                msg = '{0} {1}'.format(prefix, self.volume.zone)
                choices = [('', msg)]
            self.instance_id.choices = choices
        else:
            # We need to set all instances as choices for the landing page to avoid failed validation of instance field
            # The landing page JS restricts the choices based on the selected volume's availability zone
            self.instance_id.choices = [(instance.id, instance.id) for instance in self.instances]


class DetachForm(BaseSecureForm):
    """CSRF-protected form to detach a volume from an instance"""
    pass


class VolumesFiltersForm(BaseSecureForm):
    """Form class for filters on landing page"""
    zone = wtforms.SelectMultipleField(label=_(u'Availability zones'))
    status = wtforms.SelectMultipleField(label=_(u'Status'))
    tags = TextEscapedField(label=_(u'Tags'))

    def __init__(self, request, conn=None, **kwargs):
        super(VolumesFiltersForm, self).__init__(request, **kwargs)
        self.request = request
        self.choices_manager = ChoicesManager(conn=conn)
        region = request.session.get('region')
        self.zone.choices = self.get_availability_zone_choices(region)
        self.status.choices = self.get_status_choices()

    def get_availability_zone_choices(self, region):
        return self.choices_manager.availability_zones(region, add_blank=False)

    @staticmethod
    def get_status_choices():
        return (
            ('available', 'Available'),
            ('in-use', 'In use'),
        )
