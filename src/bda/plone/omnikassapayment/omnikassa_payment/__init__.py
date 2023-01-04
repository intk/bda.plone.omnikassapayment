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

import requests
import datetime
import base64

logger = logging.getLogger('bda.plone.payment')
_ = MessageFactory('bda.plone.payment')

CREATE_PAY_INIT_URL = "https://betalen.rabobank.nl/omnikassa-api/"

#REFRESH_TOKEN = "eyJraWQiOiIvKzdpVE5PL0FmSEhKN05kYmFWVGcyZTR6eXFjN3dYV3pFT08wcktoU0NJPSIsImFsZyI6IlJTMjU2In0.eyJta2lkIjoxMDE1MCwiZW52IjoiUyIsImV4cCI6NzI1ODAyODQwMH0.W4RFtP15ai3vWGESEPRElhLrmOPbI30krwRgEA-ECNo6gR0xngKDvUXevyRxuy4d7yqD8Bq71gC7fT8AFYWsnXdF7bDyuDtQyZF7l02NUMNA5fHkLZumbbZi167l5dNzUSNsQ0u_teeVSsitHmrbt_8wbMRskPdKiygfXZspUOwoEw_Fy5jIq3L1Pm4te9AgwvxYaXJe_c4Qhvy-sdUPaiTHBpwgeJlz1zIwUhLQpGIb4OL4SKG-nGLVRhJbBFEphA-fTpGIFtYdWxlRhh-SZeLoNqislXLEINQb6wWwvfEaxfJnE7-uh69INXBVI1VLTHlYguXX-Ld2Nnrk-t0uOg"
#REFRESH_TOKEN = "eyJraWQiOiI0cnd5d2k4RWh5TDc5bVc0eUpsUXhsUUNtQzVqSmZFam00VnZQQ2NDVzBzPSIsImFsZyI6IlJTMjU2In0.eyJta2lkIjoxMDE1MSwiZW52IjoiUCIsImV4cCI6MTU5NDMzMjAwMH0.haLt1HeUqIJ9XoFk36y5TIAh0BPTSOdzCBWFH8a2Isd_i63lVP3TE47CP1nXJm7bZGTs3r200eRGJkocN41gTF1bUuMx_bB34E1nCC95QP0sl9CGASIAuRlQje67gjBCvxwhTs0TtRiHzaDP8r9mJiXhqst6KCQC50N4iOjcDhx_vlArwjQ_BSWNKBlQVqgFvdrW6dUSTNnS_HbGjBSYHa2upMIm44gP9f7-ThD6obIflhIt7tHpCkSZAlhng0KJkfr-KpB53eRQQkBsAYKc-vFyGi81WZuCku6I-d6wCuZoRrpwDiOT8X2DB0YFOOQ6k_UBYE8psCE07AfGik5AVQ"
#SIGNING_KEY = base64.b64decode("4TD2QcxlGo9C8tUQLmOx1GOolrPCmNcItggZFfy/Cuo=")
REFRESH_TOKEN = "eyJraWQiOiI0cnd5d2k4RWh5TDc5bVc0eUpsUXhsUUNtQzVqSmZFam00VnZQQ2NDVzBzPSIsImFsZyI6IlJTMjU2In0.eyJta2lkIjo0NjY1MywiZW52IjoiUCIsImV4cCI6MTY2MDA4MjQwMH0.f_qp3pJDicsE5kjwbhHJLLo05Mk0FzNnhRcxHWZQe7Lyno7KOK_tRPNJW9nRq2PneLcJLEybSahSvaZ8vXU0PC6-2My-3ht30JrWU9LS1aZCVZPcBCTKdbwfRMLIMiov7izpuC8GIWLPxkWgtsjRRn3JOBcoPNXXtsZGGZYcCo8n3ow8x7X_QbXSzQQK2NO4ZxHDik4jqwoTSLaXA22CZTo9_mPWGRw41bJJJCGFvzPluJQN-3Sps_VypVBa3SYQb3GS9npwQdRaGysdj1rg85jJu7zR7IlDYEfuMCgAGFQ_UfBbjcm58U_mwwoHfIwqUaxCFFu-wdoUz7erUKxPbg"
#SIGNING_KEY = base64.b64decode("43TK6zsBU4io1b7p0hayzO0gKaGE1a2ebgE1dHjmaMc=")
SIGNING_KEY = base64.b64decode("9TRMKaRZcRX6yNnqepB9nj+N7BFFVahxA5+JPjaUPew=")

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


