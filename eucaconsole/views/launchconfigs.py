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
Pyramid views for Eucalyptus and AWS launch configurations

"""
import simplejson as json
from urllib import quote, urlencode

from boto.exception import BotoServerError
from boto.ec2.autoscale.launchconfig import LaunchConfiguration

from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from ..forms import GenerateFileForm
from ..forms.images import ImagesFiltersForm
from ..forms.keypairs import KeyPairForm
from ..forms.launchconfigs import LaunchConfigDeleteForm, CreateLaunchConfigForm, LaunchConfigsFiltersForm
from ..forms.securitygroups import SecurityGroupForm
from ..i18n import _
from ..models import Notification
from ..views import LandingPageView, BaseView, BlockDeviceMappingItemView, JSONResponse
from ..views.images import ImageView
from ..views.roles import RoleView
from ..views.securitygroups import SecurityGroupsView
from . import boto_error_handler
from . import guess_mimetype_from_buffer


class LaunchConfigsView(LandingPageView):
    def __init__(self, request):
        super(LaunchConfigsView, self).__init__(request)
        self.title_parts = [_(u'Launch Configs')]
        self.ec2_conn = self.get_connection()
        self.autoscale_conn = self.get_connection(conn_type='autoscale')
        self.iam_conn = self.get_connection(conn_type="iam")
        self.autoscale_conn = self.get_connection(conn_type='autoscale')
        self.initial_sort_key = 'name'
        self.prefix = '/launchconfigs'
        self.filter_keys = ['image_id', 'image_name', 'key_name', 'name', 'security_groups']
        self.sort_keys = self.get_sort_keys()
        self.json_items_endpoint = self.get_json_endpoint('launchconfigs_json')
        self.delete_form = LaunchConfigDeleteForm(self.request, formdata=self.request.params or None)
        self.filters_form = LaunchConfigsFiltersForm(
            self.request,
            cloud_type=self.cloud_type,
            ec2_conn=self.ec2_conn,
            autoscale_conn=self.autoscale_conn,
            formdata=self.request.params or None
        )
        search_facets = self.filters_form.facets
        self.render_dict = dict(
            filter_keys=self.filter_keys,
            search_facets=BaseView.escape_json(json.dumps(search_facets)),
            sort_keys=self.sort_keys,
            prefix=self.prefix,
            initial_sort_key=self.initial_sort_key,
            json_items_endpoint=self.json_items_endpoint,
            delete_form=self.delete_form,
        )

    @view_config(route_name='launchconfigs', renderer='../templates/launchconfigs/launchconfigs.pt')
    def launchconfigs_landing(self):
        # sort_keys are passed to sorting drop-down
        return self.render_dict

    @view_config(route_name='launchconfigs_delete', request_method='POST')
    def launchconfigs_delete(self):
        if self.delete_form.validate():
            name = self.request.params.get('name')
            location = self.request.route_path('launchconfigs')
            prefix = _(u'Unable to delete launch configuration')
            template = u'{0} {1} - {2}'.format(prefix, name, u'{0}')
            with boto_error_handler(self.request, location, template):
                self.autoscale_conn.delete_launch_configuration(name)
                prefix = _(u'Successfully deleted launch configuration.')
                msg = u'{0} {1}'.format(prefix, name)
                queue = Notification.SUCCESS
                notification_msg = msg
                self.request.session.flash(notification_msg, queue=queue)
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.delete_form.get_errors_list()
        return self.render_dict

    @staticmethod
    def get_sort_keys():
        return [
            dict(key='name', name=_(u'Name: A to Z')),
            dict(key='-name', name=_(u'Name: Z to A')),
            dict(key='created_time', name=_(u'Creation time: Oldest to Newest')),
            dict(key='-created_time', name=_(u'Creation time: Newest to Oldest')),
            dict(key='image_name', name=_(u'Image Name: A to Z')),
            dict(key='-image_name', name=_(u'Image Name: Z to A')),
            dict(key='key_name', name=_(u'Key pair: A to Z')),
            dict(key='-key_name', name=_(u'Key pair: Z to A')),
        ]


class LaunchConfigsJsonView(LandingPageView):
    """JSON response view for Launch Configurations landing page"""
    def __init__(self, request):
        super(LaunchConfigsJsonView, self).__init__(request)
        self.ec2_conn = self.get_connection()
        self.autoscale_conn = self.get_connection(conn_type='autoscale')
        with boto_error_handler(request):
            self.items = self.get_items()
            self.securitygroups = self.get_all_security_groups()
            self.scaling_groups = self.autoscale_conn.get_all_groups()

    @view_config(route_name='launchconfigs_json', renderer='json', request_method='POST')
    def launchconfigs_json(self):
        if not(self.is_csrf_valid()):
            return JSONResponse(status=400, message="missing CSRF token")
        with boto_error_handler(self.request):
            launchconfigs_array = []
            launchconfigs_image_mapping = self.get_launchconfigs_image_mapping()
            scalinggroup_launchconfig_names = self.get_scalinggroups_launchconfig_names()
            launchconfig_sg_mapping = self.get_launchconfigs_sg_mapping()
            for launchconfig in self.filter_items(self.items):
                security_groups = self.get_security_groups(launchconfig.security_groups)
                security_groups_array = sorted({
                    'name': group.name,
                    'id': group.id,
                    'rules_count': self.get_security_group_rules_count_by_id(group.id)
                } for group in security_groups)
                image_id = launchconfig.image_id
                name = launchconfig.name
                image_name = ''
                root_device_type = ''
                image = launchconfigs_image_mapping.get(image_id)
                if image:
                    image_name = image.get('name')
                    root_device_type = image.get('root_device_type')
                launchconfigs_array.append(dict(
                    created_time=self.dt_isoformat(launchconfig.created_time),
                    image_id=image_id,
                    image_name=image_name,
                    instance_type=launchconfig.instance_type,
                    instance_monitoring=launchconfig.instance_monitoring.enabled == 'true',
                    key_name=launchconfig.key_name,
                    name=name,
                    security_groups=security_groups_array,
                    root_device_type=root_device_type,
                    in_use=name in scalinggroup_launchconfig_names,
                    scaling_group=launchconfig_sg_mapping.get(name)
                ))
            return dict(results=launchconfigs_array)

    def get_items(self):
        return self.autoscale_conn.get_all_launch_configurations() if self.autoscale_conn else []

    def get_launchconfigs_image_mapping(self):
        launchconfigs_image_ids = [launchconfig.image_id for launchconfig in self.items]
        launchconfigs_image_ids = list(set(launchconfigs_image_ids))
        try:
            launchconfigs_images = self.ec2_conn.get_all_images(image_ids=launchconfigs_image_ids) if self.ec2_conn else []
        except BotoServerError:
            return dict()
        launchconfigs_image_mapping = dict()
        for image in launchconfigs_images:
            launchconfigs_image_mapping[image.id] = dict(
                name=image.name or image.id,
                root_device_type=image.root_device_type
            )
        return launchconfigs_image_mapping

    def get_scalinggroups_launchconfig_names(self):
        return [group.launch_config_name for group in self.scaling_groups]

    def get_launchconfigs_sg_mapping(self):
        ret = dict()
        for sg in self.scaling_groups:
            ret[sg.launch_config_name] = sg.name
        return ret

    def get_all_security_groups(self):
        if self.ec2_conn:
            return self.ec2_conn.get_all_security_groups()
        return []

    def get_security_groups(self, groupids):
        security_groups = []
        if groupids:
            for id in groupids:
                security_group = ''
                # Due to the issue that AWS-Classic and AWS-VPC different values,
                # name and id, for .securitygroup for launch config object
                if id.startswith('sg-'):
                    security_group = self.get_security_group_by_id(id)
                else:
                    security_group = self.get_security_group_by_name(id)
                if security_group:
                    security_groups.append(security_group)
        return security_groups

    def get_security_group_by_id(self, id):
        if self.securitygroups:
            for sgroup in self.securitygroups:
                if sgroup.id == id:
                    return sgroup
        return ''

    def get_security_group_by_name(self, name):
        if self.securitygroups:
            for sgroup in self.securitygroups:
                if sgroup.name == name:
                    return sgroup
        return ''

    def get_security_group_rules_count_by_id(self, id):
        if id.startswith('sg-'):
            security_group = self.get_security_group_by_id(id)
        else:
            security_group = self.get_security_group_by_name(id)
        if security_group:
            return len(security_group.rules)
        return None


class LaunchConfigView(BaseView):
    """Views for single LaunchConfig"""
    TEMPLATE = '../templates/launchconfigs/launchconfig_view.pt'

    def __init__(self, request):
        super(LaunchConfigView, self).__init__(request)
        self.title_parts = [_(u'Launch Config'), request.matchdict.get('id')]
        self.ec2_conn = self.get_connection()
        self.iam_conn = self.get_connection(conn_type="iam")
        self.autoscale_conn = self.get_connection(conn_type='autoscale')
        with boto_error_handler(request):
            self.launch_config = self.get_launch_config()
            self.image = self.get_image()
            self.security_groups = self.get_security_group_list()
            self.in_use = self.is_in_use()
        self.delete_form = LaunchConfigDeleteForm(self.request, formdata=self.request.params or None)
        self.role = None
        if self.launch_config and self.launch_config.instance_profile_name:
            arn = self.launch_config.instance_profile_name
            try:
                profile_name = arn[(arn.rindex('/') + 1):]
            except ValueError:
                profile_name = arn
            inst_profile = self.iam_conn.get_instance_profile(profile_name)
            self.role = inst_profile.roles.member.role_name

        if self.launch_config.user_data is not None:
            user_data = self.launch_config.user_data
            mime_type = guess_mimetype_from_buffer(user_data, mime=True)
            if mime_type.find('text') == 0:
                self.launch_config.user_data = user_data
            else:
                # get more descriptive text
                mime_type = guess_mimetype_from_buffer(user_data)
                self.launch_config.user_data = None
            self.launch_config.userdata_type = mime_type
            self.launch_config.userdata_istext = True if mime_type.find('text') >= 0 else False
        else:
            self.launch_config.userdata_type = ''
        self.is_vpc_supported = BaseView.is_vpc_supported(request)
        self.render_dict = dict(
            launch_config=self.launch_config,
            launch_config_name=self.escape_braces(self.launch_config.name) if self.launch_config else '',
            launch_config_key_name=self.escape_braces(self.launch_config.key_name) if self.launch_config else '',
            launch_config_vpc_ip_assignment=self.get_vpc_ip_assignment_display(
                self.launch_config.associate_public_ip_address) if self.launch_config else '',
            lc_created_time=self.dt_isoformat(self.launch_config.created_time),
            escaped_launch_config_name=quote(self.launch_config.name.encode('utf-8')),
            in_use=self.in_use,
            image=self.image,
            security_groups=self.security_groups,
            delete_form=self.delete_form,
            role=self.role,
            controller_options_json=self.get_controller_options_json(),
            is_vpc_supported=self.is_vpc_supported,
        )

    @view_config(route_name='launchconfig_view', renderer=TEMPLATE)
    def launchconfig_view(self):
        return self.render_dict

    @view_config(route_name='launchconfig_delete', request_method='POST', renderer=TEMPLATE)
    def launchconfig_delete(self):
        if self.delete_form.validate():
            name = self.request.params.get('name')
            location = self.request.route_path('launchconfigs')
            prefix = _(u'Unable to delete launch configuration')
            template = u'{0} {1} - {2}'.format(prefix, self.launch_config.name, '{0}')
            with boto_error_handler(self.request, location, template):
                self.log_request(_(u"Deleting launch configuration {0}").format(name))
                self.autoscale_conn.delete_launch_configuration(name)
                prefix = _(u'Successfully deleted launch configuration.')
                msg = u'{0} {1}'.format(prefix, name)
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.delete_form.get_errors_list()
        return self.render_dict

    def get_launch_config(self):
        if self.autoscale_conn:
            launch_config_param = self.request.matchdict.get('id')
            launch_configs = self.autoscale_conn.get_all_launch_configurations(names=[launch_config_param])
            return launch_configs[0] if launch_configs else None
        return None

    def get_image(self):
        if self.ec2_conn:
            try:
                images = self.ec2_conn.get_all_images(image_ids=[self.launch_config.image_id])
            except BotoServerError:
                return None
            image = images[0] if images else None
            if image is None:
                return None
            image.platform = ImageView.get_platform(image)
            return image
        return None

    def get_security_groups(self):
        if self.ec2_conn:
            groupids = self.launch_config.security_groups
            security_groups = []
            if groupids:
                if groupids[0].startswith('sg-'):
                    security_groups = self.ec2_conn.get_all_security_groups(filters={'group-id': groupids})
                else:
                    security_groups = self.ec2_conn.get_all_security_groups(filters={'group-name': groupids})
            return security_groups
        return []

    def get_securitygroups_rules(self, securitygroups):
        rules_dict = {}
        for security_group in securitygroups:
            rules = SecurityGroupsView.get_rules(security_group.rules)
            if security_group.vpc_id is not None:
                rules_egress = SecurityGroupsView.get_rules(security_group.rules_egress, rule_type='outbound')
                rules = rules + rules_egress
            rules_dict[security_group.id] = rules
        return rules_dict

    def get_security_group_list(self):
        security_groups = []
        security_group_list = []
        security_groups = self.get_security_groups()
        if security_groups:
            rules_dict = self.get_securitygroups_rules(security_groups)
            for sgroup in security_groups:
                rules = rules_dict[sgroup.id]
                sgroup_dict = {}
                sgroup_dict['id'] = sgroup.id
                sgroup_dict['name'] = sgroup.name
                sgroup_dict['rules'] = rules
                sgroup_dict['rule_count'] = len(rules)
                security_group_list.append(sgroup_dict)
        return security_group_list

    def is_in_use(self):
        """Returns whether or not the launch config is in use (i.e. in any scaling group).
        :rtype: Boolean
        """
        launch_configs = []
        if self.autoscale_conn:
            launch_configs = [group.launch_config_name for group in self.autoscale_conn.get_all_groups()]
        return self.launch_config.name in launch_configs

    @staticmethod
    def get_vpc_ip_assignment_display(value):
        choices = [
            ('None', _(u'Only for instances in default VPC & subnet')),
            ('True', _(u'For all instances')),
            ('False', _(u'Never'))
        ]
        for choice in choices:
            if choice[0] == str(value):
                return choice[1]
        return ''

    def get_controller_options_json(self):
        return BaseView.escape_json(json.dumps({
            'in_use': self.in_use,
            'has_image': True if self.image else False,
        }))


class CreateLaunchConfigView(BlockDeviceMappingItemView):
    """Create Launch Configuration wizard"""
    TEMPLATE = '../templates/launchconfigs/launchconfig_wizard.pt'

    def __init__(self, request):
        super(CreateLaunchConfigView, self).__init__(request)
        self.title_parts = [_(u'Launch Config'), _(u'Create')]
        self.image = self.get_image()
        with boto_error_handler(request):
            self.securitygroups = self.get_security_groups()
        self.iam_conn = None
        if BaseView.has_role_access(request):
            self.iam_conn = self.get_connection(conn_type="iam")
        self.vpc_conn = self.get_connection(conn_type='vpc')
        self.create_form = CreateLaunchConfigForm(
            self.request, image=self.image, conn=self.conn, iam_conn=self.iam_conn,
            securitygroups=self.securitygroups, formdata=self.request.params or None)
        self.filters_form = ImagesFiltersForm(
            self.request, cloud_type=self.cloud_type, formdata=self.request.params or None)
        self.keypair_form = KeyPairForm(self.request, formdata=self.request.params or None)
        self.securitygroup_form = SecurityGroupForm(self.request, self.vpc_conn, formdata=self.request.params or None)
        self.generate_file_form = GenerateFileForm(self.request, formdata=self.request.params or None)
        self.owner_choices = self.get_owner_choices()

        controller_options_json = BaseView.escape_json(json.dumps({
            'securitygroups_choices': dict(self.create_form.securitygroup.choices),
            'keypair_choices': dict(self.create_form.keypair.choices),
            'role_choices': dict(self.create_form.role.choices),
            'securitygroups_json_endpoint': self.request.route_path('securitygroups_json'),
            'securitygroups_rules_json_endpoint': self.request.route_path('securitygroups_rules_json'),
            'image_json_endpoint': self.request.route_path('image_json', id='_id_'),
            'default_vpc_network': self.get_default_vpc_network(),
        }))
        self.is_vpc_supported = BaseView.is_vpc_supported(request)
        self.render_dict = dict(
            image=self.image,
            create_form=self.create_form,
            filters_form=self.filters_form,
            keypair_form=self.keypair_form,
            securitygroup_form=self.securitygroup_form,
            generate_file_form=self.generate_file_form,
            owner_choices=self.owner_choices,
            snapshot_choices=self.get_snapshot_choices(),
            preset='',
            security_group_placeholder_text=_(u'Select...'),
            controller_options_json=controller_options_json,
            is_vpc_supported=self.is_vpc_supported,
        )

    @view_config(route_name='launchconfig_new', renderer=TEMPLATE, request_method='GET')
    def launchconfig_new(self):
        """Displays the Create Launch Configuration wizard"""
        self.render_dict['preset'] = self.request.params.get('preset')
        return self.render_dict

    @view_config(route_name='launchconfig_create', renderer=TEMPLATE, request_method='POST')
    def launchconfig_create(self):
        """Handles the POST from the Create Launch Configuration wizard"""
        if self.create_form.validate():
            autoscale_conn = self.get_connection(conn_type='autoscale')
            location = self.request.route_path('launchconfigs')
            image_id = self.image.id
            name = self.request.params.get('name')
            key_name = self.unescape_braces(self.request.params.get('keypair', ''))
            if key_name:
                # Handle "None (advanced)" option if key_name is 'none'
                key_name = None if key_name == 'none' else self.unescape_braces(key_name)
            security_groups = self.request.params.getall('securitygroup')
            instance_type = self.request.params.get('instance_type', 'm1.small')
            associate_public_ip_address = self.request.params.get('associate_public_ip_address') or None
            # associate_public_ip_address's value can be 'None', True, or False for VPC systems
            # in case of no VPC system, the value os assciate_public_ip_address should be kept None
            if self.is_vpc_supported and associate_public_ip_address != 'None':
                associate_public_ip_address = True if associate_public_ip_address == 'true' else False
            kernel_id = self.request.params.get('kernel_id') or None
            ramdisk_id = self.request.params.get('ramdisk_id') or None
            monitoring_enabled = self.request.params.get('monitoring_enabled') == 'y'
            bdmapping_json = self.request.params.get('block_device_mapping')
            block_device_mappings = [self.get_block_device_map(bdmapping_json)] if bdmapping_json != '{}' else None
            role = self.request.params.get('role')
            with boto_error_handler(self.request, location):
                instance_profile = None
                if role != '':  # need to set up instance profile, add role and supply to run_instances
                    instance_profile = RoleView.get_or_create_instance_profile(self.iam_conn, role)
                self.log_request(_(u"Creating launch configuration {0}").format(name))
                launch_config = LaunchConfiguration(
                    name=name,
                    image_id=image_id,
                    key_name=key_name,
                    security_groups=security_groups,
                    user_data=self.get_user_data(),
                    instance_type=instance_type,
                    associate_public_ip_address=associate_public_ip_address,
                    kernel_id=kernel_id,
                    ramdisk_id=ramdisk_id,
                    block_device_mappings=block_device_mappings,
                    instance_monitoring=monitoring_enabled,
                    instance_profile_name=instance_profile.arn if instance_profile else None
                )
                autoscale_conn.create_launch_configuration(launch_config=launch_config)
                msg = _(u'Successfully sent create launch configuration request. '
                        u'It may take a moment to create the launch configuration.')
                queue = Notification.SUCCESS
                self.request.session.flash(msg, queue=queue)

            if self.request.params.get('create_sg_from_lc') == 'y':
                location = u'{0}?{1}'.format(
                    self.request.route_path('scalinggroup_new'),
                    urlencode(self.encode_unicode_dict({'launch_config': name}))
                )
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.create_form.get_errors_list()
        return self.render_dict

    def get_security_groups(self):
        if self.conn:
            return self.conn.get_all_security_groups()
        return []

    def get_securitygroups_rules(self):
        rules_dict = {}
        for security_group in self.securitygroups:
            rules = SecurityGroupsView.get_rules(security_group.rules)
            if security_group.vpc_id is not None:
                rules_egress = SecurityGroupsView.get_rules(security_group.rules_egress, rule_type='outbound')
                rules = rules + rules_egress
            rules_dict[security_group.id] = rules
        return rules_dict

    def get_default_vpc_network(self):
        default_vpc = self.request.session.get('default_vpc', [])
        if self.is_vpc_supported:
            if 'none' in default_vpc or 'None' in default_vpc:
                if self.cloud_type == 'aws':
                    return 'None'
                # for euca, return the first vpc on the list
                if self.vpc_conn:
                    with boto_error_handler(self.request):
                        vpc_networks = self.vpc_conn.get_all_vpcs()
                        if vpc_networks:
                            return vpc_networks[0].id
            else:
                return default_vpc[0]
        return 'None'


class CreateMoreLaunchConfigView(BlockDeviceMappingItemView):
    """Create another Launch Configuration like this one"""
    TEMPLATE = '../templates/launchconfigs/launchconfig_create_more.pt'

    def __init__(self, request):
        super(CreateMoreLaunchConfigView, self).__init__(request)
        self.request = request
        self.iam_conn = None
        if BaseView.has_role_access(request):
            self.iam_conn = self.get_connection(conn_type="iam")
        self.vpc_conn = self.get_connection(conn_type='vpc')
        autoscale_conn = self.get_connection(conn_type='autoscale')
        name = self.request.matchdict.get('id')
        with boto_error_handler(request):
            lc = autoscale_conn.get_all_launch_configurations(names=[name])
            launch_config = lc[0]
            images = self.get_connection().get_all_images(image_ids=[launch_config.image_id])
            self.image = images[0] if images else None
            self.image.platform_name = ImageView.get_platform(self.image)[2]

        self.create_form = CreateLaunchConfigForm(
            self.request, image=self.image, conn=self.conn, iam_conn=self.iam_conn,
            keyname=launch_config.key_name,
            formdata=self.request.params or None)
        self.create_form.image_id.data = launch_config.image_id
        self.create_form.instance_type.data = launch_config.instance_type
        self.create_form.securitygroup.data = launch_config.security_groups
        self.filters_form = ImagesFiltersForm(
            self.request, cloud_type=self.cloud_type, formdata=self.request.params or None)
        self.keypair_form = KeyPairForm(self.request, formdata=self.request.params or None)
        self.securitygroup_form = SecurityGroupForm(self.request, self.vpc_conn, formdata=self.request.params or None)
        self.generate_file_form = GenerateFileForm(self.request, formdata=self.request.params or None)
        self.owner_choices = self.get_owner_choices()

        if launch_config.user_data is not None and launch_config.user_data != '':
            user_data = launch_config.user_data
            mime_type = guess_mimetype_from_buffer(user_data, mime=True)
        else:
            user_data = ''
            mime_type = ''

        controller_options_json = BaseView.escape_json(json.dumps({
            'user_data': dict(type=mime_type, data=user_data)
        }))
        self.is_vpc_supported = BaseView.is_vpc_supported(request)

        self.render_dict = dict(
            image=self.image,
            launch_config=launch_config,
            launchconfig_name=launch_config.name,
            create_form=self.create_form,
            filters_form=self.filters_form,
            keypair_form=self.keypair_form,
            securitygroup_form=self.securitygroup_form,
            generate_file_form=self.generate_file_form,
            owner_choices=self.owner_choices,
            snapshot_choices=self.get_snapshot_choices(),
            preset='',
            security_group_placeholder_text=_(u'Select...'),
            controller_options_json=controller_options_json,
            is_vpc_supported=self.is_vpc_supported,
        )

    @view_config(route_name='launchconfig_more', renderer=TEMPLATE, request_method='GET')
    def launchconfig_more(self):
        return self.render_dict

