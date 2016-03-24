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
Pyramid views for Login/Logout

"""
import base64
import logging
import simplejson as json
from urllib2 import HTTPError, URLError
from urlparse import urlparse
from boto.connection import AWSAuthConnection
from boto.exception import BotoServerError

from pyramid.httpexceptions import HTTPFound
from pyramid.security import NO_PERMISSION_REQUIRED, remember, forget
from pyramid.settings import asbool
from pyramid.view import view_config, forbidden_view_config

from ..forms.login import EucaLoginForm, EucaLogoutForm, AWSLoginForm
from ..i18n import _
from ..models.auth import AWSAuthenticator, ConnectionManager
from ..views import BaseView
from ..views import JSONResponse
from ..constants import AWS_REGIONS


INVALID_SSL_CERT_MSG = _(u"This cloud's SSL server certificate isn't valid. Please contact your cloud administrator.")


@forbidden_view_config()
def redirect_to_login_page(request):
    login_url = request.route_path('login')
    return HTTPFound(login_url)


class PermissionCheckMixin(object):
    def check_iam_perms(self, session, creds):
        iam_conn = self.get_connection(
            conn_type='iam', cloud_type='euca', region='euca',
            access_key=creds.access_key, secret_key=creds.secret_key, security_token=creds.session_token)
        account = session['account']
        session['account_access'] = True if account == 'eucalyptus' else False
        session['user_access'] = False
        try:
            iam_conn.get_all_users(path_prefix="/notlikely")
            session['user_access'] = True
        except BotoServerError:
            pass
        session['group_access'] = False
        try:
            iam_conn.get_all_groups(path_prefix="/notlikely")
            session['group_access'] = True
        except BotoServerError:
            pass
        session['role_access'] = False
        try:
            iam_conn.list_roles(path_prefix="/notlikely")
            session['role_access'] = True
        except BotoServerError:
            pass


class LoginView(BaseView, PermissionCheckMixin):
    TEMPLATE = '../templates/login.pt'

    def __init__(self, request):
        super(LoginView, self).__init__(request)
        self.title_parts = [_(u'Login')]
        self.euca_login_form = EucaLoginForm(self.request, formdata=self.request.params or None)
        self.aws_login_form = AWSLoginForm(self.request, formdata=self.request.params or None)
        self.aws_enabled = asbool(request.registry.settings.get('enable.aws'))
        referrer = urlparse(self.request.url).path
        login_url = self.request.route_path('login')
        logout_url = self.request.route_path('logout')
        if referrer in [login_url, logout_url]:
            referrer = '/'  # never use the login form (or logout view) itself as came_from
        self.came_from = self.sanitize_url(self.request.params.get('came_from', referrer))
        self.login_form_errors = []
        self.duration = str(int(self.request.registry.settings.get('session.cookie_expires')) + 60)
        self.login_refresh = str(int(self.request.registry.settings.get('session.timeout')) - 60)
        self.secure_session = asbool(self.request.registry.settings.get('session.secure', False))
        self.https_proxy = self.request.environ.get('HTTP_X_FORWARDED_PROTO') == 'https'
        self.https_scheme = self.request.scheme == 'https'
        options_json = BaseView.escape_json(json.dumps(dict(
            account=request.params.get('account', default=''),
            username=request.params.get('username', default=''),
        )))
        self.render_dict = dict(
            https_required=self.show_https_warning(),
            euca_login_form=self.euca_login_form,
            aws_login_form=self.aws_login_form,
            login_form_errors=self.login_form_errors,
            aws_enabled=self.aws_enabled,
            duration=self.duration,
            login_refresh=self.login_refresh,
            came_from=self.came_from,
            controller_options_json=options_json,
        )

    def show_https_warning(self):
        if self.secure_session and not (any([self.https_proxy, self.https_scheme])):
            return True
        return False

    @view_config(route_name='login', request_method='GET', renderer=TEMPLATE, permission=NO_PERMISSION_REQUIRED)
    @forbidden_view_config(request_method='GET', renderer=TEMPLATE)
    def login_page(self):
        if self.request.is_xhr:
            message = getattr(self.request.exception, 'message', _(u"Session Timed Out"))
            status = getattr(self.request.exception, 'status', "403 Forbidden")
            status = int(status[:status.index(' ')]) or 403
            return JSONResponse(status=status, message=message)
        return self.render_dict

    @view_config(route_name='login', request_method='POST', renderer=TEMPLATE, permission=NO_PERMISSION_REQUIRED)
    def handle_login(self):
        """Handle login form post"""

        login_type = self.request.params.get('login_type')

        if login_type == 'Eucalyptus':
            return self.handle_euca_login()
        elif login_type == 'AWS':
            return self.handle_aws_login()

        return self.render_dict

    def handle_euca_login(self):
        new_passwd = None
        auth = self.get_euca_authenticator()
        session = self.request.session

        if self.euca_login_form.validate():
            account = self.request.params.get('account')
            username = self.request.params.get('username')
            password = self.request.params.get('password')
            euca_region = self.request.params.get('euca-region')
            try:
                # TODO: also return dns enablement
                creds = auth.authenticate(
                    account=account, user=username, passwd=password,
                    new_passwd=new_passwd, timeout=8, duration=self.duration)
                logging.info(u"Authenticated Eucalyptus user: {acct}/{user} from {ip}".format(
                    acct=account, user=username, ip=BaseView.get_remote_addr(self.request)))
                default_region = self.request.registry.settings.get('default.region', 'euca')
                user_account = u'{user}@{account}'.format(user=username, account=account)
                session.invalidate()  # Refresh session
                session['cloud_type'] = 'euca'
                session['account'] = account
                session['username'] = username
                session['session_token'] = creds.session_token
                session['access_id'] = creds.access_key
                session['secret_key'] = creds.secret_key
                session['region'] = euca_region if euca_region != '' else default_region
                session['username_label'] = user_account
                session['dns_enabled'] = auth.dns_enabled  # this *must* be prior to line below
                session['supported_platforms'] = self.get_account_attributes(['supported-platforms'])
                session['default_vpc'] = self.get_account_attributes(['default-vpc'])

                # handle checks for IAM perms
                self.check_iam_perms(session, creds)
                headers = remember(self.request, user_account)
                return HTTPFound(location=self.came_from, headers=headers)
            except HTTPError, err:
                logging.info("http error " + str(vars(err)))
                if err.code == 403:  # password expired
                    changepwd_url = self.request.route_path('managecredentials')
                    return HTTPFound(
                        changepwd_url + ("?came_from=&expired=true&account=%s&username=%s" % (account, username))
                    )
                elif err.msg == u'Unauthorized':
                    msg = _(u'Invalid user/account name and/or password.')
                    self.login_form_errors.append(msg)
            except URLError, err:
                logging.info("url error " + str(vars(err)))
                # if str(err.reason) == 'timed out':
                # opened this up since some other errors should be reported as well.
                if err.reason.find('ssl') > -1:
                    msg = INVALID_SSL_CERT_MSG
                else:
                    msg = _(u'No response from host')
                self.login_form_errors.append(msg)
        return self.render_dict

    def handle_aws_login(self):
        session = self.request.session
        if self.aws_login_form.validate():
            package = self.request.params.get('package')
            package = base64.decodestring(package)
            aws_region = self.request.params.get('aws-region')
            validate_certs = asbool(self.request.registry.settings.get('connection.ssl.validation', False))
            conn = AWSAuthConnection(None, aws_access_key_id='', aws_secret_access_key='')
            ca_certs_file = conn.ca_certificates_file
            conn = None
            ca_certs_file = self.request.registry.settings.get('connection.ssl.certfile', ca_certs_file)
            auth = AWSAuthenticator(package=package, validate_certs=validate_certs, ca_certs=ca_certs_file)
            try:
                creds = auth.authenticate(timeout=10)
                logging.info(u"Authenticated AWS user from {ip}".format(ip=BaseView.get_remote_addr(self.request)))
                default_region = self.request.registry.settings.get('aws.default.region', 'us-east-1')
                session.invalidate()  # Refresh session
                session['cloud_type'] = 'aws'
                session['session_token'] = creds.session_token
                session['access_id'] = creds.access_key
                session['secret_key'] = creds.secret_key
                last_visited_aws_region = [reg for reg in AWS_REGIONS if reg.get('name') == aws_region]
                session['region'] = aws_region if last_visited_aws_region else default_region
                session['username_label'] = u'{user}...@AWS'.format(user=creds.access_key[:8])
                session['supported_platforms'] = self.get_account_attributes(['supported-platforms'])
                session['default_vpc'] = self.get_account_attributes(['default-vpc'])
                conn = ConnectionManager.aws_connection(
                    session['region'], creds.access_key, creds.secret_key, creds.session_token, 'vpc')
                vpcs = conn.get_all_vpcs()
                if not vpcs or len(vpcs) == 0:
                    # remove vpc from supported-platforms
                    if 'VPC' in session.get('supported_platforms', []):
                        session.get('supported_platforms').remove('VPC')
                headers = remember(self.request, creds.access_key[:8])
                return HTTPFound(location=self.came_from, headers=headers)
            except HTTPError, err:
                if err.msg == 'Forbidden':
                    msg = _(u'Invalid access key and/or secret key.')
                    self.login_form_errors.append(msg)
            except URLError, err:
                if err.reason.find('ssl') > -1:
                    msg = INVALID_SSL_CERT_MSG
                else:
                    msg = _(u'No response from host')
                self.login_form_errors.append(msg)
        return self.render_dict


class LogoutView(BaseView):
    def __init__(self, request):
        super(LogoutView, self).__init__(request)
        self.request = request
        self.login_url = request.route_path('login')
        self.euca_logout_form = EucaLogoutForm(self.request, formdata=self.request.params or None)

    @view_config(route_name='logout', request_method='POST')
    def logout(self):
        if self.euca_logout_form.validate():
            forget(self.request)
            self.request.session.invalidate()
        return HTTPFound(location=self.login_url)
