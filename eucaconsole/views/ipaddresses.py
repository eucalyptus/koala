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
Pyramid views for Eucalyptus and AWS Elastic IP Addresses

"""
import simplejson as json

from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from ..forms.ipaddresses import (
    AllocateIPsForm, AssociateIPForm, DisassociateIPForm, ReleaseIPForm, IPAddressesFiltersForm)
from ..i18n import _
from ..models import Notification
from ..views import LandingPageView, TaggedItemView, BaseView, JSONResponse
from . import boto_error_handler


class IPAddressesView(LandingPageView):
    """Views for IP Addresses landing page"""
    VIEW_TEMPLATE = '../templates/ipaddresses/ipaddresses.pt'

    def __init__(self, request):
        super(IPAddressesView, self).__init__(request)
        self.title_parts = [_(u'IP Addresses')]
        self.prefix = '/ipaddresses'
        self.conn = self.get_connection()
        self.location = self.get_redirect_location('ipaddresses')
        self.allocate_form = AllocateIPsForm(self.request, formdata=self.request.params or None)
        with boto_error_handler(self.request, self.location):
            self.associate_form = AssociateIPForm(self.request, conn=self.conn, formdata=self.request.params or None)
            self.disassociate_form = DisassociateIPForm(self.request, formdata=self.request.params or None)
        self.release_form = ReleaseIPForm(self.request, formdata=self.request.params or None)
        self.is_vpc_supported = BaseView.is_vpc_supported(request)
        self.render_dict = dict(
            prefix=self.prefix,
            allocate_form=self.allocate_form,
            associate_form=self.associate_form,
            disassociate_form=self.disassociate_form,
            release_form=self.release_form,
            allocate_ip_dialog_error_message=_(u'Please enter a whole number greater than zero'),
            is_vpc_supported=self.is_vpc_supported,
            cloud_type=self.cloud_type,
        )

    @view_config(route_name='ipaddresses', renderer=VIEW_TEMPLATE)
    def ipaddresses_landing(self):
        # sort_keys are passed to sorting drop-down
        # Handle Allocate IP addresses form
        if self.request.method == 'POST':
            if self.cloud_type == 'euca':
                del self.allocate_form.domain 
            if self.allocate_form.validate():
                new_ips = []
                domain = self.request.params.get('domain') or None
                ipcount = int(self.request.params.get('ipcount', 0))
                with boto_error_handler(self.request, self.location):
                    self.log_request(_(u"Allocating {0} Elastic IPs").format(ipcount))
                    for i in xrange(ipcount):
                        new_ip = self.conn.allocate_address(domain=domain)
                        new_ips.append(new_ip.public_ip)
                    prefix = _(u'Successfully allocated IPs')
                    ips = ', '.join(new_ips)
                    msg = u'{prefix} {ips}'.format(prefix=prefix, ips=ips)
                    self.request.session.flash(msg, queue=Notification.SUCCESS)
                return HTTPFound(location=self.location)
        filters_form = IPAddressesFiltersForm(self.request, conn=self.conn, formdata=self.request.params or None)
        if self.cloud_type == 'euca':
            del filters_form.domain
        search_facets = filters_form.facets
        self.render_dict.update(
            initial_sort_key='public_ip',
            json_items_endpoint=self.get_json_endpoint('ipaddresses_json'),
            filters_form=filters_form,
            filter_keys=['public_ip', 'instance_id', 'domain'],
            search_facets=BaseView.escape_json(json.dumps(search_facets)),
            sort_keys=self.get_sort_keys(),
        )
        return self.render_dict

    @view_config(route_name='ipaddresses_associate', request_method="POST")
    def ipaddresses_associate(self):
        if self.associate_form.validate():
            instance_id = self.request.params.get('instance_id')
            public_ip = self.request.params.get('public_ip')
            with boto_error_handler(self.request, self.location):
                self.log_request(_(u"Associating Elastic IP {0} with instance {1}").format(public_ip, instance_id))
                elastic_ip = self.get_elastic_ip(public_ip)
                elastic_ip.associate(instance_id)
                template = _(u'Successfully associated IP {ip} with instance {instance}')
                msg = template.format(ip=elastic_ip.public_ip, instance=instance_id)
                self.request.session.flash(msg, queue=Notification.SUCCESS)
        else:
            msg = _(u'Unable to associate IP with instance')
            self.request.session.flash(msg, queue=Notification.ERROR)
        return HTTPFound(location=self.location)

    @view_config(route_name='ipaddresses_disassociate', request_method="POST")
    def ipaddresses_disassociate(self):
        if self.disassociate_form.validate():
            public_ip_param = self.request.params.get('public_ip')
            public_ips = public_ip_param.split(', ')
            instance_id_param = self.request.params.get('instance_id')
            instance_ids = instance_id_param.split(', ')
            with boto_error_handler(self.request, self.location):
                for idx, public_ip in enumerate(public_ips):
                    self.log_request(_(u"Disassociating Elastic IP {0} from instance {1}").format(
                        public_ip, instance_ids[idx]))
                    elastic_ip = self.get_elastic_ip(public_ip)
                    elastic_ip.disassociate()
                    template = _(u'Successfully disassociated IP {ip} from instance {instance}')
                    msg = template.format(ip=public_ip_param, instance=instance_id_param)
                    self.request.session.flash(msg, queue=Notification.SUCCESS)
        else:
            msg = _(u'Unable to disassociate IP from instance')
            self.request.session.flash(msg, queue=Notification.ERROR)
        return HTTPFound(location=self.location)

    @view_config(route_name='ipaddresses_release', request_method="POST")
    def ipaddresses_release(self):
        if self.release_form.validate():
            public_ip_param = self.request.params.get('public_ip')
            public_ips = public_ip_param.split(', ')
            allocation_id = self.request.params.get('allocation_id')
            with boto_error_handler(self.request, self.location):
                self.log_request(_(u"Releasing Elastic IP(s) {0}").format(public_ip_param))
                if allocation_id == '':
                    for public_ip in public_ips:
                        self.conn.release_address(public_ip=public_ip.strip())
                else:
                    self.conn.release_address(allocation_id=allocation_id)
                template = _(u'Successfully released {ip} to the cloud')
                msg = template.format(ip=public_ip_param)
                self.request.session.flash(msg, queue=Notification.SUCCESS)
        else:
            msg = _(u'Unable to release IP address')
            self.request.session.flash(msg, queue=Notification.ERROR)
        return HTTPFound(location=self.location)

    def get_elastic_ip(self, public_ip):
        addresses_param = [public_ip]
        ip_addresses = self.conn.get_all_addresses(addresses=addresses_param)
        elastic_ip = ip_addresses[0] if ip_addresses else None
        return elastic_ip

    @staticmethod
    def get_sort_keys():
        """sort_keys are passed to sorting drop-down on landing page"""
        return [
            dict(key='public_ip', name=_(u'IP Address')),
            dict(key='instance_id', name=_(u'Instance')),
        ]


class IPAddressesJsonView(LandingPageView):
    def __init__(self, request):
        super(IPAddressesJsonView, self).__init__(request)
        self.conn = self.get_connection()

    @view_config(route_name='ipaddresses_json', renderer='json', request_method='POST')
    def ipaddresses_json(self):
        if not(self.is_csrf_valid()):
            return JSONResponse(status=400, message="missing CSRF token")
        ipaddresses = []
        with boto_error_handler(self.request):
            items = self.filter_items(self.get_items(), ignore=['assignment', 'allocate'])
            if self.request.params.getall('assignment'):
                items = self.filter_by_assignment(items)
            instances = self.get_instances(items)
            for address in items:
                ipaddresses.append(dict(
                    public_ip=address.public_ip,
                    allocation_id=address.allocation_id,
                    instance_id=address.instance_id,
                    instance_name=TaggedItemView.get_display_name(
                        instances[address.instance_id]) if address.instance_id in instances else address.instance_id,
                    domain=address.domain,
                ))
            return dict(results=ipaddresses)

    def get_items(self):
        return self.conn.get_all_addresses() if self.conn else []

    # return dictionary of instances (by their id)
    def get_instances(self, ipaddresses):
        ids = []
        for ip in ipaddresses:
            if ip.instance_id:
                ids.append(ip.instance_id)
        instances = self.conn.get_only_instances(ids)
        ret = {}
        for inst in instances:
            ret[inst.id] = inst
        return ret

    def filter_by_assignment(self, items):
        filtered_items = []
        for item in items:
            for assignment in self.request.params.getall('assignment'):
                if (assignment and item.instance_id) or (not assignment and not item.instance_id):
                    filtered_items.append(item)
        return filtered_items


class IPAddressView(BaseView):
    """Views for actions on single IP Address"""
    VIEW_TEMPLATE = '../templates/ipaddresses/ipaddress_view.pt'

    def __init__(self, request):
        super(IPAddressView, self).__init__(request)
        self.title_parts = [_(u'IP Addresses'), request.matchdict.get('public_ip')]
        self.conn = self.get_connection()
        self.elastic_ip = self.get_elastic_ip()
        self.instance = self.get_instance()
        self.associate_form = AssociateIPForm(self.request, conn=self.conn, formdata=self.request.params or None)
        self.disassociate_form = DisassociateIPForm(self.request, formdata=self.request.params or None)
        self.release_form = ReleaseIPForm(self.request, formdata=self.request.params or None)
        if self.elastic_ip:
            self.elastic_ip.instance_name = ''
            if self.instance:
                self.elastic_ip.instance_name = TaggedItemView.get_display_name(self.instance)
        self.render_dict = dict(
            eip=self.elastic_ip,
            associate_form=self.associate_form,
            disassociate_form=self.disassociate_form,
            release_form=self.release_form,
        )

    @view_config(route_name='ipaddress_view', renderer=VIEW_TEMPLATE)
    def ipaddress_view(self):
        return self.render_dict

    @view_config(route_name='ipaddress_associate', request_method="POST")
    def ipaddress_associate(self):
        if self.associate_form.validate():
            instance_id = self.request.params.get('instance_id')
            location = self.request.route_path('ipaddresses')
            with boto_error_handler(self.request, location):
                self.log_request(_(u"Associating Elastic IP {0} with instance {1}").format(self.elastic_ip, instance_id))
                self.elastic_ip.associate(instance_id)
                msg = _(u'Successfully associated IP {ip} with instance {instance}')
                notification_msg = msg.format(ip=self.elastic_ip.public_ip, instance=instance_id)
                self.request.session.flash(notification_msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)
        return self.render_dict

    @view_config(route_name='ipaddress_disassociate', renderer=VIEW_TEMPLATE, request_method="POST")
    def ipaddress_disassociate(self):
        if self.disassociate_form.validate():
            location = self.request.route_path('ipaddresses')
            with boto_error_handler(self.request, location):
                self.log_request(_(u"Disassociating Elastic IP {0} from instance {1}").format(
                    self.elastic_ip, getattr(self.elastic_ip, 'instance_name', '')))
                self.elastic_ip.disassociate()
                msg = _(u'Successfully disassociated IP {ip} from instance {instance}')
                notification_msg = msg.format(ip=self.elastic_ip.public_ip, instance=self.elastic_ip.instance_id)
                self.request.session.flash(notification_msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)
        return self.render_dict

    @view_config(route_name='ipaddress_release', renderer=VIEW_TEMPLATE, request_method="POST")
    def ipaddress_release(self):
        if self.release_form.validate():
            location = self.request.route_path('ipaddresses')
            with boto_error_handler(self.request, location):
                self.log_request(_(u"Releasing Elastic IP {0}").format(self.elastic_ip))
                self.elastic_ip.release()
                msg = _(u'Successfully released {ip} to the cloud')
                notification_msg = msg.format(ip=self.elastic_ip.public_ip)
                self.request.session.flash(notification_msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)
        return self.render_dict

    def get_elastic_ip(self):
        address_param = self.request.matchdict.get('public_ip')
        addresses_param = [address_param]
        ip_addresses = []
        elastic_ip = None
        if self.conn:
            ip_addresses = self.conn.get_all_addresses(addresses=addresses_param)
        elastic_ip = ip_addresses[0] if ip_addresses else None
        return elastic_ip

    def get_instance(self):
        if self.elastic_ip and self.elastic_ip.instance_id:
            instances = self.conn.get_only_instances(instance_ids=[self.elastic_ip.instance_id])
            return instances[0] if instances else None
        return None
