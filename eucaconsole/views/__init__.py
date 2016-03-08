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
Core views

"""
import base64
import hashlib
import hmac
import logging
import pylibmc
import simplejson as json
import string
import textwrap
import time
from datetime import datetime, timedelta
import threading

from cgi import FieldStorage
from contextlib import contextmanager
from dateutil import tz
from markupsafe import Markup
from random import choice
from urllib import urlencode
from urlparse import urlparse
try:
    import python_magic as magic
except ImportError:
    import magic

from boto.connection import AWSAuthConnection
from boto.ec2.blockdevicemapping import BlockDeviceType, BlockDeviceMapping
from boto.exception import BotoServerError

from pyramid.httpexceptions import HTTPFound, HTTPException, HTTPUnprocessableEntity
from pyramid.i18n import TranslationString
from pyramid.response import Response
from pyramid.security import NO_PERMISSION_REQUIRED
from pyramid.settings import asbool
from pyramid.view import notfound_view_config, view_config

from ..caches import long_term
from ..caches import invalidate_cache
from ..constants.images import AWS_IMAGE_OWNER_ALIAS_CHOICES, EUCA_IMAGE_OWNER_ALIAS_CHOICES
from ..forms.login import EucaLogoutForm
from ..models.auth import EucaAuthenticator
from ..i18n import _
from ..models import Notification
from ..models.auth import ConnectionManager, RegionCache


def escape_braces(event):
    """Escape double curly braces in template variables to prevent AngularJS expression injections"""
    for k, v in event.rendering_val.items():
        if not k.endswith('_json') and event.get('renderer_name') != 'json':
            if type(v) in [str, unicode] or isinstance(v, Markup) or isinstance(v, TranslationString):
                event.rendering_val[k] = BaseView.escape_braces(v)


class JSONResponse(Response):
    def __init__(self, status=200, message=None, id=None, **kwargs):
        super(JSONResponse, self).__init__(**kwargs)
        self.status = status
        self.content_type = 'application/json'
        self.body = json.dumps(
            dict(message=message, id=id)
        )


# Can use this for 1.5, but the fix below for 1.4 also works in 1.5.
# class JSONError(HTTPException):
class JSONError(HTTPUnprocessableEntity):
    def __init__(self, status=400, message=None, **kwargs):
        super(JSONError, self).__init__(**kwargs)
        self.status = status
        self.content_type = 'application/json'
        self.body = json.dumps(
            dict(message=message)
        )


class BaseView(object):
    """Base class for all views"""
    def __init__(self, request, **kwargs):
        self.request = request
        self.region = request.session.get('region')
        self.access_key = request.session.get('access_id')
        self.secret_key = request.session.get('secret_key')
        self.cloud_type = request.session.get('cloud_type')
        self.security_token = request.session.get('session_token')
        self.euca_logout_form = EucaLogoutForm(self.request)

    def get_connection(self, conn_type='ec2', cloud_type=None, region=None, access_key=None,
                       secret_key=None, security_token=None):
        conn = None
        if cloud_type is None:
            cloud_type = self.cloud_type

        if region is None:
            region = self.region
        if access_key is None:
            access_key = self.access_key
        if secret_key is None:
            secret_key = self.secret_key
        if security_token is None:
            security_token = self.security_token

        validate_certs = False
        if self.request.registry.settings:  # do this to pass tests
            validate_certs = asbool(self.request.registry.settings.get('connection.ssl.validation', False))
            certs_file = self.request.registry.settings.get('connection.ssl.certfile', None)
        if cloud_type == 'aws':
            conn = ConnectionManager.aws_connection(
                region, access_key, secret_key, security_token, conn_type, validate_certs)
        elif cloud_type == 'euca':
            host = self._get_ufs_host_setting_()
            port = self._get_ufs_port_setting_()
            dns_enabled = self.request.session.get('dns_enabled', True)
            regions = RegionCache(None).regions()
            if len(regions) > 0:
                for region in regions:
                    if region['endpoints']['ec2'].find(host) > -1:
                        self.default_region = region['name']
            conn = ConnectionManager.euca_connection(
                host, port, region, access_key, secret_key, security_token,
                conn_type, dns_enabled, validate_certs, certs_file
            )

        return conn

    def get_account_display_name(self):
        if self.cloud_type == 'euca':
            return self.request.session.get('account')
        return self.request.session.get('access_id')  # AWS

    def is_csrf_valid(self, token=None):
        if token is None:
            token = self.request.params.get('csrf_token')
        return self.request.session.get_csrf_token() == token

    def _store_file_(self, filename, mime_type, contents):
        # disable using memcache for file storage
        # try:
        #    default_term.set('file_cache', (filename, mime_type, contents))
        # except pylibmc.Error as ex:
        #    logging.warn("memcached misconfigured or not reachable, using session storage")
        # to re-enable, uncomment lines above and indent 2 lines below
        session = self.request.session
        session['file_cache'] = (filename, mime_type, contents)

    def _has_file_(self):
        # check both cache and session
        # disable using memcache for file storage
        # try:
        #    return not isinstance(default_term.get('file_cache'), NoValue)
        # except pylibmc.Error as ex:
        # to re-enable, uncomment lines above and indent 2 lines below
        session = self.request.session
        return 'file_cache' in session

    def get_user_data(self):
        input_type = self.request.params.get('inputtype')
        userdata_input = self.request.params.get('userdata')
        userdata_file_param = self.request.POST.get('userdata_file')
        userdata_file = userdata_file_param.file.read() if isinstance(userdata_file_param, FieldStorage) else None
        if input_type == 'file':
            userdata = userdata_file
        elif input_type == 'text':
            userdata = userdata_input
        else:
            userdata = userdata_file or userdata_input or None  # Look up file upload first
        return userdata

    def get_shared_buckets_storage_key(self, host):
        return "{0}{1}{2}{3}".format(
            host,
            self.region,
            self.request.session['account' if self.cloud_type == 'euca' else 'access_id'],
            self.request.session['username'] if self.cloud_type == 'euca' else '',
        )

    @long_term.cache_on_arguments(namespace='images')
    def _get_images_cached_(self, _owners, _executors, _ec2_region, acct, ufshost):
        """
        This method is decorated and will cache the image set
        """
        return self._get_images_(_owners, _executors, _ec2_region)

    def _get_images_(self, _owners, _executors, _ec2_region):
        """
        this method produces a cachable list of images
        """
        with boto_error_handler(self.request):
            logging.info("loading images from server (not cache)")
            filters = {'image-type': 'machine'}
            images = self.get_connection().get_all_images(owners=_owners, executable_by=_executors, filters=filters)
            ret = []
            for img in images:
                # trim some un-necessary items we don't need to cache
                del img.connection
                del img.region
                del img.product_codes
                del img.billing_products
                # alter things we want to cache, but are un-picklable
                if img.block_device_mapping:
                    for bdm in img.block_device_mapping.keys():
                        mapping_type = img.block_device_mapping[bdm]
                        del mapping_type.connection
                ret.append(img)
            return ret

    def get_images(self, conn, owners, executors, ec2_region):
        """
        This method sets the right account value so we cache private images per-acct
        and handles caching error by fetching the data from the server.
        """
        acct = self.request.session.get('account', '')
        if acct == '':
            acct = self.request.session.get('access_id', '')
        if 'amazon' in owners or 'aws-marketplace' in owners:
            acct = ''
        ufshost = self.get_connection().host if self.cloud_type == 'euca' else ''
        try:
            if self.cloud_type == 'euca' and asbool(self.request.registry.settings.get('cache.images.disable', False)):
                return self._get_images_(owners, executors, ec2_region)
            else:
                return self._get_images_cached_(owners, executors, ec2_region, acct, ufshost)
        except pylibmc.Error:
            logging.warn('memcached not responding')
            return self._get_images_(owners, executors, ec2_region)

    def invalidate_images_cache(self):
        region = self.request.session.get('region')
        acct = self.request.session.get('account', '')
        if acct == '':
            acct = self.request.session.get('access_id', '')
        ufshost = self.get_connection().host if self.cloud_type == 'euca' else ''
        invalidate_cache(long_term, 'images', None, [], [], region, acct, ufshost)
        invalidate_cache(long_term, 'images', None, [u'self'], [], region, acct, ufshost)
        invalidate_cache(long_term, 'images', None, [], [u'self'], region, acct, ufshost)

    def get_euca_authenticator(self):
        """
        This method centralizes configuration of the EucaAuthenticator.
        """
        host = self._get_ufs_host_setting_()
        port = self._get_ufs_port_setting_()
        validate_certs = asbool(self.request.registry.settings.get('connection.ssl.validation', False))
        conn = AWSAuthConnection(None, aws_access_key_id='', aws_secret_access_key='')
        ca_certs_file = conn.ca_certificates_file
        conn = None
        ca_certs_file = self.request.registry.settings.get('connection.ssl.certfile', ca_certs_file)
        dns_enabled = self.request.session.get('dns_enabled', True)
        auth = EucaAuthenticator(host, port, dns_enabled, validate_certs=validate_certs, ca_certs=ca_certs_file)
        return auth

    def get_account_attributes(self, attribute_names=None):
        self.__init__(self.request)
        attribute_names = attribute_names or ['supported-platforms']
        conn = self.get_connection()
        if conn:
            with boto_error_handler(self.request):
                attributes = conn.describe_account_attributes(attribute_names=attribute_names)
                return attributes[0].attribute_values

    def _get_ufs_host_setting_(self):
        host = self.request.registry.settings.get('ufshost')
        if not host:
            host = self.request.registry.settings.get('clchost', 'localhost')
        return host

    def _get_ufs_port_setting_(self):
        port = self.request.registry.settings.get('ufsport')
        if not port:
            port = self.request.registry.settings.get('clcport', 8773)
        return int(port)

    @staticmethod
    def is_vpc_supported(request):
        return 'VPC' in request.session.get('supported_platforms', [])

    @staticmethod
    def escape_braces(s):
        if type(s) in [str, unicode] or isinstance(s, Markup) or isinstance(s, TranslationString):
            return s.replace('{{', '&#123;&#123;').replace('}}', '&#125;&#125;')

    @staticmethod
    def unescape_braces(s):
        if type(s) in [str, unicode] or isinstance(s, Markup) or isinstance(s, TranslationString):
            return s.replace('&#123;&#123;', '{{').replace('&#125;&#125;', '}}')

    @staticmethod
    def sanitize_url(url):
        default_path = '/'
        if not url:
            return default_path
        parsed_url = urlparse(url)
        scheme = parsed_url.scheme
        netloc = parsed_url.netloc
        if scheme:
            if not netloc:  # Prevent arbitrary redirects when url scheme has extra slash e.g. "http:///example.com"
                return default_path
            url = parsed_url.path
        return url or default_path

    @staticmethod
    def get_remote_addr(request):
        return request.environ.get('HTTP_X_FORWARDED_FOR', getattr(request, 'remote_addr', ''))

    @staticmethod
    def log_message(request, message, level='info'):
        prefix = ''
        cloud_type = request.session.get('cloud_type', 'euca')
        if cloud_type == 'euca':
            account = request.session.get('account', '')
            username = request.session.get('username', '')
            prefix = u'{0}/{1}@{2}'.format(account, username, BaseView.get_remote_addr(request))
        elif cloud_type == 'aws':
            account = request.session.get('username_label', '')
            region = request.session.get('region')
            prefix = u'{0}/{1}@{2}'.format(account, region, BaseView.get_remote_addr(request))
        log_message = u"{prefix} [{id}]: {msg}".format(prefix=prefix, id=request.id, msg=message)
        if level == 'info':
            logging.info(log_message)
        elif level == 'error':
            logging.error(log_message)
        # Very useful to use this when an error is logged and you need more details
        # import traceback; traceback.print_exc()

    def log_request(self, message):
        self.log_message(self.request, message)

    @staticmethod
    def handle_error(err=None, request=None, location=None, template=u"{0}"):
        status = getattr(err, 'status', None) or err.args[0] if err.args else ""
        message = template.format(err.reason)
        if err.error_message is not None:
            message = err.error_message
            if 'because of:' in message:
                message = message[message.index("because of:") + 11:]
            if 'RelatesTo Error:' in message:
                message = message[message.index("RelatesTo Error:") + 16:]
            # do we need this logic in the common code?? msg = err.message.split('remoteDevice')[0]
            # this logic found in volumes.js
        BaseView.log_message(request, message, level='error')
        perms_notice = _(u'You do not have the required permissions to perform this '
                         u'operation. Please retry the operation, and contact your cloud '
                         u'administrator to request an updated access policy if the problem persists.')
        if request.is_xhr:
            if err.code in ['AccessDenied', 'UnauthorizedOperation']:
                message = perms_notice
            raise JSONError(message=message, status=status or 403)
        if status == 403 or 'token has expired' in message:  # S3 token expiration responses return a 400 status
            if err.code in ['AccessDenied', 'UnauthorizedOperation'] and location is not None:
                request.session.flash(perms_notice, queue=Notification.ERROR)
                raise HTTPFound(location=location)

            notice = _(u'Your session has timed out. This may be due to inactivity, '
                       u'a policy that does not provide login permissions, or an unexpected error. '
                       u'Please log in again, and contact your cloud administrator if the problem persists.')
            request.session.flash(notice, queue=Notification.WARNING)
            raise HTTPFound(location=request.route_path('login'))
        request.session.flash(message, queue=Notification.ERROR)
        if location is None:
            location = request.current_route_url()
        raise HTTPFound(location)

    @staticmethod
    def escape_json(json_string):
        """Escape JSON strings passed to AngularJS controllers in templates"""
        replace_mapping = {
            "\'": "__apos__",
            '\\"': "__dquote__",
            "\\": "__bslash__",
        }
        for key, value in replace_mapping.items():
            json_string = json_string.replace(key, value)
        return json_string

    @staticmethod
    def dt_isoformat(dt_obj, tzone='UTC'):
        """Convert a timezone-unaware datetime object to tz-aware one and return it as an ISO-8601 formatted string"""
        return dt_obj.replace(tzinfo=tz.gettz(tzone)).isoformat()

    # these methods copied from euca2ools:bundleinstance.py and used with small changes
    @staticmethod
    def generate_default_policy(bucket, prefix, token=None):
        delta = timedelta(hours=24)
        expire_time = (datetime.utcnow() + delta).replace(microsecond=0)

        conditions = [{'acl': 'ec2-bundle-read'},
                      {'bucket': bucket},
                      ['starts-with', '$key', prefix]]
        if token is not None:
            conditions.append({'x-amz-security-token': token})
        policy = {'conditions': conditions,
                  'expiration': time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                              expire_time.timetuple())}
        policy_json = json.dumps(policy)
        return base64.b64encode(policy_json)

    @staticmethod
    def gen_policy_signature(policy, secret_key):
        # hmac cannot handle unicode
        secret_key = secret_key.encode('ascii', 'ignore')
        my_hmac = hmac.new(secret_key, digestmod=hashlib.sha1)
        my_hmac.update(policy)
        return base64.b64encode(my_hmac.digest())

    @staticmethod
    def has_role_access(request):
        return request.session['cloud_type'] == 'euca' and request.session['role_access']

    @staticmethod
    def generate_random_string(length=16):
        chars = string.letters + string.digits
        return ''.join(choice(chars) for i in range(length))

    @staticmethod
    def encode_unicode_dict(unicode_dict):
        encoded_dict = {}
        for k, v in unicode_dict.iteritems():
            if isinstance(k, unicode):
                k = k.encode('utf-8')
            elif isinstance(k, str):
                k.decode('utf-8')
            if isinstance(v, unicode):
                v = v.encode('utf-8')
            elif isinstance(v, str):
                v.decode('utf-8')
            encoded_dict[k] = v
        return encoded_dict


class TaggedItemView(BaseView):
    """Common view for items that have tags (e.g. security group)"""

    def __init__(self, request, **kwargs):
        super(TaggedItemView, self).__init__(request, **kwargs)
        self.tagged_obj = None
        self.conn = None

    def add_tags(self):
        if self.conn:
            tags_json = self.request.params.get('tags', '{}')
            tags_dict = self._normalize_tags(json.loads(tags_json))
            tags = {}
            for key, value in tags_dict.items():
                key = self.unescape_braces(key.strip())
                if not any([key.startswith('aws:'), key.startswith('euca:')]):
                    tags[key] = self.unescape_braces(value.strip())
            if tags:
                self.conn.create_tags([self.tagged_obj.id], tags)

    def remove_tags(self):
        if self.conn:
            tagkeys = []
            object_tags = self.tagged_obj.tags.keys()
            for tagkey in object_tags:
                if not any([tagkey.startswith('aws:'), tagkey.startswith('euca:')]):
                    tagkeys.append(tagkey)
            self.conn.delete_tags([self.tagged_obj.id], tagkeys)

    def update_tags(self):
        if self.tagged_obj is not None:
            self.remove_tags()
            self.add_tags()

    def update_name_tag(self, value):
        if self.tagged_obj is not None:
            if value != self.tagged_obj.tags.get('Name'):
                self.tagged_obj.remove_tag('Name')
                if value and not value.startswith('aws:'):
                    tag_value = self.unescape_braces(value)
                    self.tagged_obj.add_tag('Name', tag_value)

    def _normalize_tags(self, tags):
        if type(tags) is dict:
            return tags

        new_tags = {}
        for tag in tags:
            name, value = tag['name'], tag['value']
            new_tags[name] = value
        return new_tags

    @staticmethod
    def serialize_tags(tags):
        if tags is not None:
            serialized_tags = [{
                'name': key,
                'value': value
            } for key, value in tags.iteritems()]
        else:
            serialized_tags = []
        return BaseView.escape_json(json.dumps(serialized_tags))

    @staticmethod
    def get_display_name(resource, escapebraces=True):
        name = ''
        if resource:
            name_tag = resource.tags.get('Name', '')
            name = u"{0}{1}".format(
                name_tag if name_tag else resource.id,
                u" ({0})".format(resource.id) if name_tag else ''
            )
        if escapebraces:
            name = BaseView.escape_braces(name)
        return name

    @staticmethod
    def get_tags_display(tags, skip_name=True, wrap_width=0):
        """Return comma-separated list of tags as a string.
           Skips the 'Name' tag by default. no wrapping by default, otherwise honor wrap_width"""
        tags_array = []
        for key, val in tags.items():
            if not any([key.startswith('aws:'), key.startswith('euca:')]):
                template = u'{0}={1}'
                if skip_name and key == 'Name':
                    continue
                else:
                    text = template.format(key, val)
                    if wrap_width > 0:
                        if len(text) > wrap_width:
                            tags_array.append(textwrap.fill(text, wrap_width))
                        else:
                            tags_array.append(text)
                    else:
                        tags_array.append(text)
        return ', '.join(tags_array)


class BlockDeviceMappingItemView(BaseView):
    def __init__(self, request):
        super(BlockDeviceMappingItemView, self).__init__(request)
        self.conn = self.get_connection()
        self.request = request

    def get_image(self):
        from eucaconsole.views.images import ImageView
        image_id = self.request.params.get('image_id')
        if self.conn and image_id:
            with boto_error_handler(self.request):
                image = self.conn.get_image(image_id)
                if image:
                    platform = ImageView.get_platform(image)
                    image.platform_name = ImageView.get_platform_name(platform)
                return image
        return None

    def get_owner_choices(self):
        if self.cloud_type == 'aws':
            return AWS_IMAGE_OWNER_ALIAS_CHOICES
        return EUCA_IMAGE_OWNER_ALIAS_CHOICES

    def get_snapshot_choices(self):
        choices = [('', _(u'None'))]
        for snapshot in self.conn.get_all_snapshots(owner='self'):
            value = snapshot.id
            snapshot_name = snapshot.tags.get('Name')
            label = u'{id}{name} ({size} GB)'.format(
                id=snapshot.id,
                name=u' - {0}'.format(snapshot_name) if snapshot_name else '',
                size=snapshot.volume_size
            )
            choices.append((value, label))
        return sorted(choices)

    @staticmethod
    def get_block_device_map(bdmapping_json=None):
        """Parse block_device_mapping JSON and return a configured BlockDeviceMapping object
        Mapping JSON structure...
            {"/dev/sda":
                {"snapshot_id": "snap-23E93E09", "volume_type": null, "delete_on_termination": true, "size": 1}  }
        """
        if bdmapping_json:
            mapping = json.loads(bdmapping_json)
            if mapping:
                bdm = BlockDeviceMapping()
                for key, val in mapping.items():
                    device = BlockDeviceType()
                    if val.get('virtual_name') is not None and val.get('virtual_name').startswith('ephemeral'):
                        device.ephemeral_name = val.get('virtual_name')
                    else:
                        device.volume_type = 'standard'
                        device.snapshot_id = val.get('snapshot_id') or None
                        device.size = val.get('size')
                        device.delete_on_termination = val.get('delete_on_termination', False)
                    bdm[key] = device
                return bdm
            return None
        return None


class LandingPageView(BaseView):
    """Common view for landing pages

    :ivar filter_keys: List of strings to pass to client-side filtering engine
        The search box input (usually above the landing page datagrid) will match each property in the list against
        each item in the collection to do the filtering.  See $scope.searchFilterItems in landingpage.js
    :ivar sort_keys: List of strings to pass to client-side sorting engine
        The sorting dropdown (usually above the landing page datagrid) will display a sorting option for
        each item in the list.  See templates/macros.pt (id="sorting_controls")
    :ivar initial_sort_key: The initial sort key used for Angular-based client-side sorting.
        Prefix the key with a '-' to perform a descending sort (e.g. '-launch_time')
    :ivar items: The list of dicts to pass to the JSON renderer to display the collection of items.
    :ivar prefix: The prefix for each landing page, relevant to the section
        For example, prefix = '/instances' for Instances

    """
    def __init__(self, request, **kwargs):
        super(LandingPageView, self).__init__(request, **kwargs)
        self.filter_keys = []
        self.sort_keys = []
        self.initial_sort_key = ''
        self.items = []
        self.prefix = '/'

    def filter_items(self, items, ignore=None, autoscale=False):
        ignore = ignore or []  # Pass list of filters to ignore
        ignore.append('csrf_token')
        filtered_items = []
        if hasattr(self.request.params, 'dict_of_lists'):
            filter_params = self.request.params.dict_of_lists()
            for skip in ignore:
                if skip in filter_params.keys():
                    del filter_params[skip]
            if not filter_params:
                return items
            for item in items:
                matchedkey_count = 0
                for filter_key, filter_value in filter_params.items():
                    if filter_value and filter_value[0]:
                        if filter_key == 'tags':  # Special case to handle tags
                            if self.match_tags(item=item, tags=filter_value[0].split(','), autoscale=autoscale):
                                matchedkey_count += 1
                        elif hasattr(item, filter_key):
                            filterkey_val = getattr(item, filter_key, None)
                            if filterkey_val:
                                if isinstance(filterkey_val, list):
                                    for fitem in filterkey_val:
                                        if fitem in filter_value:
                                            matchedkey_count += 1
                                else:
                                    if filterkey_val in filter_value:
                                        matchedkey_count += 1
                            elif 'none' in filter_value or 'None' in filter_value:
                                # Handle the special case where 'filterkey_val' value is None
                                if filterkey_val is None:
                                    matchedkey_count += 1
                    else:
                        matchedkey_count += 1  # Handle empty param values
                if matchedkey_count == len(filter_params):
                    filtered_items.append(item)
        return filtered_items

    def match_tags(self, item=None, tags=None, autoscale=False):
        for tag in tags:
            tag = self.unescape_braces(tag.strip())
            if autoscale:  # autoscaling tags are a list of Tag boto.ec2.autoscale.tag.Tag objects
                if item.tags:
                    for as_tag in item.tags:
                        if as_tag and tag == as_tag.key or tag == as_tag.value:
                            return True
            else:  # Standard tags are a dict of key/value pairs
                if any([tag in item.tags.keys(), tag in item.tags.values()]):
                    return True
        return False

    def get_json_endpoint(self, route, path=False):
        return self.request.route_path(route) if path is False else route

    def get_redirect_location(self, route):
        location = u'{0}'.format(self.request.route_path(route))
        encoded_get_params = self.encode_unicode_dict(self.request.GET)
        if self.request.GET:
            location = u'{0}?{1}'.format(location, urlencode(encoded_get_params))
        return location


@notfound_view_config(renderer='../templates/notfound.pt')
def notfound_view(request):
    """404 Not Found view"""
    request.response.status = 404
    return dict()


@view_config(context=BotoServerError, permission=NO_PERMISSION_REQUIRED)
def conn_error(exc, request):
    """Generic handler for BotoServerError exceptions"""
    try:
        BaseView.handle_error(err=exc, request=request)
    except HTTPException as ex:
        return ex
    return


@contextmanager
def boto_error_handler(request, location=None, template="{0}"):
    try:
        yield
    except BotoServerError as err:
        BaseView.handle_error(err=err, request=request, location=location, template=template)


@view_config(route_name='file_download', request_method='POST')
def file_download(request):
    session = request.session
    if session.get('file_cache'):
        (filename, mime_type, contents) = session['file_cache']
        # Clean the session information regrading the new keypair
        del session['file_cache']
        response = Response(content_type=mime_type)
        response.body = str(contents)
        response.content_disposition = 'attachment; filename="{name}"'.format(name=filename)
        return response
    # no file found ...
    # this isn't handled on on client anyway, so we can return pretty much anything
    return Response(body='BaseView:file not found', status=500)

_magic_type = magic.Magic(mime=True)
_magic_type._thread_check = lambda: None
_magic_desc = magic.Magic(mime=False)
_magic_desc._thread_check = lambda: None
_magic_lock = threading.Lock()


def guess_mimetype_from_buffer(buffer, mime=False):
    with _magic_lock:
        if mime:
            return _magic_type.from_buffer(buffer)
        else:
            return _magic_desc.from_buffer(buffer)
