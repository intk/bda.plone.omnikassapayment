from status_codes import get_status_description


class OmnikassaException(Exception):
    pass


class InvalidSignatureException(OmnikassaException):
    pass


class InvalidParamsException(OmnikassaException):
    pass


class UnknownStatusException(OmnikassaException):
    def __init__(self, status):
        assert isinstance(status, int)

        self.status = status

    def __unicode__(self):

        try:
            description = get_status_description(self.status)
            return u'Omnikassa returned unknown status: %s (%d)' % \
                (description, self.status)
        except:
            return u'Omnikassa returned unknown status: %d' % self.status

    def __str__(self):
        return repr(self.parameter)
