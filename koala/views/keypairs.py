# -*- coding: utf-8 -*-
"""
Pyramid views for Eucalyptus and AWS key pairs

"""
from pyramid.i18n import TranslationString as _
from pyramid.view import view_config

from ..forms.keypairs import KeyPairForm
from ..models import Notification
from ..views import BaseView, LandingPageView

class KeyPairsView(LandingPageView):
    def __init__(self, request):
        super(KeyPairsView, self).__init__(request)
        self.initial_sort_key = 'name'
        self.prefix = '/keypairs'
        self.display_type = self.request.params.get('display', 'tableview')  # Set tableview as default

    def get_items(self):
        conn = self.get_connection()
        return conn.get_all_key_pairs() if conn else []

    @view_config(route_name='keypairs', renderer='../templates/keypairs/keypairs.pt')
    def keypairs_landing(self):
        json_items_endpoint = self.request.route_url('keypairs_json')
        # filter_keys are passed to client-side filtering in search box
        self.filter_keys = ['name', 'fingerprint']
        # sort_keys are passed to sorting drop-down
        self.sort_keys = [
            dict(key='name', name=_(u'Name')),
            dict(key='fingerprint', name=_(u'Fingerprint')),
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

    @view_config(route_name='keypairs_json', renderer='json', request_method='GET')
    def keypairs_json(self):
        keypairs = []
        for keypair in self.get_items():
            keypairs.append(dict(
                name=keypair.name,
                fingerprint=keypair.fingerprint,
            ))
        return dict(results=keypairs)


class KeyPairView(BaseView):
    """Views for single Key Pair"""
    TEMPLATE = '../templates/keypairs/keypair_view.pt'

    def __init__(self, request):
        super(KeyPairView, self).__init__(request)
        self.conn = self.get_connection()
        self.keypair = self.get_keypair()
        self.keypair_form = KeyPairForm(self.request, keypair=self.keypair, formdata=self.request.params or None)
        print "INIT COMPLETE"

    def get_keypair(self):
        keypair_param = self.request.matchdict.get('id')
        keypairs_param = [keypair_param]
        keypairs = self.conn.get_all_key_pairs(keynames=keypairs_param)
        keypair = keypairs[0] if keypairs else None
        return keypair 

    @view_config(route_name='keypair_view', renderer=TEMPLATE)
    def keypair_view(self):
        return dict(
            keypair=self.keypair,
        )

    @view_config(route_name='keypair_create', request_method='POST', renderer=TEMPLATE)
    def keypair_create(self):
        """
        if self.keypair_form.validate():
            name = self.request.params.get('name')
            new_keypair = self.conn.create_key_pair(name)
            location = self.request.route_url('keypairs')
            msg = _(u'Successfully created key pair {keypair}')
            notification_msg = msg.format(keypair=name)
            self.request.session.flash(notification_msg, queue=Notification.SUCCESS)
            return HTTPFound(location=location)
        """
        print "HERELO"
        return dict(
            keypair=self.keypair,
            keypair_form=self.keypair_form,
            #keypair_names=self.get_security_group_names(),
        )



