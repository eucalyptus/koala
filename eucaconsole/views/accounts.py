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
Pyramid views for Eucalyptus and AWS Accounts

"""
import csv
import simplejson as json
import StringIO
from urllib import urlencode, unquote

from boto.exception import BotoServerError
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.view import view_config

from ..forms.accounts import AccountForm, AccountUpdateForm, DeleteAccountForm
from ..forms.quotas import QuotasForm
from ..i18n import _
from ..models import Notification
from ..models.quotas import Quotas
from ..views import BaseView, LandingPageView, JSONResponse
from . import boto_error_handler
from .users import PasswordGeneration


class AccountsView(LandingPageView):
    TEMPLATE = '../templates/accounts/accounts.pt'

    def __init__(self, request):
        super(AccountsView, self).__init__(request)
        self.title_parts = [_(u'Accounts')]
        self.conn = self.get_connection(conn_type="iam")
        self.initial_sort_key = 'account_name'
        self.prefix = '/accounts'
        self.delete_form = DeleteAccountForm(self.request, formdata=self.request.params or None)

    @view_config(route_name='accounts', renderer=TEMPLATE)
    def accounts_landing(self):
        json_items_endpoint = self.request.route_path('accounts_json')
        if self.request.GET:
            json_items_endpoint += u'?{params}'.format(params=urlencode(self.request.GET))
        # filter_keys are passed to client-side filtering in search box
        self.filter_keys = ['account_name', 'account_id']
        # sort_keys are passed to sorting drop-down
        self.sort_keys = [
            dict(key='account_name', name=_(u'Account name: A to Z')),
            dict(key='-account_name', name=_(u'Account name: Z to A')),
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

    @view_config(route_name='accounts_delete', request_method='POST')
    def accounts_delete(self):
        location = self.request.route_path('accounts')
        account_name = self.request.params.get('name')
        if self.delete_form.validate():
            with boto_error_handler(self.request, location):
                self.log_request(_(u"Deleting account {0}").format(account_name))
                params = {'AccountName': account_name, 'Recursive': 'true'}
                self.conn.get_response('DeleteAccount', params)
                msg = _(u'Successfully deleted account')
                self.request.session.flash(msg, queue=Notification.SUCCESS)
        else:
            msg = _(u'Unable to delete account.')  # TODO Pull in form validation error messages here
            self.request.session.flash(msg, queue=Notification.ERROR)
        return HTTPFound(location=location)


class AccountsJsonView(BaseView):
    """Accounts returned as JSON"""

    def __init__(self, request):
        super(AccountsJsonView, self).__init__(request)
        self.conn = self.get_connection(conn_type="iam")

    @view_config(route_name='accounts_json', renderer='json', request_method='POST')
    def accounts_json(self):
        # TODO: take filters into account??
        accounts = []
        for account in self.get_items():
            policies = []
            try:
                policies = self.conn.get_response(
                    'ListAccountPolicies',
                    params={'AccountName': account.account_name}, list_marker='PolicyNames')
                policies = policies.policy_names
            except BotoServerError:
                pass
            accounts.append(dict(
                account_name=account.account_name,
                account_id=account.account_id,
                policy_count=len(policies),
            ))
        return dict(results=accounts)

    @view_config(route_name='account_summary_json', renderer='json', request_method='GET')
    def account_summary_json(self):
        name = self.request.matchdict.get('name')
        with boto_error_handler(self.request):
            users = self.conn.get_response('ListUsers', params={'DelegateAccount': name}, list_marker='Users')
            groups = self.conn.get_response('ListGroups', params={'DelegateAccount': name}, list_marker='Groups')
            roles = self.conn.get_response('ListRoles', params={'DelegateAccount': name}, list_marker='Roles')
            return dict(
                results=dict(
                    account_name=name,
                    user_count=len(users.list_users_response.list_users_result.users),
                    group_count=len(groups.list_groups_response.list_groups_result.groups),
                    role_count=len(roles.list_roles_response.list_roles_result.roles),
                )
            )

    def get_items(self):
        with boto_error_handler(self.request):
            return self.conn.get_response('ListAccounts', params={}, list_marker='Accounts').accounts


class AccountView(BaseView):
    """Views for single Account"""
    TEMPLATE = '../templates/accounts/account_view.pt'
    NEW_TEMPLATE = '../templates/accounts/account_new.pt'

    def __init__(self, request):
        super(AccountView, self).__init__(request)
        self.title_parts = [_(u'Account'), request.matchdict.get('name') or _(u'Create')]
        self.conn = self.get_connection(conn_type="iam")
        self.account = self.get_account()
        self.account_route_id = self.request.matchdict.get('name')
        self.account_form = AccountForm(self.request, account=self.account, formdata=self.request.params or None)
        self.account_update_form = AccountUpdateForm(self.request, account=self.account,
                                                     formdata=self.request.params or None)
        self.delete_form = DeleteAccountForm(self.request, formdata=self.request.params)
        self.quotas_form = QuotasForm(self.request, account=self.account, conn=self.conn)
        self.account_name_validation_error_msg = _(
            u'''
            Account names must be between 3 and 63 characters long, and may contain lower case
            letters, numbers, '.', '@' and '-', and cannot contain spaces. Account names must not
            consist of exactly 12 digits.
            ''')
        self.render_dict = dict(
            account=self.account,
            account_route_id=self.account_route_id,
            account_form=self.account_form,
            account_update_form=self.account_update_form,
            delete_form=self.delete_form,
            quota_err=_(u"Requires non-negative integer (or may be empty)"),
            quotas_form=self.quotas_form,
            account_name_validation_error_msg=self.account_name_validation_error_msg,
        )

    def get_account(self):
        account_param = self.request.matchdict.get('name')
        # Return None if the request is to create new account. Prob. No accountname "new" can be created
        if account_param == "new" or account_param is None:
            return None
        account = None
        try:
            accounts = self.conn.get_response('ListAccounts', params={}, list_marker='Accounts').accounts
            account = [account for account in accounts if account.account_name == account_param][0]
        except BotoServerError:
            pass
        return account

    @view_config(route_name='account_new', renderer=NEW_TEMPLATE)
    def account_new(self):
        return self.render_dict

    @view_config(route_name='account_view', renderer=TEMPLATE)
    def account_view(self):
        if self.account is not None:
            with boto_error_handler(self.request):
                users = self.conn.get_response(
                    'ListUsers',
                    params={'DelegateAccount': self.account.account_name}, list_marker='Users')
                self.render_dict['users'] = users.list_users_response.list_users_result.users
                groups = self.conn.get_response(
                    'ListGroups',
                    params={'DelegateAccount': self.account.account_name}, list_marker='Groups')
                self.render_dict['groups'] = groups.list_groups_response.list_groups_result.groups
                roles = self.conn.get_response(
                    'ListRoles',
                    params={'DelegateAccount': self.account.account_name}, list_marker='Roles')
                self.render_dict['roles'] = roles.list_roles_response.list_roles_result.roles
        return self.render_dict

    @view_config(route_name='account_create', request_method='POST', renderer='json')
    def account_create(self):
        if self.account_form.validate():
            new_account_name = self.request.params.get('account_name')
            location = self.request.route_path('account_view', name=new_account_name)

            random_password = self.request.params.get('random_password', 'n') == 'y'
            access_keys = self.request.params.get('access_keys', 'n') == 'y'
            users_json = self.request.params.get('users')

            user_list = []

            with boto_error_handler(self.request, location):
                self.log_request(_(u'Creating account {0}').format(new_account_name))
                self.conn.get_response('CreateAccount',
                                       params={'AccountName': new_account_name})

                user = self._create_user(new_account_name, 'admin', None,
                                         create_password=random_password,
                                         create_access_keys=access_keys)
                user_list.append(user)

                quotas = Quotas()
                quotas.create_quota_policy(self, account=new_account_name)

                if users_json:
                    users = json.loads(users_json)
                    for (name, email) in users.items():
                        user = self._create_user(new_account_name, name, email,
                                                 create_password=random_password,
                                                 create_access_keys=access_keys)
                        user_list.append(user)

                # assemble file response
                has_file = 'n'
                if access_keys or random_password:
                    string_output = StringIO.StringIO()
                    csv_w = csv.writer(string_output)
                    header = [_(u'Account'), _(u'User Name')]
                    if random_password:
                        header.append(_(u'Password'))
                    if access_keys:
                        header.extend([_(u'Access Key'), _(u'Secret Key')])
                    csv_w.writerow(header)
                    for user in user_list:
                        row = [user['account'], user['name']]
                        if random_password:
                            row.append(user['password'])
                        if access_keys:
                            row.extend([user['access_id'], user['secret_key']])
                        csv_w.writerow(row)
                    self._store_file_(u"{acct}-users.csv".format(acct=new_account_name),
                                      'text/csv', string_output.getvalue())
                    has_file = 'y'

                return dict(
                    message=_(u"Successfully created account {account}").format(account=new_account_name),
                    results=dict(hasFile=has_file)
                )

        return self.render_dict

    def _create_user(self, account, name, email, path='/', create_password=True, create_access_keys=True):
        user = {
            'account': account,
            'name': name
        }

        if name is not 'admin':
            self.log_request(_(u'Creating user {0}').format(name))
            self.conn.get_response('CreateUser',
                                   params={'UserName': name, 'Path': path,
                                           'DelegateAccount': account})

        if create_password:
            self.log_request(_(u'Generating password for user {0}').format(name))
            password = PasswordGeneration.generate_password()
            self.conn.get_response('CreateLoginProfile',
                                       params={'UserName': name, 'Password': password,
                                               'DelegateAccount': account})
            user['password'] = password

        if create_access_keys:
            self.log_request(_(u'Creating access keys for user {0}').format(name))
            creds = self.conn.get_response('CreateAccessKey',
                                           params={'UserName': name, 'DelegateAccount': account})
            user['access_id'] = creds.access_key.access_key_id
            user['secret_key'] = creds.access_key.secret_access_key

        return user


    @view_config(route_name='account_update', request_method='POST', renderer=TEMPLATE)
    def account_update(self):
        if self.account_update_form.validate():
            location = self.request.route_path('account_view', name=self.account.account_name)
            with boto_error_handler(self.request, location):
                quotas = Quotas()
                quotas.update_quotas(self, account=self.account.account_name, as_account='')
            return HTTPFound(location=location)

        return self.render_dict

    @view_config(route_name='account_delete', request_method='POST')
    def account_delete(self):
        if not self.delete_form.validate():
            return JSONResponse(status=400, message="missing CSRF token")
        location = self.request.route_path('accounts')
        if self.account is None:
            raise HTTPNotFound()
        with boto_error_handler(self.request, location):
            self.log_request(_(u"Deleting account {0}").format(self.account.account_name))
            params = {'AccountName': self.account.account_name, 'Recursive': 'true'}
            self.conn.get_response('DeleteAccount', params)
            msg = _(u'Successfully deleted account')
            self.request.session.flash(msg, queue=Notification.SUCCESS)
        return HTTPFound(location=location)

    def account_update_name(self, new_account_name):
        this_account_name = new_account_name if new_account_name is not None else self.account.account_name
        self.conn.update_account(self.account.account_name, new_account_name=new_account_name)
        msg_template = _(u'Successfully modified account {account}')
        msg = msg_template.format(account=this_account_name)
        self.request.session.flash(msg, queue=Notification.SUCCESS)
        return

    @view_config(route_name='account_policies_json', renderer='json', request_method='GET')
    def account_policies_json(self):
        """Return account policies list"""
        with boto_error_handler(self.request):
            policies = self.conn.get_response('ListAccountPolicies', params={'AccountName': self.account.account_name},
                                              list_marker='PolicyNames')
            return dict(results=policies.policy_names)

    @view_config(route_name='account_policy_json', renderer='json', request_method='GET')
    def account_policy_json(self):
        """Return account policies list"""
        with boto_error_handler(self.request):
            policy_name = self.request.matchdict.get('policy')
            policy = self.conn.get_response('GetAccountPolicy', params={'AccountName': self.account.account_name,
                                                                        'PolicyName': policy_name}, verb='POST')
            parsed = json.loads(unquote(policy.policy_document))
            return dict(results=json.dumps(parsed, indent=2))

    @view_config(route_name='account_update_policy', request_method='POST', renderer='json')
    def account_update_policy(self):
        if not (self.is_csrf_valid()):
            return JSONResponse(status=400, message="missing CSRF token")
        # calls iam:PutAccountPolicy
        policy = self.request.matchdict.get('policy')
        with boto_error_handler(self.request):
            self.log_request(_(u"Updating policy {0} for account {1}").format(policy, self.account.account_name))
            policy_text = self.request.params.get('policy_text')
            result = self.conn.get_response('PutAccountPolicy',
                                            params={'AccountName': self.account.account_name, 'PolicyName': policy,
                                                    'PolicyDocument': policy_text}, verb='POST')
            return dict(message=_(u"Successfully updated account policy"), results=result)

    @view_config(route_name='account_delete_policy', request_method='POST', renderer='json')
    def account_delete_policy(self):
        if not self.is_csrf_valid():
            return JSONResponse(status=400, message="missing CSRF token")
        # calls iam:DeleteAccountPolicy
        policy = self.request.matchdict.get('policy')
        with boto_error_handler(self.request):
            self.log_request(_(u"Deleting policy {0} for account {1}").format(policy, self.account.account_name))
            result = self.conn.get_response('DeleteAccountPolicy',
                                            params={'AccountName': self.account.account_name, 'PolicyName': policy},
                                            verb='POST')
            return dict(message=_(u"Successfully deleted account policy"), results=result)

