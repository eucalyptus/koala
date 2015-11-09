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
Panels (reusable, parameterized template snippets) used across the app.

See http://docs.pylonsproject.org/projects/pyramid_layout/en/latest/layouts.html#using-panels

"""
from operator import itemgetter

import simplejson as json

from boto.s3.bucket import Bucket
from boto.s3.key import Key

from wtforms.fields import IntegerField, BooleanField
from wtforms.validators import Length
from pyramid_layout.panel import panel_config

from ..constants.securitygroups import RULE_PROTOCOL_CHOICES, RULE_ICMP_CHOICES
from ..i18n import _
from ..views import BaseView
from ..views.buckets import DELIMITER, BucketItemDetailsView


def get_object_type(bucket_object):
    """
    Detect object type
    :return: object type (one of 'bucket', 'folder', 'object')
    """
    if bucket_object is None:
        return ''
    object_type = 'bucket' if isinstance(bucket_object, Bucket) else 'object'
    if object_type == 'object' and bucket_object.size == 0 and DELIMITER in bucket_object.name:
        object_type = 'folder'
    return object_type


@panel_config('top_nav', renderer='../templates/panels/top_nav.pt')
def top_nav(context, request, off_canvas=False):
    """ Top nav bar panel"""
    return dict(
        off_canvas=off_canvas
    )


@panel_config('form_field', renderer='../templates/panels/form_field_row.pt')
def form_field_row(context, request, field=None, reverse=False, leftcol_width=4, rightcol_width=8,
                   leftcol_width_large=2, rightcol_width_large=10,
                   inline=True, stack_label=False, ng_attrs=None, **kwargs):
    """ Widget for a singe form field row.
        The left/right column widths are Zurb Foundation grid units.
            e.g. leftcol_width=3 would set column for labels with a wrapper of <div class="small-3 columns">...</div>
        Pass any HTML attributes to this widget as keyword arguments.
            e.g. ${panel('form_field', field=the_field)}
    """
    html_attrs = {}
    error_msg = kwargs.get('error_msg') or getattr(field, 'error_msg', None)

    # Add required="required" HTML attribute to form field if any "required" validators
    if field.flags.required:
        html_attrs['required'] = 'required'

    # Add appropriate HTML attributes based on validators
    for validator in field.validators:
        # Add maxlength="..." HTML attribute to form field if any length validators
        # If we have multiple Length validators, the last one wins
        if isinstance(validator, Length):
            html_attrs['maxlength'] = validator.max

    # Add HTML attributes based on field type (e.g. IntegerField)
    if isinstance(field, IntegerField):
        html_attrs['pattern'] = 'integer'  # Uses Zurb Foundation Abide's 'integer' named pattern
        html_attrs['type'] = 'number'  # Use input type="number" for IntegerField inputs
        html_attrs['min'] = kwargs.get('min', 0)

    checkbox = False
    if isinstance(field, BooleanField):
        checkbox = True

    # Add any passed kwargs to field's HTML attributes
    for key, value in kwargs.items():
        html_attrs[key] = value

    # Add AngularJS attributes
    # A bit of a hack since we can't pass ng-model='foo' to the form_field panel
    # So instead we pass ng_attrs={'model': 'foo'} to the form field
    # e.g. ${panel('form_field', field=volume_form['snapshot_id'], ng_attrs={'model': 'snapshot_id'}, **html_attrs)}
    if ng_attrs:
        for ngkey, ngvalue in ng_attrs.items():
            html_attrs[u'ng-{0}'.format(ngkey)] = ngvalue

    if stack_label:
        leftcol_width = 0
        leftcol_width_large = 0
        rightcol_width_large = 12

    return dict(
        field=field, error_msg=error_msg, html_attrs=html_attrs, inline=inline, checkbox=checkbox,
        leftcol_width=leftcol_width, rightcol_width=rightcol_width,
        leftcol_width_large=leftcol_width_large, rightcol_width_large=rightcol_width_large,
        reverse=reverse, stack_label=stack_label
    )


@panel_config('tag_editor', renderer='../templates/panels/tag_editor.pt')
def tag_editor(context, request, tags=None, leftcol_width=4, rightcol_width=8, show_name_tag=True):
    """ Tag editor panel.
        Usage example (in Chameleon template): ${panel('tag_editor', tags=security_group.tags)}
    """
    tags = tags or {}
    controller_options_json = BaseView.escape_json(json.dumps({
        'tags': tags,
        'show_name_tag': show_name_tag,
    }))
    return dict(
        controller_options_json=controller_options_json,
        show_name_tag=show_name_tag,
        leftcol_width=leftcol_width,
        rightcol_width=rightcol_width,
    )


@panel_config('user_editor', renderer='../templates/panels/user_editor.pt')
def user_editor(context, request, leftcol_width=4, rightcol_width=8, help_text=None, show_admin=False):
    """ User editor panel.
        Usage example (in Chameleon template): ${panel('user_editor')}
    """
    return dict(leftcol_width=leftcol_width, rightcol_width=rightcol_width, help_text=help_text, show_admin=show_admin)


@panel_config('policy_list', renderer='../templates/panels/policy_list.pt')
def policy_list(context, request, policies_url=None, policy_url=None, remove_url=None, update_url=None, add_url=None):
    """ User list panel.
        Usage example (in Chameleon template): ${panel('policy_list')}
    """
    return dict(policies_url=policies_url, policy_url=policy_url,
                remove_url=remove_url, update_url=update_url, add_url=add_url)


@panel_config('autoscale_tag_editor', renderer='../templates/panels/autoscale_tag_editor.pt')
def autoscale_tag_editor(context, request, tags=None, leftcol_width=2, rightcol_width=10):
    """ Tag editor panel for Scaling Groups.
        Usage example (in Chameleon template): ${panel('autoscale_tag_editor', tags=scaling_group.tags)}
    """
    tags = tags or []
    tags_list = []
    for tag in tags:
        tags_list.append(dict(
            name=tag.key,
            value=tag.value,
            propagate_at_launch=tag.propagate_at_launch,
        ))
    controller_options_json = BaseView.escape_json(json.dumps({
        'tags_list': tags_list,
    }))
    return dict(
        controller_options_json=controller_options_json,
        leftcol_width=leftcol_width,
        rightcol_width=rightcol_width,
    )


@panel_config('securitygroup_rules', renderer='../templates/panels/securitygroup_rules.pt')
def securitygroup_rules(context, request, rules=None, rules_egress=None, leftcol_width=3, rightcol_width=9):
    """ Security group rules panel.
        Usage example (in Chameleon template): ${panel('securitygroup_rules', rules=security_group.rules)}
    """
    rules = rules or []
    rules_list = []
    for rule in rules:
        grants = []
        for g in rule.grants:
            grants.append(
                dict(name=BaseView.escape_braces(g.name), owner_id=g.owner_id, group_id=g.group_id, cidr_ip=g.cidr_ip)
            )
        rules_list.append(dict(
            ip_protocol=rule.ip_protocol,
            from_port=rule.from_port,
            to_port=rule.to_port,
            grants=grants,
        ))
    rules_egress = rules_egress or []
    rules_egress_list = []
    for rule in rules_egress:
        grants = [
            dict(name=g.name, owner_id=g.owner_id, group_id=g.group_id, cidr_ip=g.cidr_ip) for g in rule.grants
        ]
        rules_egress_list.append(dict(
            ip_protocol=rule.ip_protocol,
            from_port=rule.from_port,
            to_port=rule.to_port,
            grants=grants,
        ))

    # Sort rules and choices
    rules_sorted = sorted(rules_list, key=itemgetter('from_port'))
    rules_egress_sorted = sorted(rules_egress_list, key=itemgetter('from_port'))
    icmp_choices_sorted = sorted(RULE_ICMP_CHOICES, key=lambda tup: tup[1])
    controller_options_json = BaseView.escape_json(json.dumps({
        'rules_array': rules_sorted,
        'rules_egress_array': rules_egress_sorted,
        'json_endpoint': request.route_path('securitygroups_json') + "?incl_elb_groups=",
        'protocols_json_endpoint': request.route_path('internet_protocols_json'),
    }))
    remote_addr = BaseView.get_remote_addr(request)

    return dict(
        protocol_choices=RULE_PROTOCOL_CHOICES,
        icmp_choices=icmp_choices_sorted,
        controller_options_json=controller_options_json,
        remote_addr=remote_addr,
        leftcol_width=leftcol_width,
        rightcol_width=rightcol_width,
    )


@panel_config('securitygroup_rules_preview', renderer='../templates/panels/securitygroup_rules_preview.pt')
def securitygroup_rules_preview(context, request, leftcol_width=3, rightcol_width=9,
                                leftcol_width_large=2, rightcol_width_large=10):
    """ Security group rules preview, used in Launch Instance and Create Launch Configuration wizards.
    """
    return dict(
        leftcol_width=leftcol_width,
        rightcol_width=rightcol_width,
        leftcol_width_large=leftcol_width_large,
        rightcol_width_large=rightcol_width_large,
    )


@panel_config('bdmapping_editor', renderer='../templates/panels/bdmapping_editor.pt')
def bdmapping_editor(context, request, image=None, instance=None, volumes=None,
                     launch_config=None, snapshot_choices=None, read_only=False, disable_dot=False, add_hr=False):
    """ Block device mapping editor (e.g. for Launch Instance page).
        Usage example (in Chameleon template): ${panel('bdmapping_editor', image=image, snapshot_choices=choices)}
    """
    snapshot_choices = snapshot_choices or []
    bdm_dict = {}
    if image is not None:
        bdm_object = image.block_device_mapping
        for key, device in bdm_object.items():
            bdm_dict[key] = dict(
                is_root=True if get_root_device_name(image) == key else False,
                virtual_name=device.ephemeral_name,
                snapshot_id=device.snapshot_id,
                size=device.size,
                delete_on_termination=device.delete_on_termination,
            )
    if instance is not None and volumes is not None:
        bdm_map = instance.block_device_mapping or []
        for device_name in bdm_map:
            bdm = bdm_map[device_name]
            if device_name in bdm_dict.keys():
                continue
            volume = [vol for vol in volumes if vol.id == bdm.volume_id][0]
            bdm_dict[device_name] = dict(
                is_root=True if instance.root_device_name == device_name else False,
                virtual_name=bdm.ephemeral_name,
                snapshot_id=getattr(volume, 'snapshot_id', None),
                size=getattr(volume, 'size', None),
                delete_on_termination=bdm.delete_on_termination,
            )
    if launch_config is not None:
        bdm_list = launch_config.block_device_mappings or []
        for bdm in bdm_list:
            if bdm.device_name in bdm_dict.keys():
                continue
            ebs = bdm.ebs
            bdm_dict[bdm.device_name] = dict(
                is_root=False,  # because we can't redefine root in a launch config
                virtual_name=bdm.virtual_name,
                snapshot_id=getattr(ebs, 'snapshot_id', None),
                size=getattr(ebs, 'volume_size', None),
                delete_on_termination=True,
            )
    controller_options_json = BaseView.escape_json(json.dumps({
        'bd_mapping': bdm_dict,
        'disable_dot': disable_dot,
        'snapshot_size_json_endpoint': request.route_path('snapshot_size_json', id='_id_'),
    }))
    return dict(
        image=image,
        snapshot_choices=snapshot_choices,
        controller_options_json=controller_options_json,
        read_only=read_only,
        disable_dot=disable_dot,
        add_hr=add_hr
    )


def get_root_device_name(img):
    return img.root_device_name.replace('&#x2f;', '/').replace(
        '&#x2f;', '/') if img.root_device_name is not None else '/dev/sda'


@panel_config('image_picker', renderer='../templates/panels/image_picker.pt')
def image_picker(context, request, image=None, filters_form=None,
                 maxheight='800px', owner_choices=None, prefix_route='instance_create'):
    """ Reusable Image picker widget (e.g. for Launch Instance page, step 1).
        Usage example (in Chameleon template): ${panel('image_picker')}
    """
    controller_options_json = BaseView.escape_json(json.dumps({
        'cloud_type': request.session.get('cloud_type'),
        'images_json_endpoint': request.route_path('images_json')
    }))
    search_facets = filters_form.facets if filters_form is not None else []
    return dict(
        image=image,
        search_facets=BaseView.escape_json(json.dumps(search_facets)),
        filter_keys=[],  # defined within image picker javascript
        maxheight=maxheight,
        owner_choices=owner_choices,
        prefix_route=prefix_route,
        controller_options_json=controller_options_json,
    )


@panel_config('policy_generator', renderer='../templates/policies/policy_generator.pt')
def policy_generator(context, request, policy_actions=None, create_form=None, resource_choices=None, resource_type=''):
    """IAM Policy generator"""
    policy_actions = policy_actions or {}
    resource_choices = resource_choices or {}
    return dict(
        policy_actions=policy_actions,
        resource_type=resource_type,
        create_form=create_form,
        instance_choices=resource_choices.get('instances'),
        image_choices=resource_choices.get('images'),
        volume_choices=resource_choices.get('volumes'),
        snapshot_choices=resource_choices.get('snapshots'),
        security_group_choices=resource_choices.get('security_groups'),
        key_pair_choices=resource_choices.get('key_pairs'),
        vm_type_choices=resource_choices.get('vm_types'),
        availability_zone_choices=resource_choices.get('availability_zones'),
    )


@panel_config('quotas_panel', renderer='../templates/users/quotas.pt')
def quotas_panel(context, request, quota_form=None, quota_err=None, in_user=True):
    """quota form for 2 different user pages."""
    return dict(
        quota_form=quota_form,
        quota_err=quota_err,
        in_user=in_user,
    )


@panel_config('securitygroup_rules_landingpage', renderer='../templates/panels/securitygroup_rules_landingpage.pt')
def securitygroup_rules_landingpage(context, request, tile_view=False):
    return dict(
        tile_view=tile_view,
    )


@panel_config('securitygroup_rules_egress_landingpage',
              renderer='../templates/panels/securitygroup_rules_egress_landingpage.pt')
def securitygroup_rules_egress_landingpage(context, request, tile_view=False):
    return dict(
        tile_view=tile_view,
    )


@panel_config('s3_sharing_panel', renderer='../templates/panels/s3_sharing_panel.pt')
def s3_sharing_panel(context, request, bucket_object=None, sharing_form=None, show_caution=False):
    grants_list = []
    if bucket_object is not None:
        for grant in bucket_object.get_acl().acl.grants:
            grants_list.append(dict(
                id=grant.id,
                display_name=grant.display_name,
                permission=grant.permission,
                grant_type=grant.type,
                uri=grant.uri,
            ))
    grantee_choices = [
        ('http://acs.amazonaws.com/groups/global/AllUsers', _(u'Anyone with the URL')),
        ('http://acs.amazonaws.com/groups/global/AuthenticatedUsers', _(u'Authenticated users')),
    ]
    if isinstance(bucket_object, Key):
        bucket_owner_id = bucket_object.bucket.get_acl().owner.id
        grantee_choices.append(
            (bucket_owner_id, _('Bucket owner'))
        )
    controller_options_json = BaseView.escape_json(json.dumps({
        'grants': grants_list,
        'create_option_text': _(u'Press enter to select')
    }))
    return dict(
        bucket_object=bucket_object,
        object_type=get_object_type(bucket_object),
        sharing_form=sharing_form,
        show_caution=show_caution,
        grantee_choices=grantee_choices,
        account_placeholder_text=_(u'Select or type to enter account/user'),
        controller_options_json=controller_options_json,
    )


@panel_config('s3_metadata_editor', renderer='../templates/panels/s3_metadata_editor.pt')
def s3_metadata_editor(context, request, bucket_object=None, metadata_form=None):
    """ S3 object metadata editor panel"""
    metadata = BucketItemDetailsView.get_extended_metadata(bucket_object)
    metadata_json = BaseView.escape_json(json.dumps(metadata))
    return dict(
        metadata_json=metadata_json,
        metadata_form=metadata_form,
        metadata_key_create_option_text=_(u'Add Metadata'),
        metadata_key_no_results_text=_(u'Click below to add the new key'),
    )


@panel_config('elb_listener_editor', renderer='../templates/panels/elb_listener_editor.pt')
def elb_listener_editor(context, request, listener_list=None, protocol_list=None, elb_security_policy=None):
    """ ELB listener editor panel """
    listener_list = listener_list or {}
    controller_options_json = BaseView.escape_json(json.dumps({
        'listener_list': listener_list,
        'protocol_list': protocol_list,
        'certificate_required_notice': _(u'Certificate is required'),
    }))
    return dict(
        controller_options_json=controller_options_json,
        elb_security_policy=elb_security_policy,
    )
