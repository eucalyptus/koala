# -*- coding: utf-8 -*-
# Copyright 2013-2017 Ent. Services Development Corporation LP
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
Pyramid views for Eucalyptus and Usage Reporting

"""
from collections import namedtuple
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

import io
import logging
import simplejson as json

from boto.exception import BotoServerError
from pyramid.response import Response
from pyramid.view import view_config
import pandas

from ..forms import ChoicesManager
from ..i18n import _
from ..views import BaseView, JSONResponse
from ..views.buckets import BucketContentsView, BucketDetailsView
from ..models.auth import RegionCache
from . import boto_error_handler


UNITS_LOOKUP = [
    {'hint': 'Bytes', 'units': 'GB'},
    {'hint': 'Alarm', 'units': 'Alarms'},
    {'hint': 'Requests', 'units': 'Requests'},
    {'hint': 'Hours', 'units': 'Hrs'},
    {'hint': 'Hrs', 'units': 'Hrs'},
    {'hint': 'Address', 'units': 'Addresses'},
    {'hint': 'Attempts', 'units': 'Attempts'},
    {'hint': 'VolumeUsage', 'units': 'GB-month'},
    {'hint': 'SnapshotUsage', 'units': 'GB-month'},
    {'hint': 'Usage', 'units': 'Units'},
]

DEFAULT_BILLING_POLICY = """
{{
  "Version": "2008-10-17",
  "Id": "Policy1335892530063",
  "Statement": [
    {{
      "Sid": "Stmt1335892150622",
      "Effect": "Allow",
      "Principal": {{
        "AWS": "arn:aws:iam::{billing_acct}:root"
      }},
      "Action": [
        "s3:GetBucketAcl",
        "s3:GetBucketPolicy"
      ],
      "Resource": "arn:aws:s3:::{bucket_name}"
    }},
    {{
      "Sid": "Stmt1335892526596",
      "Effect": "Allow",
      "Principal": {{
        "AWS": "arn:aws:iam::{billing_acct}:root"
      }},
      "Action": [
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::{bucket_name}/*"
    }}
  ]
}}
"""


class ReportingView(BaseView):
    def __init__(self, request):
        super(ReportingView, self).__init__(request)
        self.title_parts = [_(u'Reporting')]

    def is_reporting_configured(self):
        conn = self.get_connection(conn_type='reporting')
        ret = conn.view_billing()
        prefs = ret.get('billingSettings')
        return prefs.get('detailedBillingEnabled')

    @view_config(route_name='reporting_instance', renderer='../templates/reporting/instance_usage.pt')
    def reporting_instance_usage(self):
        vmtypes = ChoicesManager(self.get_connection()).instance_types(self.cloud_type)
        facets = [
            {'name': 'instance_type', 'label': _(u'Instance type'),
                'options': [{'key': choice[0], 'label':choice[1]} for choice in vmtypes]},
            {'name': 'platform', 'label': _(u'Platform'),
                'options': [{'key': 'linux', 'label': _(u'Linux')}, {'key': 'windows', 'label': _(u'Windows')}]}
        ]
        regions = RegionCache(None).regions()
        if len(regions) > 1:
            facets.append({'name': 'region', 'label': _(u'Region'),
                           'options': [{'key': choice[0], 'label':choice[1]} for choice in regions]})
        tags = self.get_connection().get_all_tags(filters={'resource-type': 'instance'})
        if len(tags) > 1:
            tag_names = sorted(set([tag.name for tag in tags]))
            facets.append({'name': 'tags', 'label': _(u'Tags'),
                           'options': [{'key': tag, 'label': tag} for tag in tag_names]})
        
        return dict(facets=BaseView.escape_json(json.dumps(facets)))

    @view_config(route_name='reporting', renderer='../templates/reporting/reporting.pt')
    def reports_landing(self):
        return dict(
            reporting_configured='true' if self.is_reporting_configured() else 'false'
        )


class ReportingAPIView(BaseView):
    """
    A view for reporting related XHR calls that carrys very little overhead
    """
    def __init__(self, request):
        super(ReportingAPIView, self).__init__(request)
        self.conn = self.get_connection(conn_type='reporting')

    @view_config(route_name='reporting_prefs', renderer='json', request_method='GET', xhr=True)
    def get_reporting_prefs(self):
        # use "ViewBilling" call to fetch billing configuration information
        ret = self.conn.view_billing()
        prefs = ret.get('billingSettings')
        ret = self.conn.view_account()
        acct_prefs = ret.get('accountSettings')
        ret = dict(
            enabled=prefs.get('detailedBillingEnabled'),
            bucketName=prefs.get('reportBucket') or '',
            activeTags=prefs.get('activeCostAllocationTags') or ['one'],
            inactiveTags=prefs.get('inactiveCostAllocationTags') or ['two', 'three', 'four'],
            userReportsEnabled=acct_prefs.get('userBillingAccess'),
        )
        return dict(results=ret)

    @view_config(route_name='reporting_prefs', renderer='json', request_method='PUT', xhr=True)
    def set_reporting_prefs(self):
        params = json.loads(self.request.body)
        csrf_token = params.get('csrf_token')
        if not self.is_csrf_valid(token=csrf_token):
            return JSONResponse(status=400, message="missing CSRF token")
        enabled = params.get('enabled')
        bucket_name = params.get('bucketName')
        tags = params.get('tags')
        self.log_request(_(u"Saving report preferences"))
        # fetch bucket policy
        s3_conn = self.get_connection(conn_type='s3')
        with boto_error_handler(self.request):
            portal_svc = self.get_connection(conn_type='admin').get_all_services(service_type='portal')
            if len(portal_svc) < 1 and len(portal_svc[0].accounts) < 1:
                logging.error('ERROR: Eucalyptus not returning account info with portal service!')
            billing_acct = portal_svc[0].accounts[0].account_number
            bucket = BucketContentsView.get_bucket(self.request, s3_conn, params.get('bucketName'))
            policy_doc = BucketDetailsView.get_bucket_policy(bucket)
            # if no policy, create required one
            if not policy_doc:
                bucket.set_policy(DEFAULT_BILLING_POLICY.format(
                    billing_acct=billing_acct, bucket_name=bucket.name
                ))
            # if existing policy, try using it. If it fails, add policy statements
            # use "ModifyBilling" to change billing configuration
            try:
                self.conn.modify_billing(enabled, bucket_name, tags)
            except BotoServerError as err:
                msg = json.loads(err.body)['error'][0]['message']
                if msg.find('bucket is not accessible') == -1:
                    # if not the error we're looking for
                    raise err
                # add statements and retry
                bucket.set_policy(self.update_bucket_policy(policy_doc, billing_acct, bucket.name))
                self.conn.modify_billing(enabled, bucket_name, tags)
            # use "ModifyAccount" to change report access
            user_reports_enabled = params.get('userReportsEnabled')
            self.conn.modify_account(user_reports_enabled)
            return dict(message=_("Successully updated reporting preferences."))

    @staticmethod
    def update_bucket_policy(existing_policy, billing_acct, bucket_name):
        policy = json.loads(existing_policy)
        new_policy_doc = DEFAULT_BILLING_POLICY.format(
            billing_acct=billing_acct, bucket_name=bucket_name
        )
        new_policy = json.loads(new_policy_doc)
        policy['Statement'].extend(new_policy['Statement'])
        return json.dumps(policy)

    @view_config(route_name='reporting_monthly_usage', renderer='json', request_method='GET', xhr=True)
    def get_reporting_monthly_usage(self):
        year = int(self.request.params.get('year'))
        month = int(self.request.params.get('month'))
        # use "ViewMontlyUsage" call to fetch usage information
        ret = self.conn.view_monthly_usage(year, month)
        csv = ret.get('data')
        data = pandas.read_csv(io.StringIO(csv), engine='c')
        if len(data) == 0:
            return dict(result=[])
        grouped = data.groupby(('ProductName', 'UsageType'))
        totals = grouped['UsageQuantity'].sum()
        totals_list = totals.to_frame().to_records().tolist()
        results = []
        service = ''
        for idx, rec in enumerate(totals_list):
            if service != rec[0]:
                results.append((rec[0],))
                service = rec[0]
            results.append((
                rec[0], rec[1],
                '{:0.8f}'.format(rec[2]).rstrip('0').rstrip('.'),
                self.units_from_details(rec[1])
            ))
        return dict(results=results)

    @view_config(route_name='reporting_monthly_usage', request_method='POST')
    def get_reporting_monthly_usage_file(self):
        if not self.is_csrf_valid():
            return JSONResponse(status=400, message="missing CSRF token")
        year = int(self.request.params.get('year'))
        month = int(self.request.params.get('month'))
        # use "ViewMontlyUsage" call to fetch usage information
        ret = self.conn.view_monthly_usage(year, month)
        filename = 'EucalyptusMonthlyUsage-{0}-{1}-{2}.csv'.format(
            self.request.session.get('account'),
            year,
            month
        )
        response = Response(content_type='text/csv')
        response.text = ret.get('data')
        response.content_disposition = 'attachment; filename="{name}"'.format(name=filename)
        response.cache_control = 'no-store'
        response.pragma = 'no-cache'
        return response

    @view_config(route_name='reporting_month_to_date_usage', renderer='json', request_method='GET', xhr=True)
    def get_reporting_month_to_date_usage(self):
        year = int(self.request.params.get('year'))
        month = int(self.request.params.get('month'))
        # use "ViewMontlyUsage" call to fetch usage information
        ret = self.conn.view_monthly_usage(year, month)
        csv = ret.get('data')
        data = pandas.read_csv(io.StringIO(csv), engine='c')
        # reduce to required columns
        data = data.filter(['ProductName', 'UsageType', 'UsageQuantity'])
        grouped = data.groupby(('ProductName', 'UsageType'))
        totals = grouped['UsageQuantity'].sum()
        totals_list = totals.to_frame().to_records().tolist()
        results = []
        service = ''
        for idx, rec in enumerate(totals_list):
            if service != rec[0]:
                results.append((rec[0],))
                service = rec[0]
            results.append((
                rec[0], rec[1],
                '{:0.8f}'.format(rec[2]).rstrip('0').rstrip('.'),
                self.units_from_details(rec[1])
            ))
        return dict(results=results)

    @view_config(route_name='reporting_service_usage', request_method='POST')
    def get_reporting_service_usage_file(self):
        if not self.is_csrf_valid():
            return JSONResponse(status=400, message="missing CSRF token")
        service = self.request.params.get('service')
        usage_type = self.request.params.get('usageType')
        granularity = self.request.params.get('granularity')
        dates = self.dates_from_params(self.request.params)
        # use "ViewUsage" call to fetch usage information
        ret = self.conn.view_usage(
            service, usage_type, 'all', dates.from_date, dates.to_date, report_granularity=granularity
        )
        filename = 'EucalyptusServiceUsage-{0}-{1}-{2}.csv'.format(
            self.request.session.get('account'),
            service,
            usage_type
        )
        response = Response(content_type='text/csv')
        response.text = ret.get('data')
        response.content_disposition = 'attachment; filename="{name}"'.format(name=filename)
        response.cache_control = 'no-store'
        response.pragma = 'no-cache'
        return response

    @view_config(route_name='reporting_instance_usage', renderer='json', request_method='GET', xhr=True)
    def get_reporting_instance_usage(self):
        conn = self.get_connection(conn_type='ec2reports')
        granularity = self.request.params.get('granularity')
        group_by = self.request.params.get('groupBy')
        dates = self.dates_from_params(self.request.params)
        filters = self.request.params.get('filters') or '[]'
        filters = json.loads(filters)
        with boto_error_handler(self.request):
            # use "ViewInstanceUsageReport" call to fetch usage information
            ret = conn.view_instance_usage_report(
                dates.from_date, dates.to_date, filters, group_by, report_granularity=granularity
            )
            csv = ret.get('usageReport')
            data = pandas.read_csv(io.StringIO(csv), engine='c')
            results = []
            for series in range(2, len(data.columns)):
                values = []
                for item in data.itertuples():
                    values.append({'x': item[1], 'y': item[series + 1]})
                results.append({'key': data.columns[series], 'values': values})
            return dict(results=results)

    @view_config(route_name='reporting_instance_usage', request_method='POST')
    def get_reporting_instance_usage_file(self):
        conn = self.get_connection(conn_type='ec2reports')
        if not self.is_csrf_valid():
            return JSONResponse(status=400, message="missing CSRF token")
        granularity = self.request.params.get('granularity')
        group_by = self.request.params.get('groupBy')
        dates = self.dates_from_params(self.request.params)
        filters = self.request.params.get('filters') or '[]'
        filters = json.loads(filters)
        with boto_error_handler(self.request):
            # use "ViewInstanceUsageReport" call to fetch usage information
            ret = conn.view_instance_usage_report(
                dates.from_date, dates.to_date, filters, group_by, report_granularity=granularity
            )
            filename = 'EucalyptusInstanceUsage-{0}-{1}-{2}.csv'.format(
                self.request.session.get('account'),
                dates.from_date,
                dates.to_date
            )
            response = Response(content_type='text/csv')
            response.text = ret.get('usageReport')
            response.content_disposition = 'attachment; filename="{name}"'.format(name=filename)
            response.cache_control = 'no-store'
            response.pragma = 'no-cache'
            return response

    @staticmethod
    def units_from_details(details):
        # ascertain unit type
        for unit in UNITS_LOOKUP:
            if unit['hint'] in details:
                return unit['units']
        return ''

    @staticmethod
    def dates_from_params(params):
        time_period = params.get('timePeriod')
        to_date = datetime.utcnow()
        if time_period == 'lastWeek':
            from_date = to_date - relativedelta(days=7)
        elif time_period == 'lastMonth':
            from_date = to_date - relativedelta(months=1)
        else:
            from_date = datetime.strptime(params.get('fromTime'), '%Y/%m/%d') + timedelta(milliseconds=1)
            to_date = datetime.strptime(params.get('toTime'), '%Y/%m/%d') + timedelta(milliseconds=1)
        
        ret = namedtuple('ret', 'from_date to_date')
        return ret(from_date=from_date, to_date=to_date)
