#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib
import urllib2
import urlparse
import logging
from lxml import etree
from zExceptions import Redirect
from zope.i18nmessageid import MessageFactory
from Products.Five import BrowserView
from Products.CMFCore.utils import getToolByName
from bda.plone.payment.interfaces import IPaymentData

from bda.plone.shop.interfaces import IShopSettings
from zope.component import getUtility
from plone.registry.interfaces import IRegistry
from zope.i18n.interfaces import IUserPreferredLanguages
from status_codes import get_status_category, SUCCESS_STATUS
from bda.plone.orders import interfaces as ifaces
from bda.plone.orders.common import OrderData
from bda.plone.orders.common import get_order
from bda.plone.orders.common import get_orders_soup

from bda.plone.payment import (
    Payment,
    Payments,
)

from ZTUtils import make_query
from bda.plone.orders.common import get_order

from security import OmnikassaSignature
import transaction
import json

from plone.app.uuid.utils import uuidToCatalogBrain
from plone import api

logger = logging.getLogger('bda.plone.payment')
_ = MessageFactory('bda.plone.payment')

CREATE_PAY_INIT_URL = "https://payment-webinit.simu.omnikassa.rabobank.nl/paymentServlet"
SECRET_KEY = ""
MERCHANT_ID = ""
KEYVERSION = 

class OmnikassaPayment(Payment):
    pid = 'omnikassa_payment'
    label = _('omnikassa_payment', 'Omnikassa Payment')
    
    def init_url(self, uid, payment_method=''):
        return '%s/@@omnikassa_payment?uid=%s&payment_method=%s' % (self.context.absolute_url(), uid, payment_method)

class OmnikassaError(Exception):
    """Raised if SIX payment return an error.
    """

def shopmaster_mail(context):
    try:
        props = getToolByName(context, 'portal_properties')
        return props.site_properties.email_from_address
    except:
        return ""

def perform_request(url, params=None):
    if params:
        query = urllib.urlencode(params)
        url = '%s?%s' % (url, query)
    return url

def create_pay_init(secretKey, merchantID, keyVersion, currencyCode, amount, transactionReference, orderId, normalReturnUrl, automaticResponseUrl):

    paymentMeanBrandList = ['ideal']

    params = {
        'Data': {
            'currencyCode': currencyCode,
            'merchantId': merchantID,
            'keyVersion': keyVersion,
            'amount': amount,
            'transactionReference': transactionReference,
            'orderId': orderId,
            'normalReturnUrl': normalReturnUrl,
            'automaticResponseUrl': automaticResponseUrl,
            'paymentMeanBrandList': paymentMeanBrandList
        },
        'interfaceVersion': "HP_1.0"
    }

    signer = OmnikassaSignature(params['Data'], 'sha256', secretKey)
    params['Seal'] = signer.signature()

    return perform_request(CREATE_PAY_INIT_URL, params)

class OmnikassaPay(BrowserView):
    def __call__(self):
        base_url = self.context.absolute_url()
        order_uid = self.request.get('uid', '')
        payment_method = self.request.get('payment_method', '')

        try:
            site_url = api.portal.get().absolute_url()
            data = IPaymentData(self.context).data(order_uid)
            secretKey = SECRET_KEY
            merchantID = MERCHANT_ID
            keyVersion = KEYVERSION
            currencyCode = 978
            amount = data['amount']
            transactionReference = data['ordernumber']
            orderId = data['ordernumber']
            normalReturnUrl = "%s/@@omnikassa_payment" %(base_url)
            automaticResponseUrl = "%s/@@omnikassa_webhook" %(site_url)
            redirect_url = create_pay_init(secretKey, merchantID, keyVersion, currencyCode, amount, transactionReference, orderId, normalReturnUrl, automaticResponseUrl)

            print "REDIRECT URL:"
            print redirect_url

        except Exception, e:
            logger.error(u"Could not initialize payment: '%s'" % str(e))
            redirect_url = '%s/@@omnikassa_payment_failed?uid=%s' \
                % (base_url, order_uid)
        raise Redirect(redirect_url)


