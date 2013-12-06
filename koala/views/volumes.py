# -*- coding: utf-8 -*-
"""
Pyramid views for Eucalyptus and AWS volumes

"""
import time

import simplejson as json

from boto.exception import EC2ResponseError

from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.i18n import TranslationString as _
from pyramid.view import view_config

from ..forms.volumes import VolumeForm, DeleteVolumeForm, CreateSnapshotForm, DeleteSnapshotForm, AttachForm, DetachForm
from ..models import LandingPageFilter, Notification
from ..views import LandingPageView, TaggedItemView, BaseView


class VolumesView(LandingPageView):
    def __init__(self, request):
        super(VolumesView, self).__init__(request)
        self.items = self.get_items()
        self.initial_sort_key = '-create_time'
        self.prefix = '/volumes'

    def get_items(self):
        conn = self.get_connection()
        return conn.get_all_volumes() if conn else []

    @view_config(route_name='volumes', renderer='../templates/volumes/volumes.pt')
    def volumes_landing(self):
        json_items_endpoint = self.request.route_url('volumes_json')
        status_choices = sorted(set(item.status for item in self.items))
        zone_choices = sorted(set(item.zone for item in self.items))
        # Filter fields are passed to 'properties_filter_form' template macro to display filters at left
        self.filter_fields = [
            LandingPageFilter(key='status', name=_(u'Status'), choices=status_choices),
            LandingPageFilter(key='zone', name=_(u'Availability zone'), choices=zone_choices),
            # LandingPageFilter(key='tags', name='Tags'),
        ]
        more_filter_keys = ['attach_status', 'id', 'instance', 'name', 'size', 'snapshot_id', 'create_time', 'tags']
        # filter_keys are passed to client-side filtering in search box
        self.filter_keys = [field.key for field in self.filter_fields] + more_filter_keys
        # sort_keys are passed to sorting drop-down
        self.sort_keys = [
            dict(key='-create_time', name=_(u'Create time')),
            dict(key='name', name=_(u'Name')),
            dict(key='status', name=_(u'Status')),
            dict(key='attach_status', name=_(u'Attach Status')),
            dict(key='zone', name=_(u'Availability zone')),
        ]

        return dict(
            display_type=self.display_type,
            filter_fields=self.filter_fields,
            filter_keys=self.filter_keys,
            sort_keys=self.sort_keys,
            prefix=self.prefix,
            initial_sort_key=self.initial_sort_key,
            json_items_endpoint=json_items_endpoint,
        )

    @view_config(route_name='volumes_json', renderer='json', request_method='GET')
    def volumes_json(self):
        volumes = []
        for volume in self.items:
            volumes.append(dict(
                create_time=volume.create_time,
                id=volume.id,
                instance=volume.attach_data.instance_id,
                name=volume.tags.get('Name', volume.id),
                snapshots=len(volume.snapshots()),
                size=volume.size,
                status=volume.status,
                attach_status=volume.attach_data.status,
                zone=volume.zone,
                tags=TaggedItemView.get_tags_display(volume.tags),
            ))
        return dict(results=volumes)


