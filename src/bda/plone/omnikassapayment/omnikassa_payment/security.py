import hashlib, logging
import hmac
import base64

log = logging.getLogger('bda.plone.payment')

class OmnikassaSignature(object):
    def __init__(self, data, hash_method, secret):
        assert hash_method in ['sha1', 'sha256', 'sha512']
        assert str(secret)

        self.data = data
        self.hash_method = hash_method
        self.secret = secret

    def _sort_data(self, data):
        # This code uppercases two times and is not well readable
        """sorted_data = [(k, v) for k, v in data.items() \
                       if self._filter_data(k, v)]
        
        sorted_data.sort(key=lambda x: x, reverse=False)"""
        return data

    def _filter_data(self, k, v):
        valid = True
        if v == '':
            valid = False
        if k == 'signature':
            valid = False
        return valid

    def _merge_data(self, data):
        pairs = ['%s' %(v) for k, v in data]
        pre_sign_string = ','.join(pairs)
        return pre_sign_string

    def _sign_string(self, pre_sign_string):
        hashmethod = getattr(hashlib, self.hash_method)
        signed = hmac.new(self.secret, msg=pre_sign_string, digestmod=hashmethod).hexdigest()
        return signed

    def signature(self):
        log.debug('Making signature for data: %s', self.data)
        
        sorted_data = self._sort_data(self.data)
        log.debug('Sorted data: %s', sorted_data)
        
        pre_sign_string = self._merge_data(sorted_data)
        log.debug('String to sign: (normal) %s', pre_sign_string)
        
        signed = self._sign_string(pre_sign_string)
        log.debug('Signed data: %s', signed)
                
        return signed

    def __unicode__(self):
        return self.signature()


