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
Pyramid views for Eucalyptus and AWS Roles

"""
from datetime import datetime
from dateutil import parser
import os
import simplejson as json
from urllib import urlencode, quote, unquote

from boto.exception import BotoServerError
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.i18n import TranslationString as _
from pyramid.view import view_config

from ..forms.roles import RoleForm, DeleteRoleForm
from ..models import Notification
from ..views import BaseView, LandingPageView, JSONResponse, TaggedItemView
from . import boto_error_handler


class RolesView(LandingPageView):
    TEMPLATE = '../templates/roles/roles.pt'

    def __init__(self, request):
        super(RolesView, self).__init__(request)
        self.title_parts = [_(u'Roles')]
        self.conn = self.get_connection(conn_type="iam")
        self.initial_sort_key = 'role_name'
        self.prefix = '/roles'
        self.delete_form = DeleteRoleForm(self.request, formdata=self.request.params or None)

    @view_config(route_name='roles', renderer=TEMPLATE)
    def roles_landing(self):
        json_items_endpoint = self.request.route_path('roles_json')
        if self.request.GET:
            json_items_endpoint += u'?{params}'.format(params=urlencode(self.request.GET))
        # filter_keys are passed to client-side filtering in search box
        self.filter_keys = ['path', 'role_name', 'role_id', 'arn']
        # sort_keys are passed to sorting drop-down
        self.sort_keys = [
            dict(key='role_name', name=_(u'Role name: A to Z')),
            dict(key='-role_name', name=_(u'Role name: Z to A')),
        ]

        return dict(
            filter_keys=self.filter_keys,
            search_facets=BaseView.escape_json(json.dumps([])),
            sort_keys=self.sort_keys,
            prefix=self.prefix,
            initial_sort_key=self.initial_sort_key,
            json_items_endpoint=json_items_endpoint,
            delete_form=self.delete_form,
        )

    @view_config(route_name='roles_delete', request_method='POST')
    def roles_delete(self):
        location = self.request.route_path('roles')
        role_name = self.request.params.get('name')
        role = self.conn.get_role(role_name=role_name)
        if role and self.delete_form.validate():
            with boto_error_handler(self.request, location):
                self.log_request(_(u"Deleting role {0}").format(role.role_name))
                profile = RoleView.get_or_create_instance_profile(self.conn, role.role_name)
                self.conn.delete_instance_profile(profile.instance_profile_name)
                self.conn.delete_role(role.role_name)
                msg = _(u'Successfully deleted role')
                self.request.session.flash(msg, queue=Notification.SUCCESS)
        else:
            msg = _(u'Unable to delete role.')  # TODO Pull in form validation error messages here
            self.request.session.flash(msg, queue=Notification.ERROR)
        return HTTPFound(location=location)


class RolesJsonView(BaseView):
    """Roles returned as JSON"""

    def __init__(self, request):
        super(RolesJsonView, self).__init__(request)
        self.conn = self.get_connection(conn_type="iam")

    @view_config(route_name='roles_json', renderer='json', request_method='POST')
    def roles_json(self):
        if not (self.is_csrf_valid()):
            return JSONResponse(status=400, message="missing CSRF token")
        # TODO: take filters into account??
        with boto_error_handler(self.request):
            profiles = self.conn.list_instance_profiles()
            profiles = profiles.list_instance_profiles_response.list_instance_profiles_result.instance_profiles
            roles = []
            for role in self.get_items():
                policies = []
                try:
                    policies = self.conn.list_role_policies(role_name=role.role_name)
                    policies = policies.policy_names
                except BotoServerError:
                    pass
                instances = []
                try:
                    profile_arns = [profile.arn for profile in profiles if
                                    profile.roles and profile.roles.member.role_name == role.role_name]
                    instances = self.get_connection().get_only_instances(
                        filters={'iam-instance-profile.arn': profile_arns})
                except BotoServerError:
                    pass
                """
                user_count = 0
                try:
                    role = self.conn.get_role(role_name=role.role_name)
                    user_count = len(role.users) if hasattr(role, 'users') else 0
                except BotoServerError as exc:
                    pass
                """
                roles.append(dict(
                    path=role.path,
                    role_name=role.role_name,
                    create_date=role.create_date,
                    policy_count=len(policies),
                    instance_count=len(instances),
                ))
            return dict(results=roles)

    def get_items(self):
        with boto_error_handler(self.request):
            return self.conn.list_roles().roles


class RoleView(BaseView):
    """Views for single Role"""
    TEMPLATE = '../templates/roles/role_view.pt'

    def __init__(self, request):
        super(RoleView, self).__init__(request)
        self.title_parts = [_(u'Role'), request.matchdict.get('name') or _(u'Create')]
        self.conn = self.get_connection(conn_type="iam")
        self.role = self.get_role()
        self.role_route_id = self.request.matchdict.get('name')
        self.all_users = self.get_all_users_array()
        self.role_form = RoleForm(self.request, role=self.role, formdata=self.request.params or None)
        self.delete_form = DeleteRoleForm(self.request, formdata=self.request.params)
        create_date = parser.parse(self.role.create_date) if self.role else datetime.now()
        self.role_name_validation_error_msg = _(
            u"Role names must be between 1 and 64 characters long, and may contain letters, numbers, '+', '=', ',', '.'. '@' and '-', and cannot contain spaces.")
        self.render_dict = dict(
            role=self.role,
            role_arn=self.role.arn if self.role else '',
            role_path=self.role.path if self.role else '',
            role_create_date=create_date,
            role_route_id=self.role_route_id,
            all_users=self.all_users,
            role_form=self.role_form,
            delete_form=self.delete_form,
            role_name_validation_error_msg=self.role_name_validation_error_msg,
        )

    def get_role(self):
        role_param = self.request.matchdict.get('name')
        # Return None if the request is to create new role. Prob. No rolename "new" can be created
        if role_param == "new" or role_param is None:
            return None
        role = None
        try:
            role = self.conn.get_role(role_name=role_param)
            role = role.get_role_response.get_role_result.role
        except BotoServerError:
            pass
        return role

    def get_all_users_array(self):
        role_param = self.request.matchdict.get('name')
        if role_param == "new" or role_param is None:
            return []
        users = []
        # Role's path to be used ?
        if self.conn:
            users = [u.user_name.encode('ascii', 'ignore') for u in self.conn.get_all_users().users]
        return users

    @staticmethod
    def _get_trusted_entity_(parsed_policy):
        principal = parsed_policy['Statement'][0]['Principal']
        if 'AWS' in principal.keys():
            arn = principal['AWS']
            if isinstance(arn, list):
                arn = arn[0]
            return _(u'Account ') + arn[arn.rindex('::') + 2:arn.rindex(':')]
        elif 'Service' in principal.keys():
            svc = principal['Service']
            if isinstance(svc, list):
                svc = svc[0]
            return _(u'Service ') + svc
        return ''

    @view_config(route_name='role_view', renderer=TEMPLATE)
    def role_view(self):
        self.render_dict['trusted_entity'] = ''
        self.render_dict['assume_role_policy_document'] = ''
        if self.role is not None:
            # first, prettify the trust doc
            parsed = json.loads(unquote(self.role.assume_role_policy_document))
            self.role.assume_role_policy_document = json.dumps(parsed, indent=2)
            # and pull out the trusted acct id
            self.render_dict['trusted_entity'] = self._get_trusted_entity_(parsed)
            self.render_dict['assume_role_policy_document'] = self.role.assume_role_policy_document
            with boto_error_handler(self.request):
                instances = []
                profiles = self.conn.list_instance_profiles()
                profiles = profiles.list_instance_profiles_response.list_instance_profiles_result.instance_profiles
                profile_arns = [profile.arn for profile in profiles if
                                profile.roles and profile.roles.member.role_name == self.role.role_name]
                instances = self.get_connection().get_only_instances(filters={'iam-instance-profile.arn': profile_arns})
                for instance in instances:
                    instance.name = TaggedItemView.get_display_name(instance)
                self.render_dict['instances'] = instances
        return self.render_dict

    @view_config(route_name='role_create', request_method='POST', renderer=TEMPLATE)
    def role_create(self):
        if self.role_form.validate():
            new_role_name = self.request.params.get('role_name')
            role_type = self.request.params.get('roletype')
            acct_id = ''
            external_id = ''
            if role_type == 'xacct':
                acct_id = self.request.params.get('accountid')
                external_id = self.request.params.get('externalid')
            new_path = self.request.params.get('path')
            err_location = self.request.route_path('roles')
            with boto_error_handler(self.request, err_location):
                self.log_request(_(u"Creating role {0}").format(new_role_name))
                if role_type == 'xacct':
                    policy = {'Version': '2012-10-17'}
                    statement = {'Effect': 'Allow', 'Action': 'sts:AssumeRole',
                                 'Principal': {'AWS': "arn:aws:iam::%s:root" % acct_id}}
                    if len(external_id) > 0:
                        statement['Condition'] = {'StringEquals': {'sts:ExternalId': external_id}}
                    policy['Statement'] = [statement]
                    self.conn.create_role(role_name=new_role_name, path=new_path,
                                          assume_role_policy_document=json.dumps(policy))
                else:
                    self.conn.create_role(role_name=new_role_name, path=new_path)
                # now add instance profile
                RoleView.get_or_create_instance_profile(self.conn, new_role_name)
                msg_template = _(u'Successfully created role {role}')
                msg = msg_template.format(role=new_role_name)
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            location = self.request.route_path('iam_policy_new') + '?type=role&id=' + quote(new_role_name)
            return HTTPFound(location=location)

        return self.render_dict

    @view_config(route_name='role_delete', request_method='POST')
    def role_delete(self):
        if not self.delete_form.validate():
            return JSONResponse(status=400, message="missing CSRF token")
        location = self.request.route_path('roles')
        if self.role is None:
            raise HTTPNotFound()
        with boto_error_handler(self.request, location):
            self.log_request(_(u"Deleting role {0}").format(self.role.role_name))
            profile = RoleView.get_or_create_instance_profile(self.conn, self.role.role_name)
            self.conn.delete_instance_profile(profile.instance_profile_name)
            self.conn.delete_role(self.role.role_name)
            msg = _(u'Successfully deleted role')
            self.request.session.flash(msg, queue=Notification.SUCCESS)
        return HTTPFound(location=location)

    @view_config(route_name='role_policies_json', renderer='json', request_method='GET')
    def role_policies_json(self):
        """Return role policies list"""
        with boto_error_handler(self.request):
            policies = self.conn.list_role_policies(role_name=self.role.role_name)
            return dict(results=policies.policy_names)

    @view_config(route_name='role_policy_json', renderer='json', request_method='GET')
    def role_policy_json(self):
        """Return role policies list"""
        with boto_error_handler(self.request):
            policy_name = self.request.matchdict.get('policy')
            policy = self.conn.get_role_policy(role_name=self.role.role_name, policy_name=policy_name)
            parsed = json.loads(unquote(policy.policy_document))
            return dict(results=json.dumps(parsed, indent=2))

    @view_config(route_name='role_update_policy', request_method='POST', renderer='json')
    def role_update_policy(self):
        if not self.is_csrf_valid():
            return JSONResponse(status=400, message="missing CSRF token")
        # calls iam:PutRolePolicy
        policy = self.request.matchdict.get('policy')
        with boto_error_handler(self.request):
            self.log_request(_(u"Updating policy {0} for role {1}").format(policy, self.role.role_name))
            policy_text = self.request.params.get('policy_text')
            result = self.conn.put_role_policy(
                role_name=self.role.role_name, policy_name=policy, policy_document=policy_text)
            return dict(message=_(u"Successfully updated role policy"), results=result)

    @view_config(route_name='role_update_trustpolicy', request_method='POST', renderer='json')
    def role_update_trustpolicy(self):
        if not self.is_csrf_valid():
            return JSONResponse(status=400, message="missing CSRF token")
        # calls iam:UpdateAssumeRolePolicy
        with boto_error_handler(self.request):
            self.log_request(_(u"Updating trust policy for role {0}").format(self.role.role_name))
            policy_text = self.request.params.get('policy_text')
            result = self.conn.update_assume_role_policy(
                role_name=self.role.role_name, policy_document=policy_text)
            parsed = json.loads(policy_text)
            return dict(message=_(u"Successfully updated trust role policy"), results=result,
                        trusted_entity=self._get_trusted_entity_(parsed))

    @view_config(route_name='role_delete_policy', request_method='POST', renderer='json')
    def role_delete_policy(self):
        if not self.is_csrf_valid():
            return JSONResponse(status=400, message="missing CSRF token")
        # calls iam:DeleteRolePolicy
        policy = self.request.matchdict.get('policy')
        with boto_error_handler(self.request):
            self.log_request(_(u"Deleting policy {0} for role {1}").format(policy, self.role.role_name))
            result = self.conn.delete_role_policy(role_name=self.role.role_name, policy_name=policy)
            return dict(message=_(u"Successfully deleted role policy"), results=result)

    @staticmethod
    def get_or_create_instance_profile(iam_conn, role_name):
        """
        Returns an instance profile either by looking up one that goes with the passes role, or
        by creating a new one an adding the role to it.
        """
        profiles = iam_conn.list_instance_profiles(path_prefix='/' + role_name)
        profiles = profiles.list_instance_profiles_response.list_instance_profiles_result.instance_profiles
        instance_profile = profiles[0] if len(profiles) > 0 else None
        if instance_profile is None:
            profile_name = u'instance_profile_{0}'.format(os.urandom(16).encode('base64').rstrip('=\n'))
            profile_name = "".join(profile_name.split('/'))
            instance_profile = iam_conn.create_instance_profile(profile_name, path='/' + role_name)
            iam_conn.add_role_to_instance_profile(profile_name, role_name)
        return instance_profile