class VolumeView(TaggedItemView):
    VIEW_TEMPLATE = '../templates/volumes/volume_view.pt'

    def __init__(self, request):
        super(VolumeView, self).__init__(request)
        self.request = request
        self.conn = self.get_connection()
        self.volume = self.get_volume()
        self.volume_form = VolumeForm(
            self.request, volume=self.volume, conn=self.conn, formdata=self.request.params or None)
        self.delete_form = DeleteVolumeForm(self.request, formdata=self.request.params or None)
        self.attach_form = AttachForm(
            self.request, conn=self.conn, volume=self.volume, formdata=self.request.params or None)
        self.detach_form = DetachForm(self.request, formdata=self.request.params or None)
        self.tagged_obj = self.volume
        self.render_dict = dict(
            volume=self.volume,
            volume_form=self.volume_form,
            delete_form=self.delete_form,
            attach_form=self.attach_form,
            detach_form=self.detach_form,
        )

    @view_config(route_name='volume_view', renderer=VIEW_TEMPLATE, request_method='GET')
    def volume_view(self):
        if self.volume is None and self.request.matchdict.get('id') != 'new':
            raise HTTPNotFound
        return self.render_dict

    @view_config(route_name='volume_update', renderer=VIEW_TEMPLATE, request_method='POST')
    def volume_update(self):
        if self.volume and self.volume_form.validate():
            # Update tags
            self.update_tags()

            location = self.request.route_url('volume_view', id=self.volume.id)
            msg = _(u'Successfully modified volume')
            self.request.session.flash(msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)

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
            try:
                volume = self.conn.create_volume(**kwargs)
                # Add name tag
                if name:
                    volume.add_tag('Name', name)
                if tags_json:
                    tags = json.loads(tags_json)
                    for tagname, tagvalue in tags.items():
                        volume.add_tag(tagname, tagvalue)
                msg = _(u'Successfully sent create volume request.  It may take a moment to create the volume.')
                queue = Notification.SUCCESS
                self.request.session.flash(msg, queue=queue)
                location = self.request.route_url('volume_view', id=volume.id)
                return HTTPFound(location=location)
            except EC2ResponseError as err:
                msg = err.message
                queue = Notification.ERROR
                self.request.session.flash(msg, queue=queue)
        return self.render_dict

    @view_config(route_name='volume_delete', renderer=VIEW_TEMPLATE, request_method='POST')
    def volume_delete(self):
        if self.volume and self.delete_form.validate():
            try:
                self.volume.delete()
                time.sleep(1)
                msg = _(u'Successfully sent delete volume request.  It may take a moment to delete the volume.')
                queue = Notification.SUCCESS
            except EC2ResponseError as err:
                msg = err.message.split('remoteDevice')[0]
                queue = Notification.ERROR
            location = self.request.route_url('volume_view', id=self.volume.id)
            self.request.session.flash(msg, queue=queue)
            return HTTPFound(location=location)
        return self.render_dict

    @view_config(route_name='volume_attach', renderer=VIEW_TEMPLATE, request_method='POST')
    def volume_attach(self):
        if self.volume and self.attach_form.validate():
            instance_id = self.request.params.get('instance_id')
            device = self.request.params.get('device')
            try:
                self.volume.attach(instance_id, device)
                time.sleep(1)
                msg = _(u'Successfully sent request to attach volume.  It may take a moment to attach to instance.')
                queue = Notification.SUCCESS
            except EC2ResponseError as err:
                msg = err.message
                queue = Notification.ERROR
            location = self.request.route_url('volume_view', id=self.volume.id)
            self.request.session.flash(msg, queue=queue)
            return HTTPFound(location=location)
        return self.render_dict

    @view_config(route_name='volume_detach', renderer=VIEW_TEMPLATE, request_method='POST')
    def volume_detach(self):
        if self.detach_form.validate():
            try:
                self.volume.detach()
                time.sleep(1)
                msg = _(u'Request successfully submitted.  It may take a moment to detach the volume.')
                queue = Notification.SUCCESS
            except EC2ResponseError as err:
                msg = err.message
                queue = Notification.ERROR
            location = self.request.route_url('volume_view', id=self.volume.id)
            self.request.session.flash(msg, queue=queue)
            return HTTPFound(location=location)
        return self.render_dict

    def get_volume(self):
        volume_id = self.request.matchdict.get('id')
        if volume_id:
            volumes_list = self.conn.get_all_volumes(volume_ids=[volume_id])
            return volumes_list[0] if volumes_list else None
        return None

    def get_snapshot(self, snapshot_id):
        snapshots_list = self.conn.get_all_snapshots(snapshot_ids=[snapshot_id])
        return snapshots_list[0] if snapshots_list else None


