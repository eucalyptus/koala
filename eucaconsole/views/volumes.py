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
Pyramid views for Eucalyptus and AWS volumes

"""
from dateutil import parser
from itertools import chain

import simplejson as json

from boto.exception import BotoServerError
from boto.ec2.snapshot import Snapshot

from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.view import view_config

from ..constants.cloudwatch import (
    MONITORING_DURATION_CHOICES, STATISTIC_CHOICES, GRANULARITY_CHOICES,
    DURATION_GRANULARITY_CHOICES_MAPPING
)
from ..constants.volumes import VOLUME_MONITORING_CHARTS_LIST
from ..forms import ChoicesManager
from ..forms.instances import InstanceMonitoringForm
from ..forms.volumes import (
    VolumeForm, DeleteVolumeForm, CreateSnapshotForm, DeleteSnapshotForm,
    RegisterSnapshotForm, AttachForm, DetachForm, VolumesFiltersForm)
from ..i18n import _
from ..models import Notification
from ..models.alarms import Alarm
from ..views import LandingPageView, TaggedItemView, BaseView, JSONResponse
from . import boto_error_handler


class BaseVolumeView(BaseView):
    """Base class for volume-related views"""
    def __init__(self, request, **kwargs):
        super(BaseVolumeView, self).__init__(request, **kwargs)
        self.conn = self.get_connection()

    def get_volume(self, volume_id=None):
        volume_id = volume_id or self.request.matchdict.get('id')
        if volume_id and volume_id != 'new':
            try:
                volumes_list = self.conn.get_all_volumes(volume_ids=[volume_id])
                return volumes_list[0] if volumes_list else None
            except BotoServerError:
                return None
        return None

    def get_instance(self, instance_id):
        reservations_list = self.conn.get_all_reservations(instance_ids=[instance_id])
        reservation = reservations_list[0] if reservations_list else None
        if reservation:
            return reservation.instances[0]
        return None


class VolumesView(LandingPageView, BaseVolumeView):
    VIEW_TEMPLATE = '../templates/volumes/volumes.pt'

    def __init__(self, request):
        super(VolumesView, self).__init__(request)
        self.title_parts = [_(u'Volumes')]
        self.conn = self.get_connection()
        self.initial_sort_key = '-create_time'
        self.prefix = '/volumes'
        self.location = self.get_redirect_location('volumes')
        with boto_error_handler(request, self.location):
            self.instances = self.conn.get_only_instances(
                filters={'instance-state-name': ['running', 'stopped']}) if self.conn else []
        self.delete_form = DeleteVolumeForm(self.request, formdata=self.request.params or None)
        self.attach_form = AttachForm(self.request, instances=self.instances, formdata=self.request.params or None)
        self.detach_form = DetachForm(self.request, formdata=self.request.params or None)
        self.enable_smart_table = True
        self.render_dict = dict(
            prefix=self.prefix,
            initial_sort_key=self.initial_sort_key,
        )

    @view_config(route_name='volumes', renderer=VIEW_TEMPLATE)
    def volumes_landing(self):
        # Filter fields are passed to 'properties_filter_form' template macro to display filters at left
        filter_keys = [
            'attach_status', 'create_time', 'id', 'instance', 'name', 'instance_name',
            'size', 'snapshot_id', 'status', 'tags', 'zone'
        ]
        filters_form = VolumesFiltersForm(self.request, conn=self.conn, formdata=self.request.params or None)
        search_facets = filters_form.facets
        controller_options_json = BaseView.escape_json(json.dumps({
            'instances_by_zone': self.get_instances_by_zone(self.instances),
        }))
        self.render_dict.update(dict(
            filters_form=filters_form,
            search_facets=BaseView.escape_json(json.dumps(search_facets)),
            sort_keys=self.get_sort_keys(),
            filter_keys=filter_keys,
            json_items_endpoint=self.get_json_endpoint('volumes_json'),
            attach_form=self.attach_form,
            detach_form=self.detach_form,
            delete_form=self.delete_form,
            controller_options_json=controller_options_json,
        ))
        return self.render_dict

    @view_config(route_name='volumes_delete', request_method='POST')
    def volumes_delete(self):
        volume_id_param = self.request.params.get('volume_id')
        volume_ids = [volume_id.strip() for volume_id in volume_id_param.split(',')]
        if self.delete_form.validate():
            for volume_id in volume_ids:
                volume = self.get_volume(volume_id)
                self.log_request(_(u"Deleting volume {0}").format(volume_id))
                with boto_error_handler(self.request, self.location):
                    volume.delete()
            if len(volume_ids) == 1:
                msg = _(u'Successfully sent delete volume request.  It may take a moment to delete the volume.')
            else:
                prefix = _(u'Successfully sent request to delete volumes')
                msg = u'{0} {1}'.format(prefix, ', '.join(volume_ids))
            self.request.session.flash(msg, queue=Notification.SUCCESS)
        else:
            msg = _(u'Unable to delete volume.')  # TODO Pull in form validation error messages here
            self.request.session.flash(msg, queue=Notification.ERROR)
        return HTTPFound(location=self.location)

    @view_config(route_name='volumes_attach', request_method='POST')
    def volumes_attach(self):
        volume_id = self.request.params.get('volume_id')
        instance_id = self.request.params.get('instance_id')
        device = self.request.params.get('device')
        validation_conditions = [
            self.is_csrf_valid(),
            instance_id in dict(self.attach_form.instance_id.choices)
        ]
        if all(validation_conditions):
            with boto_error_handler(self.request, self.location):
                self.log_request(_(u"Attaching volume {0} to {1} as {2}").format(volume_id, instance_id, device))
                self.conn.attach_volume(volume_id, instance_id, device)
                msg = _(u'Successfully sent request to attach volume.  It may take a moment to attach to instance.')
                self.request.session.flash(msg, queue=Notification.SUCCESS)
        else:
            msg = _(u'Unable to attach volume.')  # TODO Pull in form validation error messages here
            self.request.session.flash(msg, queue=Notification.ERROR)
        return HTTPFound(location=self.location)

    @view_config(route_name='volumes_detach', request_method='POST')
    def volumes_detach(self):
        volume_id_param = self.request.params.get('volume_id')
        volume_ids = [volume_id.strip() for volume_id in volume_id_param.split(',')]
        if self.detach_form.validate():
            for volume_id in volume_ids:
                self.log_request(_(u"Detaching volume {0}").format(volume_id))
                with boto_error_handler(self.request, self.location):
                    self.conn.detach_volume(volume_id)
            if len(volume_ids) == 1:
                msg = _(u'Request successfully submitted.  It may take a moment to detach the volume.')
            else:
                prefix = _(u'Successfully sent request to detach volumes')
                msg = u'{0} {1}'.format(prefix, ', '.join(volume_ids))
            self.request.session.flash(msg, queue=Notification.SUCCESS)
        else:
            msg = _(u'Unable to attach volume.')  # TODO Pull in form validation error messages here
            self.request.session.flash(msg, queue=Notification.ERROR)
        return HTTPFound(location=self.location)

    @staticmethod
    def get_instances_by_zone(instances):
        zones = set(instance.placement for instance in instances)
        instances_by_zone = {}
        for zone in zones:
            zone_instances = []
            for instance in instances:
                if instance.placement == zone:
                    instance_name = TaggedItemView.get_display_name(instance)
                    zone_instances.append({'id': instance.id, 'name': instance_name})
            instances_by_zone[zone] = zone_instances
        return instances_by_zone

    @staticmethod
    def get_sort_keys():
        """sort_keys are passed to sorting drop-down on landing page"""
        return [
            dict(key='create_time', name=_(u'Creation time: Oldest to Newest')),
            dict(key='-create_time', name=_(u'Creation time: Newest to Oldest')),
            dict(key='name', name=_(u'Name: A to Z')),
            dict(key='-name', name=_(u'Name: Z to A')),
            dict(key='status', name=_(u'Status')),
            dict(key='zone', name=_(u'Availability zone')),
        ]


class VolumesJsonView(LandingPageView):
    def __init__(self, request, conn=None, zone=None, enable_filters=True, **kwargs):
        super(VolumesJsonView, self).__init__(request, **kwargs)
        self.conn = conn or self.get_connection()
        self.zone = zone
        self.enable_filters = enable_filters

    @view_config(route_name='volumes_json', renderer='json', request_method='POST')
    def volumes_json(self):
        if not(self.is_csrf_valid()):
            return JSONResponse(status=400, message="missing CSRF token")
        volumes = []
        transitional_states = ['attaching', 'detaching', 'creating', 'deleting']
        filters = {}
        availability_zone_param = self.zone or self.request.params.getall('zone')
        if availability_zone_param:
            filters.update({'availability-zone': availability_zone_param})
        # Don't filter by these request params in Python, as they're included in the "filters" params sent to the CLC
        # Note: the choices are from attributes in VolumesFiltersForm
        ignore_params = ['zone']
        # Get alarms for volumes and build a list of resource ids to optimize alarm status fetch
        cw_conn = self.get_connection(conn_type='cloudwatch')
        alarms = [alarm for alarm in cw_conn.describe_alarms() if 'VolumeId' in alarm.dimensions]
        alarm_resource_ids = set(list(
            chain.from_iterable([chain.from_iterable(alarm.dimensions.values()) for alarm in alarms])
        ))
        with boto_error_handler(self.request):
            if self.enable_filters:
                filtered_items = self.filter_items(self.get_items(filters=filters), ignore=ignore_params)
            else:
                filtered_items = self.get_items()
            instance_ids = list(set([
                vol.attach_data.instance_id for vol in filtered_items if vol.attach_data.instance_id is not None]))
            if len(filtered_items) < 1000:
                volume_ids = [volume.id for volume in filtered_items]
                snapshots = self.conn.get_all_snapshots(filters={'volume-id': volume_ids}) if self.conn else []
            else:
                snapshots = self.conn.get_all_snapshots() if self.conn else []
            instances = self.conn.get_only_instances(instance_ids=instance_ids) if self.conn else []

            for volume in filtered_items:
                status = volume.status
                alarm_status = ''
                attach_status = volume.attach_data.status
                is_root_volume = False
                instance_name = None
                if volume.attach_data is not None and volume.attach_data.instance_id is not None:
                    instance = [inst for inst in instances if inst.id == volume.attach_data.instance_id][0]
                    instance_name = TaggedItemView.get_display_name(instance, escapebraces=False)
                    if instance.root_device_type == 'ebs' and volume.attach_data.device == instance.root_device_name:
                        is_root_volume = True  # Note: Check for 'True' when passed to JS via Chameleon template
                if status != 'deleted':
                    snapshot_name = [snap.tags.get('Name') for snap in snapshots if snap.id == volume.snapshot_id]
                    if len(snapshot_name) == 0:
                        snapshot_name = ''
                    elif snapshot_name[0] is None:
                        snapshot_name = ''
                    else:
                        snapshot_name = snapshot_name[0]
                    if volume.id in alarm_resource_ids:
                        alarm_status = Alarm.get_resource_alarm_status(volume.id, alarms)
                    volumes.append(dict(
                        create_time=volume.create_time,
                        id=volume.id,
                        instance=volume.attach_data.instance_id,
                        device=volume.attach_data.device,
                        instance_name=instance_name,
                        instance_tag_name=instance.tags.get('Name') if instance_name else '',
                        name=TaggedItemView.get_display_name(volume, escapebraces=False),
                        volume_tag_name=volume.tags.get('Name'),
                        snapshots=len([snap.id for snap in snapshots if snap.volume_id == volume.id]),
                        snapshot_id=volume.snapshot_id,
                        snapshot_name=snapshot_name,
                        size=volume.size,
                        status=status,
                        attach_status=attach_status,
                        alarm_status=alarm_status,
                        is_root_volume=is_root_volume,
                        zone=volume.zone,
                        tags=TaggedItemView.get_tags_display(volume.tags),
                        real_tags=volume.tags,
                        transitional=status in transitional_states or attach_status in transitional_states,
                    ))
            return dict(results=volumes)

    def get_items(self, filters=None):
        items = self.conn.get_all_volumes(filters=filters) if self.conn else []
        # because volume status is a combination of status and attach_status, resolve that here
        for item in items:
            if item.status == 'in-use':
                item.status = item.attach_data.status
        return items


class VolumeView(TaggedItemView, BaseVolumeView):
    VIEW_TEMPLATE = '../templates/volumes/volume_view.pt'

    def __init__(self, request, ec2_conn=None, **kwargs):
        super(VolumeView, self).__init__(request, **kwargs)
        name = request.matchdict.get('id')
        if name == 'new':
            name = _(u'Create')
        self.title_parts = [_(u'Volume'), name, _(u'General')]
        self.conn = ec2_conn or self.get_connection()
        self.location = request.route_path('volume_view', id=request.matchdict.get('id'))
        with boto_error_handler(request, self.location):
            self.volume = self.get_volume()
            snapshots = self.conn.get_all_snapshots(owner='self') if self.conn else []
            zones = ChoicesManager(self.conn).get_availability_zones(self.region)
            instances = self.conn.get_only_instances() if self.conn else []
        self.volume_form = VolumeForm(
            self.request, conn=self.conn, volume=self.volume, snapshots=snapshots,
            zones=zones, formdata=self.request.params or None)
        self.delete_form = DeleteVolumeForm(self.request, formdata=self.request.params or None)
        self.attach_form = AttachForm(
            self.request, instances=instances, volume=self.volume, formdata=self.request.params or None)
        self.detach_form = DetachForm(self.request, formdata=self.request.params or None)
        self.tagged_obj = self.volume
        self.attach_data = self.volume.attach_data if self.volume else None
        self.volume_name = self.get_volume_name()
        self.instance_name = None
        is_root_volume = False
        if self.attach_data is not None and self.attach_data.instance_id is not None:
            instance = self.get_instance(self.attach_data.instance_id)
            self.instance_name = TaggedItemView.get_display_name(instance)
            if instance.root_device_type == 'ebs' and self.volume.attach_data.device == instance.root_device_name:
                is_root_volume = True
        self.render_dict = dict(
            volume=self.volume,
            volume_name=self.volume_name,
            instance_name=self.instance_name,
            device_name=self.attach_data.device if self.attach_data else None,
            is_root_volume=is_root_volume,
            attachment_time=self.get_attachment_time(),
            volume_form=self.volume_form,
            delete_form=self.delete_form,
            attach_form=self.attach_form,
            detach_form=self.detach_form,
            controller_options_json=self.get_controller_options_json(),
        )

    @view_config(route_name='volume_view', renderer=VIEW_TEMPLATE, request_method='GET')
    def volume_view(self):
        if self.volume is None and self.request.matchdict.get('id') != 'new':
            raise HTTPNotFound()
        return self.render_dict

    def get_attachment_time(self):
        """Returns volume attach time as a python datetime.datetime object"""
        if self.volume and self.attach_data.attach_time:
            return parser.parse(self.attach_data.attach_time)
        return None

    @view_config(route_name='volume_update', renderer=VIEW_TEMPLATE, request_method='POST')
    def volume_update(self):
        if self.volume and self.volume_form.validate():
            location = self.request.route_path('volume_view', id=self.volume.id)
            with boto_error_handler(self.request, location):
                # Update tags
                self.update_tags()

                # Save Name tag
                name = self.request.params.get('name', '')
                self.update_name_tag(name)

                msg = _(u'Successfully modified volume')
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.volume_form.get_errors_list()
        return self.render_dict

    @view_config(route_name='volume_create', renderer=VIEW_TEMPLATE, request_method='POST')
    def volume_create(self):
        if self.volume_form.validate():
            name = self.request.params.get('name', '')
            tags_json = self.request.params.get('tags')
            size = int(self.request.params.get('size', 1))
            zone = self.request.params.get('zone')
            snapshot_id = self.request.params.get('snapshot_id')
            kwargs = dict(size=size, zone=zone)
            if snapshot_id:
                snapshot = self.get_snapshot(snapshot_id)
                kwargs['snapshot'] = snapshot
            with boto_error_handler(self.request, self.request.route_path('volumes')):
                self.log_request(_(u"Creating volume (size={0}, zone={1}, snapshot_id={2})").format(
                    size, zone, snapshot_id))
                volume = self.conn.create_volume(**kwargs)
                # Add name tag
                if name:
                    volume.add_tag('Name', name)
                if tags_json:
                    tags = json.loads(tags_json)
                    for tagname, tagvalue in tags.items():
                        volume.add_tag(tagname, tagvalue)
                msg = _(u'Successfully sent create volume request.  It may take a moment to create the volume.')
                self.request.session.flash(msg, queue=Notification.SUCCESS)
                location = self.request.route_path('volume_view', id=volume.id)
                return HTTPFound(location=location)
        else:
            self.request.error_messages = self.volume_form.get_errors_list()
        return self.render_dict

    @view_config(route_name='volume_delete', renderer=VIEW_TEMPLATE, request_method='POST')
    def volume_delete(self):
        if self.volume and self.delete_form.validate():
            with boto_error_handler(self.request, self.location):
                self.log_request(_(u"Deleting volume {0}").format(self.volume.id))
                self.volume.delete()
                msg = _(u'Successfully sent delete volume request.  It may take a moment to delete the volume.')
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            location = self.request.route_path('volumes')
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.volume_form.get_errors_list()
        return self.render_dict

    @view_config(route_name='volume_attach', renderer=VIEW_TEMPLATE, request_method='POST')
    def volume_attach(self):
        if self.volume and self.attach_form.validate():
            instance_id = self.request.params.get('instance_id')
            device = self.request.params.get('device')
            with boto_error_handler(self.request, self.location):
                self.log_request(_(u"Attaching volume {0} to {1} as {2}").format(self.volume.id, instance_id, device))
                self.volume.attach(instance_id, device)
                msg = _(u'Successfully sent request to attach volume.  It may take a moment to attach to instance.')
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            location = self.request.route_path('volume_view', id=self.volume.id)
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.volume_form.get_errors_list()
        return self.render_dict

    @view_config(route_name='volume_detach', renderer=VIEW_TEMPLATE, request_method='POST')
    def volume_detach(self):
        if self.detach_form.validate():
            with boto_error_handler(self.request, self.location):
                self.log_request(_(u"Detaching volume {0} from {1}").format(
                    self.volume.id, self.volume.attach_data.instance_id))
                self.volume.detach()
                msg = _(u'Request successfully submitted.  It may take a moment to detach the volume.')
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            location = self.request.route_path('volume_view', id=self.volume.id)
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.volume_form.get_errors_list()
        return self.render_dict

    def get_snapshot(self, snapshot_id):
        snapshots_list = self.conn.get_all_snapshots(snapshot_ids=[snapshot_id])
        return snapshots_list[0] if snapshots_list else None

    def get_instance(self, instance_id):
        if instance_id:
            instances_list = self.conn.get_only_instances(instance_ids=[instance_id])
            return instances_list[0] if instances_list else None
        return None

    def get_volume_name(self):
        if self.volume:
            return TaggedItemView.get_display_name(self.volume)
        return None

    def get_controller_options_json(self):
        if not self.volume:
            return '{}'
        return BaseView.escape_json(json.dumps({
            'volume_status_json_url': self.request.route_path('volume_state_json', id=self.volume.id),
            'volume_status': self.volume.status,
            'attach_status': self.volume.attach_data.status,
        }))


class VolumeStateView(BaseVolumeView):
    def __init__(self, request, ec2_conn=None, **kwargs):
        super(VolumeStateView, self).__init__(request, **kwargs)
        self.request = request
        self.conn = ec2_conn or self.get_connection()
        self.volume = self.get_volume()

    @view_config(route_name='volume_state_json', renderer='json', request_method='GET')
    def volume_state_json(self):
        """Return current volume status"""
        volume_status = self.volume.status if self.volume else 'deleted'
        attach_status = self.volume.attach_data.status if self.volume else 'detached'
        attach_device = self.volume.attach_data.device if self.volume else None
        attach_time = self.volume.attach_data.attach_time if self.volume else None
        attach_instance = self.volume.attach_data.instance_id if self.volume else None
        return dict(
            results=dict(volume_status=volume_status,
                         attach_status=attach_status,
                         attach_device=attach_device,
                         attach_time=attach_time,
                         attach_instance=attach_instance)
        )

    @view_config(route_name='volumes_expando_details', renderer='json', request_method='GET')
    def volume_expando_details(self):
        return self.volume_state_json()


class VolumeSnapshotsView(BaseVolumeView):
    VIEW_TEMPLATE = '../templates/volumes/volume_snapshots.pt'

    def __init__(self, request, ec2_conn=None, **kwargs):
        super(VolumeSnapshotsView, self).__init__(request, **kwargs)
        name = request.matchdict.get('id')
        if name == 'new':
            name = _(u'Create')
        self.title_parts = [_(u'Volume'), name, _(u'Snapshots')]
        self.conn = ec2_conn or self.get_connection()
        self.location = self.request.route_path('volume_snapshots', id=self.request.matchdict.get('id'))
        with boto_error_handler(request, self.location):
            self.volume = self.get_volume()
        self.tagged_obj = self.volume
        self.volume_name = TaggedItemView.get_display_name(self.volume)
        self.add_form = None
        self.create_form = CreateSnapshotForm(self.request, formdata=self.request.params or None)
        self.delete_form = DeleteSnapshotForm(self.request, formdata=self.request.params or None)
        self.register_form = RegisterSnapshotForm(self.request, formdata=self.request.params or None)
        self.render_dict = dict(
            volume=self.volume,
            volume_name=self.volume_name,
            create_form=self.create_form,
            delete_form=self.delete_form,
            register_form=self.register_form,
        )

    @view_config(route_name='volume_snapshots', renderer=VIEW_TEMPLATE, request_method='GET')
    def volume_snapshots(self):
        if self.volume is None:
            raise HTTPNotFound()
        return self.render_dict

    @view_config(route_name='volume_snapshots_json', renderer='json', request_method='GET')
    def volume_snapshots_json(self):
        with boto_error_handler(self.request):
            snapshots = []
            for snapshot in self.volume.snapshots():
                delete_form_action = self.request.route_path(
                    'volume_snapshot_delete', id=self.volume.id, snapshot_id=snapshot.id)
                snapshots.append(dict(
                    id=snapshot.id,
                    name=TaggedItemView.get_display_name(snapshot, escapebraces=False),
                    progress=snapshot.progress,
                    transitional=self.is_transitional(snapshot),
                    volume_size=self.volume.size,
                    start_time=snapshot.start_time,
                    description=snapshot.description,
                    status=snapshot.status,
                    delete_form_action=delete_form_action,
                ))
            return dict(results=snapshots)

    @view_config(route_name='volume_snapshot_create', renderer=VIEW_TEMPLATE, request_method='POST')
    def volume_snapshot_create(self):
        if self.create_form.validate():
            name = self.request.params.get('name')
            description = self.request.params.get('description')
            tags_json = self.request.params.get('tags')
            with boto_error_handler(self.request, self.location):
                self.log_request(_(u"Creating snapshot from volume {0}").format(self.volume.id))
                params = {'VolumeId': self.volume.id}
                if description:
                    params['Description'] = description[0:255]
                snapshot = self.volume.connection.get_object('CreateSnapshot', params, Snapshot, verb='POST')

                # Add name tag
                if name:
                    snapshot.add_tag('Name', name)
                if tags_json:
                    tags = json.loads(tags_json)
                    for tagname, tagvalue in tags.items():
                        snapshot.add_tag(tagname, tagvalue)
                msg = _(u'Successfully sent create snapshot request.  It may take a moment to create the snapshot.')
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            location = self.request.route_path('volume_snapshots', id=self.volume.id)
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.create_form.get_errors_list()
        return self.render_dict

    @view_config(route_name='volume_snapshot_delete', renderer=VIEW_TEMPLATE, request_method='POST')
    def volume_snapshot_delete(self):
        if self.delete_form.validate():
            volume_id = self.request.matchdict.get('id')
            snapshot_id = self.request.matchdict.get('snapshot_id')
            if volume_id and snapshot_id:
                snapshot = self.get_snapshot(snapshot_id)
                with boto_error_handler(self.request, self.location):
                    snapshot.delete()
                    msg = _(u'Successfully deleted the snapshot.')
                    self.request.session.flash(msg, queue=Notification.SUCCESS)
                location = self.request.route_path('volume_snapshots', id=self.volume.id)
                return HTTPFound(location=location)
        return self.render_dict

    def get_snapshot(self, snapshot_id):
        snapshots_list = self.conn.get_all_snapshots(snapshot_ids=[snapshot_id])
        return snapshots_list[0] if snapshots_list else None

    @staticmethod
    def is_transitional(snapshot):
        if snapshot.status.lower() == 'completed':
            return False
        return int(snapshot.progress.replace('%', '')) < 100


class VolumeMonitoringView(BaseVolumeView):
    VIEW_TEMPLATE = '../templates/volumes/volume_monitoring.pt'

    def __init__(self, request):
        super(VolumeMonitoringView, self).__init__(request)
        self.title_parts = [_(u'Volume'), request.matchdict.get('id'), _(u'Monitoring')]
        self.cw_conn = self.get_connection(conn_type='cloudwatch')
        with boto_error_handler(self.request):
            self.volume = self.get_volume()
        self.volume_name = TaggedItemView.get_display_name(self.volume)
        self.monitoring_form = InstanceMonitoringForm(self.request, formdata=self.request.params or None)
        self.instance = None
        attached_instance_id = self.volume.attach_data.instance_id
        monitoring_enabled = False
        if attached_instance_id:
            self.instance = self.get_instance(attached_instance_id)
            if self.instance:
                attached_instance_id = TaggedItemView.get_display_name(self.instance)
                monitoring_enabled = self.instance.monitoring_state == 'enabled'
        self.render_dict = dict(
            volume=self.volume,
            volume_name=self.volume_name,
            attached_instance_id=attached_instance_id,
            monitoring_enabled=monitoring_enabled,
            monitoring_form=self.monitoring_form,
            is_attached=attached_instance_id is not None,
            duration_choices=MONITORING_DURATION_CHOICES,
            statistic_choices=STATISTIC_CHOICES,
            controller_options_json=self.get_controller_options_json()
        )

    @view_config(route_name='volume_monitoring', renderer=VIEW_TEMPLATE, request_method='GET')
    def volume_monitoring(self):
        if self.volume is None:
            raise HTTPNotFound()
        return self.render_dict

    @view_config(route_name='volume_monitoring_update', renderer=VIEW_TEMPLATE, request_method='POST')
    def volume_monitoring_update(self):
        """Update monitoring state for the volume's instance"""
        if self.monitoring_form.validate():
            if self.instance:
                location = self.request.route_path('volume_monitoring', id=self.volume.id)
                with boto_error_handler(self.request, location):
                    monitoring_state = self.instance.monitoring_state
                    action = 'disabled' if monitoring_state == 'enabled' else 'enabled'
                    self.log_request(_(u"Monitoring for instance {0} {1}").format(self.instance.id, action))
                    if monitoring_state == 'disabled':
                        self.conn.monitor_instances([self.instance.id])
                    else:
                        self.conn.unmonitor_instances([self.instance.id])
                    msg = _(
                        u'Request successfully submitted.  It may take a moment for the monitoring status to update.')
                    self.request.session.flash(msg, queue=Notification.SUCCESS)
                return HTTPFound(location=location)

    def get_controller_options_json(self):
        if not self.volume:
            return ''
        return BaseView.escape_json(json.dumps({
            'metric_title_mapping': {},
            'charts_list': VOLUME_MONITORING_CHARTS_LIST,
            'granularity_choices': GRANULARITY_CHOICES,
            'duration_granularities_mapping': DURATION_GRANULARITY_CHOICES_MAPPING,
        }))