def get_access_token(url=CREATE_PAY_INIT_URL+'gatekeeper/refresh'):
    headers = {"Authorization":"Bearer "+REFRESH_TOKEN}
    url = requests.get(url, headers=headers)
    if url:
        response_json = url.json()
        token = response_json.get('token', '')
        return token
    else:
        return None

def perform_request(url, data=None):
    response = None
    if data:
        access_token = get_access_token()

        headers = {"Authorization":"Bearer "+access_token, 'Content-Type': 'application/json', 'user-agent': ''}
        json_data = json.dumps(data)
        response = requests.post(url, data=json.dumps(data), headers=headers)
        return response

    return response

def create_pay_init(merchantOrderId, amount, merchantReturnUrl, paymentBrand, paymentBrandForce, automaticResponseUrl):
    params = {}
    
    data = [
        ('timestamp', datetime.datetime.now().isoformat()),
        ('merchantOrderId', merchantOrderId),
        ('currency', 'EUR'),
        ('amount', amount),
        ('language', 'NL'),
        ('description', ''),
        ('merchantReturnURL', merchantReturnUrl),
        ('paymentBrand', 'IDEAL'),
        ('paymentBrandForce', 'FORCE_ALWAYS')
    ]

    for key,value in data:
        params[key] = value

    currency = params.pop('currency', None)
    total_amount = params.pop('amount', None)

    params['amount'] = {
        'amount': total_amount,
        'currency': currency
    }

    signer = OmnikassaSignature(data, 'sha512', SIGNING_KEY)
    params['signature'] = signer.signature()

    return perform_request(CREATE_PAY_INIT_URL+"order/server/api/order", params)

class OmnikassaPay(BrowserView):
    def __call__(self):
        base_url = self.context.absolute_url()
        order_uid = self.request.get('uid', '')
        payment_method = self.request.get('payment_method', '')

        try:
            site_url = api.portal.get().absolute_url()
            data = IPaymentData(self.context).data(order_uid)

            merchantOrderId = data['ordernumber']
            amount = str(data['amount'])
            merchantReturnUrl = "%s/@@omnikassa_payment_success" %(base_url)
            paymentBrand = 'IDEAL'
            paymentBrandForce = 'FORCE_ONCE'
            automaticResponseUrl = "%s/@@omnikassa_webhook" %(site_url)

            response = create_pay_init(merchantOrderId, amount, merchantReturnUrl, paymentBrand, paymentBrandForce, automaticResponseUrl)
            redirect_url = response.json().get('redirectUrl', '')

        except Exception, e:
            logger.error(u"Could not initialize payment: '%s'" % str(e))
            redirect_url = '%s/@@omnikassa_payment_failed?uid=%s' \
                % (base_url, order_uid)
        raise Redirect(redirect_url)


class OmnikassaWebhook(BrowserView):
    def __call__(self):
        data = self.request.form
        return True

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
        tickets = False
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
        ordernumber = data.get('order_id', '')
        status = data.get('status', '')
        req_signature = data.get('signature', '')

        if ordernumber:
            order_uid = IPaymentData(self.context).uid_for(ordernumber)

            if status not in ['COMPLETED']:
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
        signature_data = [
            ('order_id', ordernumber),
            ('status', status)
        ]

        signer = OmnikassaSignature(signature_data, 'sha512', SIGNING_KEY)
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

        if req_signature == signer.signature() or skip_payment:
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




    

        