class VolumeStateView(BaseView):
    def __init__(self, request):
        super(VolumeStateView, self).__init__(request)
        self.request = request
        self.conn = self.get_connection()
        self.volume = self.get_volume()

    @view_config(route_name='volume_state_json', renderer='json', request_method='GET')
    def volume_state_json(self):
        """Return current volume status"""
        volume_status = self.volume.status
        attach_status = self.volume.attach_data.status
        return dict(
            results=dict(volume_status=volume_status, attach_status=attach_status)
        )

    def get_volume(self):
        volume_id = self.request.matchdict.get('id')
        if volume_id:
            volumes_list = self.conn.get_all_volumes(volume_ids=[volume_id])
            return volumes_list[0] if volumes_list else None
        return None


class VolumeSnapshotsView(BaseView):
    VIEW_TEMPLATE = '../templates/volumes/volume_snapshots.pt'

    def __init__(self, request):
        super(VolumeSnapshotsView, self).__init__(request)
        self.request = request
        self.conn = self.get_connection()
        self.volume = self.get_volume()
        self.add_form = None
        self.create_form = CreateSnapshotForm(self.request, formdata=self.request.params or None)
        self.delete_form = DeleteSnapshotForm(self.request, formdata=self.request.params or None)
        self.render_dict = dict(
            volume=self.volume,
            create_form=self.create_form,
            delete_form=self.delete_form,
        )

    @view_config(route_name='volume_snapshots', renderer=VIEW_TEMPLATE, request_method='GET')
    def volume_snapshots(self):
        if self.volume is None:
            raise HTTPNotFound()
        return self.render_dict

    @view_config(route_name='volume_snapshots_json', renderer='json', request_method='GET')
    def volume_snapshots_json(self):
        snapshots = []
        for snapshot in self.volume.snapshots():
            delete_form_action = self.request.route_url(
                'volume_snapshot_delete', id=self.volume.id, snapshot_id=snapshot.id)
            snapshots.append(dict(
                id=snapshot.id,
                name=snapshot.tags.get('Name', ''),
                progress=snapshot.progress,
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
            description = self.request.params.get('description')
            try:
                self.volume.create_snapshot(description)
                msg = _(u'Successfully sent create snapshot request.  It may take a moment to create the snapshot.')
                queue = Notification.SUCCESS
            except EC2ResponseError as err:
                msg = err.message
                queue = Notification.ERROR
            location = self.request.route_url('volume_snapshots', id=self.volume.id)
            self.request.session.flash(msg, queue=queue)
            return HTTPFound(location=location)
        return self.render_dict

    @view_config(route_name='volume_snapshot_delete', renderer=VIEW_TEMPLATE, request_method='POST')
    def volume_snapshot_delete(self):
        if self.delete_form.validate():
            volume_id = self.request.matchdict.get('id')
            snapshot_id = self.request.matchdict.get('snapshot_id')
            if volume_id and snapshot_id:
                snapshot = self.get_snapshot(snapshot_id)
                try:
                    snapshot.delete()
                    time.sleep(1)
                    msg = _(u'Successfully deleted the snapshot.')
                    queue = Notification.SUCCESS
                except EC2ResponseError as err:
                    msg = err.message
                    queue = Notification.ERROR
                location = self.request.route_url('volume_snapshots', id=self.volume.id)
                self.request.session.flash(msg, queue=queue)
                return HTTPFound(location=location)
        return self.render_dict

    def get_volume(self):
        volume_id = self.request.matchdict.get('id')
        if volume_id:
            volumes_list = self.conn.get_all_volumes(volume_ids=[volume_id])
            return volumes_list[0] if volumes_list else None
        return None

    def get_snapshot(self, snapshot_id):
        snapshots_list = self.conn.get_all_snapshots(snapshot_ids=[snapshot_id])
        return snapshots_list[0] if snapshots_list else None
