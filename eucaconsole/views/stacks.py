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
Pyramid views for Eucalyptus and AWS CloudFormation stacks

"""
from urllib import quote
import simplejson as json

from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from ..i18n import _
from ..forms.stacks import StacksDeleteForm, StacksFiltersForm, StacksCreateForm
from ..models import Notification
from ..views import LandingPageView, BaseView, JSONResponse
from . import boto_error_handler


class StacksView(LandingPageView):
    def __init__(self, request):
        super(StacksView, self).__init__(request)
        self.request = request
        self.cloudformation_conn = self.get_connection(conn_type="cloudformation")
        self.initial_sort_key = 'name'
        self.prefix = '/stacks'
        self.filter_keys = ['name', 'create-time']
        self.sort_keys = self.get_sort_keys()
        self.json_items_endpoint = self.get_json_endpoint('stacks_json')
        self.delete_form = StacksDeleteForm(self.request, formdata=self.request.params or None)
        self.filters_form = StacksFiltersForm(
            self.request, cloud_type=self.cloud_type, formdata=self.request.params or None)
        search_facets = self.filters_form.facets
        self.render_dict = dict(
            filter_fields=False,
            filter_keys=self.filter_keys,
            search_facets=BaseView.escape_json(json.dumps(search_facets)),
            sort_keys=self.sort_keys,
            prefix=self.prefix,
            initial_sort_key=self.initial_sort_key,
            json_items_endpoint=self.json_items_endpoint,
            delete_form=self.delete_form,
        )

    @view_config(route_name='stacks', renderer='../templates/stacks/stacks.pt')
    def stacks_landing(self):
        # sort_keys are passed to sorting drop-down
        return self.render_dict

    @view_config(route_name='stacks_delete', request_method='POST')
    def stacks_delete(self):
        if self.delete_form.validate():
            name = self.request.params.get('name')
            location = self.request.route_path('stacks')
            prefix = _(u'Unable to delete stack')
            template = u'{0} {1} - {2}'.format(prefix, name, '{0}')
            with boto_error_handler(self.request, location, template):
                self.cloudformation_conn.delete_stack(name)
                prefix = _(u'Successfully deleted stack.')
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
            dict(key='creation_time', name=_(u'Creation time: Oldest to Newest')),
            dict(key='-creation_time', name=_(u'Creation time: Newest to Oldest')),
        ]


class StacksJsonView(LandingPageView):
    """JSON response view for Stack landing page"""
    def __init__(self, request):
        super(StacksJsonView, self).__init__(request)
        self.cloudformation_conn = self.get_connection(conn_type="cloudformation")
        with boto_error_handler(request):
            self.items = self.get_items()

    @view_config(route_name='stacks_json', renderer='json', request_method='POST')
    def stacks_json(self):
        if not(self.is_csrf_valid()):
            return JSONResponse(status=400, message="missing CSRF token")
        transitional_states = ['CREATE_IN_PROGRESS', 'ROLLBACK_IN_PROGRESS', 'DELETE_IN_PROGRESS']
        with boto_error_handler(self.request):
            stacks_array = []
            for stack in self.filter_items(self.items):
                is_transitional = stack.stack_status in transitional_states
                name = stack.stack_name
                status = stack.stack_status
                stacks_array.append(dict(
                    creation_time=self.dt_isoformat(stack.creation_time),
                    status=status.lower().replace('_', '-'),
                    description=stack.description,
                    name=name,
                    transitional=is_transitional,
                ))
            return dict(results=stacks_array)

    def get_items(self):
        return self.cloudformation_conn.describe_stacks() if self.cloudformation_conn else []


class StackView(BaseView):
    """Views for single stack"""
    TEMPLATE = '../templates/stacks/stack_view.pt'

    def __init__(self, request):
        super(StackView, self).__init__(request)
        self.cloudformation_conn = self.get_connection(conn_type='cloudformation')
        with boto_error_handler(request):
            self.stack = self.get_stack()
        self.delete_form = StacksDeleteForm(self.request, formdata=self.request.params or None)
        search_facets = [
            {'name':'status', 'label':_(u"Status"), 'options': [
                {'key':'create-complete', 'label':_("Create Complete")},
                {'key':'create-in-progress', 'label':_("Create In Progresss")},
                {'key':'create-failed', 'label':_("Create Failed")},
                {'key':'delete-complete', 'label':_("Delete Complete")},
                {'key':'delete-in-progress', 'label':_("Delete In Progresss")},
                {'key':'delete-failed', 'label':_("Delete Failed")},
                {'key':'rollback-complete', 'label':_("Rollback Complete")},
                {'key':'rollback-in-progress', 'label':_("Rollback In Progresss")},
                {'key':'rollback-failed', 'label':_("Rollback Failed")}
            ]},
            {'name':'phys-id', 'label':_(u"Physical ID")}
        ];
        self.render_dict = dict(
            stack=self.stack,
            stack_name=self.escape_braces(self.stack.stack_name) if self.stack else '',
            stack_id=self.stack.stack_id if self.stack else '',
            stack_creation_time=self.dt_isoformat(self.stack.creation_time),
            status=self.stack.stack_status.lower().replace('_', '-'),
            delete_form=self.delete_form,
            in_use=False,
            search_facets=BaseView.escape_json(json.dumps(search_facets)),
            filter_keys=[],
            controller_options_json=self.get_controller_options_json(),
        )

    @view_config(route_name='stack_view', renderer=TEMPLATE)
    def stack_view(self):
        return self.render_dict
 
    @view_config(route_name='stack_delete', request_method='POST', renderer=TEMPLATE)
    def stack_delete(self):
        if self.delete_form.validate():
            name = self.request.params.get('name')
            location = self.request.route_path('stacks')
            prefix = _(u'Unable to delete stack')
            template = u'{0} {1} - {2}'.format(prefix, self.stack.stack_name, '{0}')
            with boto_error_handler(self.request, location, template):
                msg = _(u"Deleting stack")
                self.log_request(u"{0} {1}".format(msg, name))
                self.cloudformation_conn.delete_stack(name)
                prefix = _(u'Successfully deleted stack.')
                msg = u'{0} {1}'.format(prefix, name)
                self.request.session.flash(msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)
        else:
            self.request.error_messages = self.delete_form.get_errors_list()
        return self.render_dict

    def get_stack(self):
        if self.cloudformation_conn:
            stack_param = self.request.matchdict.get('name')
            stacks = self.cloudformation_conn.describe_stacks(stack_name_or_id=stack_param)
            return stacks[0] if stacks else None
        return None

    def get_controller_options_json(self):
        return BaseView.escape_json(json.dumps({
            'stack_name': self.stack.stack_name,
            'stack_status_json_url': self.request.route_path('stack_state_json', name=self.stack.stack_name),
            'stack_template_url': self.request.route_path('stack_template', name=self.stack.stack_name),
            'stack_events_url': self.request.route_path('stack_events', name=self.stack.stack_name),
        }))


class StackStateView(BaseView):
    def __init__(self, request):
        super(StackStateView, self).__init__(request)
        self.request = request
        self.cloudformation_conn = self.get_connection(conn_type='cloudformation')
        self.stack_name = self.request.matchdict.get('name')

    @view_config(route_name='stack_state_json', renderer='json', request_method='GET')
    def stack_state_json(self):
        """Return current stack status"""
        with boto_error_handler(self.request):
            stacks = self.cloudformation_conn.describe_stacks(self.stack_name)
            stack = stacks[0] if stacks else None
            stack_resources = self.cloudformation_conn.list_stack_resources(self.stack_name)
            stack_status = stack.stack_status if stack else 'delete_complete'
            stack_outputs = stack.outputs if stack else None
            outputs = [];
            for output in stack_outputs:
                outputs.append({'key':output.key, 'value':output.value})
            resources = []
            for resource in stack_resources:
                resources.append({
                    'type':resource.resource_type,
                    'logical_id':resource.logical_resource_id,
                    'physical_id':resource.physical_resource_id,
                    'status':resource.resource_status,
                    'updated_timestamp':resource.LastUpdatedTimestamp})
            return dict(
                results=dict(stack_status=stack_status.lower().replace('_', '-'),
                             outputs=outputs,
                             resources=resources)
            )

    @view_config(route_name='stack_template', renderer='json', request_method='GET')
    def stack_template(self):
        """Return stack template"""
        with boto_error_handler(self.request):
            template = self.cloudformation_conn.get_template(self.stack_name)
            parsed = json.loads(template['GetTemplateResponse']['GetTemplateResult']['TemplateBody'])
            params = []
            for name in parsed['Parameters'].keys():
                param = parsed['Parameters'][name]
                params.append({'name':name, 'description':param['Description'], 'type':param['Type']})
            return dict(
                results=dict(description=parsed['Description'],
                             parameters=params)
            )

    @view_config(route_name='stack_events', renderer='json', request_method='GET')
    def stack_events(self):
        """Return stack events"""
        with boto_error_handler(self.request):
            stack_events = self.cloudformation_conn.describe_stack_events(self.stack_name)
            events = []
            for event in stack_events:
                events.append({
                    'timestamp':event.timestamp.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'status':event.resource_status,
                    'status_reason':event.resource_status_reason,
                    'type':event.resource_type,
                    'logical_id':event.logical_resource_id,
                    'physical_id':event.physical_resource_id})
            return dict(
                results=dict(events=events)
            )

class StackWizardView(BaseView):
    """View for Create Stack wizard"""
    TEMPLATE = '../templates/stacks/stack_wizard.pt'

    def __init__(self, request):
        super(StackWizardView, self).__init__(request)
        self.request = request
        self.create_form = StacksCreateForm(request)
        self.render_dict = dict(
            create_form=self.create_form,
            controller_options_json=self.get_controller_options_json(),  # TODO: delete if not needed
        )

    def get_controller_options_json(self):
        return BaseView.escape_json(json.dumps({
            '': '',
        }))

    @view_config(route_name='stack_new', renderer=TEMPLATE, request_method='GET')
    def stack_new(self):
        """Displays the Stack wizard"""
        return self.render_dict

