# -*- coding: utf-8 -*-
"""
Forms for Volumes

"""
import wtforms
from wtforms import validators

from pyramid.i18n import TranslationString as _

from . import BaseSecureForm


class VolumeForm(BaseSecureForm):
    """Volume form
       Note: no need to add a 'tags' field.  Use the tag_editor panel (in a template) instead
    """
    name = wtforms.TextField(label=_(u'Name'))
    snapshot_id = wtforms.SelectField(label=_(u'Create from snapshot?'))
    size_error_msg = _(u'Volume size is required')
    size = wtforms.TextField(
        label=_(u'Volume size (GB)'),
        validators=[validators.Required(message=size_error_msg)],
    )
    zone_error_msg = _(u'Availability zone is required')
    zone = wtforms.SelectField(
        label=_(u'Availability zone'),
        validators=[validators.Required(message=zone_error_msg)],
    )

    def __init__(self, request, volume=None, conn=None, **kwargs):
        super(VolumeForm, self).__init__(request, **kwargs)
        self.cloud_type = request.session.get('cloud_type', 'euca')
        self.volume = volume
        self.conn = conn
        self.size.error_msg = self.size_error_msg
        self.zone.error_msg = self.zone_error_msg

        if volume is not None:
            self.name.data = volume.tags.get('Name', '')
            self.size.data = volume.size
            self.snapshot_id.data = volume.snapshot_id if volume.snapshot_id else ''
            self.zone.data = volume.zone

        if conn is not None:
            self.set_volume_snapshot_choices()
            self.set_availability_zone_choices()

    def set_volume_snapshot_choices(self):
        choices = [('', _(u'None'))]
        # TODO: May need to filter get_all_snapshots() call for AWS?
        for snapshot in self.conn.get_all_snapshots():
            value = snapshot.id
            label = '{id} ({size} GB)'.format(id=snapshot.id, size=snapshot.volume_size)
            choices.append((value, label))
        self.snapshot_id.choices = sorted(choices)

    def set_availability_zone_choices(self):
        choices = [('', _(u'select...'))]
        for zone in self.conn.get_all_zones():
            choices.append((zone.name, zone.name))
        self.zone.choices = sorted(choices)


class DeleteVolumeForm(BaseSecureForm):
    """CSRF-protected form to delete a volume"""
    pass


class CreateSnapshotForm(BaseSecureForm):
    """CSRF-protected form to create a snapshot from a volume"""
    desc_error_msg = _(u'Description is required')
    description = wtforms.TextAreaField(
        label=_(u'Description'),
        validators=[
            validators.Required(message=desc_error_msg),
            validators.Length(max=255, message=_(u'Description must be less than 255 characters'))
        ],
    )

    def __init__(self, request, **kwargs):
        super(CreateSnapshotForm, self).__init__(request, **kwargs)
        self.request = request
        self.description.error_msg = self.desc_error_msg


class DeleteSnapshotForm(BaseSecureForm):
    """CSRF-protected form to delete a snapshot from a volume"""
    pass


class AttachForm(BaseSecureForm):
    """CSRF-protected form to attach a volume to a selected instance
       Note: This is for attaching a volume to a choice of instances on the volume detail page
             The form to attach a volume to an instance at the instance page is at forms.instances.AttachVolumeForm
    """
    instance_error_msg = _(u'Instance is required')
    instance_id = wtforms.SelectField(
        label=_(u'Instance'),
        validators=[validators.Required(message=instance_error_msg)],
    )
    device_error_msg = _(u'Device is required')
    device = wtforms.TextField(
        label=_(u'Device'),
        validators=[validators.Required(message=device_error_msg)],
    )

    def __init__(self, request, volume=None, conn=None, **kwargs):
        super(AttachForm, self).__init__(request, **kwargs)
        self.request = request
        self.conn = conn
        self.volume = volume
        self.instance_id.error_msg = self.instance_error_msg
        self.device.error_msg = self.device_error_msg
        if conn is not None:
            self.set_instance_choices()

    def set_instance_choices(self):
        """Populate instance field with instances available to attach volume to"""
        choices = [('', _(u'select...'))]
        for instance in self.conn.get_only_instances():
            if self.volume and self.volume.zone == instance.placement:
                name_tag = instance.tags.get('Name')
                extra = ' ({name})'.format(name=name_tag) if name_tag else ''
                vol_name = '{id}{extra}'.format(id=instance.id, extra=extra)
                choices.append((instance.id, vol_name))
        if len(choices) == 1:
            choices = [('', _(u'No available volumes in the availability zone'))]
        self.instance_id.choices = choices


class DetachForm(BaseSecureForm):
    """CSRF-protected form to detach a volume from an instance"""
    pass