class OmnikassaPaySuccess(BrowserView):

    def get_header_image(self, ticket):
        if ticket:
            folder = self.context
            if folder.portal_type in ["Folder", "Event"]:
                if folder.portal_type == "Event":
                    uuid = folder.UID()
                    brain = uuidToCatalogBrain(uuid)
                    if brain:
                        leadmedia = getattr(brain, 'leadMedia', None)
                        if leadmedia:
                            image = uuidToCatalogBrain(leadmedia)
                            if hasattr(image, 'getURL'):
                                url = image.getURL()
                                scale_url = "%s/%s" %(url, "@@images/image/large")
                                return scale_url
                else:
                    contents = folder.getFolderContents({"portal_type": "Image", "Title":"tickets-header"})
                    if len(contents) > 0:
                        image = contents[0]
                        url = image.getURL()
                        scale_url = "%s/%s" %(url, "@@images/image/large")
                        return scale_url
        else:
            brains = self.context.portal_catalog(Title="webwinkel-header", portal_type="Image")
            if len(brains) > 0:
                brain = brains[0]
                if brain.portal_type == "Image":
                    url = brain.getURL()
                    scale_url = "%s/%s" %(url, "@@images/image/large")
                    return scale_url

            return ""


    def verify(self):
        #
        # Get Payment details
        #
        # Get order
        order = None
        tickets = is_context_ticket(self.context)
        skip_payment = False

        order_data = {
            "order_id": "",
            "total": "",
            "shipping": "",
            "currency": "",
            "tax": "",
            "ticket": tickets,
            "download_link": None,
            "verified": False
        }

        data = self.request.form
        ordernumber = data.get('orderID', '')
        if ordernumber:
            order_uid = IPaymentData(self.context).uid_for(ordernumber)
            if get_status_category(int(data['STATUS'])) != SUCCESS_STATUS:
                return order_data
        else:
            order_uid = data.get('order_uid', '')
            if order_uid:
                try:
                    order = OrderData(self.context, uid=order_uid)
                except:
                    order = None
                if order:
                    if order.total > 0:
                        return order_data
                    else:
                        skip_payment = True
                else:
                    return order_data
            else:
                return order_data
        
        #
        # SHA passphrase verification
        #
        signer = OmnikassaSignature(data, 'sha512', SHA_OUT_PASSWORD)
        payment = Payments(self.context).get('omnikassa_payment')
        
        if not order:
            try:
                order = OrderData(self.context, uid=order_uid)
            except:
                order = None

        # Check if order exists   
        if order_uid != None and order != None:
            order = OrderData(self.context, uid=order_uid)
            order_nr = order.order.attrs['ordernumber']

            # Build order data
            order_data = {  
                "ordernumber": str(order_nr),
                "order_id": str(order_uid),
                "total": str(order.total),
                "shipping": str(order.shipping),
                "currency": str(order.currency),
                "tax": str(order.vat),
                "ticket": tickets,
                "download_link": None,
                "verified": False,
                "already_sent":False,
                "bookings":json.dumps([])
            }

            order_bookings = []
           
            for booking in order.bookings:
                try:
                    booking_uid = booking.attrs['buyable_uid']
                    item_number = booking.attrs['item_number']

                    if item_number:
                        sku = str(item_number)
                    else:
                        sku = str(booking_uid)

                    item_category = "Product" # Default category
                    if tickets:
                        item_category = "E-Ticket"

                    order_bookings.append({
                        'id':sku,
                        'price': str(float(booking.attrs['net'])),
                        'name': str(booking.attrs['title']),
                        'category': item_category,
                        'quantity': int(booking.attrs['buyable_count']),
                    })
                except:
                    pass

            try:
                order_data['bookings'] = json.dumps(order_bookings)
            except:
                # Invalid JSON format
                order_data['bookings'] = json.dumps([])

            if tickets:
                base_url = self.context.portal_url()
                params = "?order_id=%s" %(str(order_uid))
                download_as_pdf_link = "%s/download_as_pdf?page_url=%s/tickets/etickets%s" %(base_url, base_url, params)
                order_data['download_link'] = download_as_pdf_link

        else:
            # Order doesn't exist in the database
            # return blank ticket
            order_data = {
                "order_id": "",
                "total": "",
                "shipping": "",
                "currency": "",
                "tax": "",
                "ticket": tickets,
                "download_link": None,
                "verified": False
            }
            return order_data

        shasign = data.get('SHASIGN', '')
        if shasign == signer.signature() or skip_payment:
            order_data['verified'] = True
            order = OrderData(self.context, uid=order_uid)
            order.salaried = ifaces.SALARIED_YES
            if order.order.attrs['email_sent'] != 'yes':
                order.order.attrs['email_sent'] = 'yes'
                orders_soup = get_orders_soup(self.context)
                order_record = order.order
                orders_soup.reindex(records=[order_record])
                transaction.get().commit()
                if not skip_payment:
                    payment.succeed(self.context, order_uid)
                return order_data
            else:
                return order_data
        else:
            payment.failed(self.context, order_uid)
            return order_data

    @property
    def shopmaster_mail(self):
        return shopmaster_mail(self.context)
    

class OmnikassaPayFailed(BrowserView):
    def finalize(self):
        return True

    def shopmaster_mail(self):
        return shopmaster_mail(self.context)




    

        
