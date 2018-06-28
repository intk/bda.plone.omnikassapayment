from bda.plone.shop import message_factory as _

from zope import schema
from plone.supermodel import model
from zope.interface import Interface
from zope.interface import provider

from bda.plone.shop.interfaces import IShopSettingsProvider

#from zope.interface import Attribute


@provider(IShopSettingsProvider)
class IOmnikassaPaymentSettings(model.Schema):
    
    model.fieldset('omnikassa',label=_(u'Omnikassa', default=u'Omnikassa'),
        fields=[
        'omnikassa_server_url',
        'omnikassa_server_test_url',
        'omnikassa_secret_key',
        'omnikassa_merchant_id',
        'omnikassa_keyversion'
        ],
    )
                   
    omnikassa_server_url = schema.ASCIILine(title=_(u'omnikassa_server_url', default=u'Server url live'),
                 required=True
    )

    omnikassa_server_test_url = schema.ASCIILine(title=_(u'omnikassa_server_test_url', default=u'Search url test'),
               required=True
    )
    
    omnikassa_secret_key = schema.ASCIILine(title=_(u'omnikassa_secret_key', default=u'Secret key'),
               required=True
    )

    omnikassa_merchant_id = schema.ASCIILine(title=_(u'omnikassa_merchant_id', default=u'Merchant ID'),
               required=True
    )

    omnikassa_keyversion = schema.ASCIILine(title=_(u'omnikassa_keyversion', default=u'Key Version'),
               required=True
    )
    