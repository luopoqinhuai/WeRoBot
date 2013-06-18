# -*- coding: utf-8 -*-

import inspect
import hashlib
from bottle import Bottle, request, response, abort

from .parser import parse_user_msg
from .reply import create_reply
from . import errors
#from .settings import settings
settings = None

__all__ = ['BaseRoBot', 'WeRoBot']


def fallback_handler(message, exc):
    s = 'Error: Message Unhandled: '
    if isinstance(exc, errors.tolerant_errors):
        s += str(exc)
    else:
        if settings.DEBUG:
            s += str(exc)
        else:
            s += 'Unexpected Exception'
    return s


class BaseRoBot(object):
    message_types = ['subscribe', 'unsubscribe', 'click',  # event
                     'text', 'image', 'link', 'location',
                     'music', 'news',
                     # ``_fallback`` is not a real message type,
                     # it is used only if the message has no relevent handler
                     '_fallback']

    def __init__(self, token=None):
        self.token = token
        # Initialize ``type -> function`` maps
        self._handlers = dict((k, None) for k in self.message_types)
        self._handlers['_fallback'] = fallback_handler

    def subscribe(self, f):
        """
        Decorator to register handler function for ``subscribe event`` messages
        """
        self.add_handler(f, types=['subscribe'])

    def unsubscribe(self, f):
        """
        Decorator to register handler function for ``unsubscribe event`` messages
        """
        self.add_handler(f, types=['unsubscribe'])

    def click(self, f):
        """
        Decorator to register handler function for ``click event`` messages
        """
        self.add_handler(f, types=['click'])

    def text(self, f):
        """
        Decorator to register handler function for ``text`` messages
        """
        self.add_handler(f, types=['text'])
        return f

    def image(self, f):
        """
        Decorator to register handler function for ``image`` messages
        """
        self.add_handler(f, types=['image'])
        return f

    def link(self, f):
        """
        Decorator to register handler function for ``link`` messages
        """
        self.add_handler(f, types=['link'])
        return f

    def location(self, f):
        """
        Decorator to register handler function for ``location`` messages
        """
        self.add_handler(f, types=['location'])
        return f

    def fallback(self, f):
        """
        Decorator to register handler function for messages that have no relevant handlers
        """
        self.add_handler(f, types=['_fallback'])
        return f

    def add_handler(self, func, types=None):
        """
        Add a new handler to the robot.
        """
        assert types, 'You should specify one or more types for the handler function'
        if not inspect.isfunction(func):
            raise TypeError('"%s" should be a funciton' % func)
        for type_ in types:
            self._handlers[type_] = func

    def _get_reply(self, message):
        if not message.type in self.message_types:
            raise errors.UnknownMessageType('Type "%s" is not supported' % message.type)

        handler = self._handlers[message.type]
        if not handler:
            raise errors.HandlerNotFound('No handler is binded for message type "%s"' % message.type)

        return handler(message)

    def check_signature(self, timestamp, nonce, signature):
        sign = [self.token, timestamp, nonce]
        sign.sort()
        sign = ''.join(sign)
        sign = hashlib.sha1(sign).hexdigest()
        return sign == signature


class WeRoBot(BaseRoBot):

    @property
    def wsgi(self):
        if not self._handlers:
            raise
        app = Bottle()

        @app.get('/')
        def echo():
            if not self.check_signature(
                request.query.timestamp,
                request.query.nonce,
                request.query.signature
            ):
                return abort('403')
            return request.query.echostr

        @app.post('/')
        def handle():
            if not self.check_signature(
                request.query.timestamp,
                request.query.nonce,
                request.query.signature
            ):
                return abort('403')

            body = request.body.read()
            message = parse_user_msg(body)
            try:
                reply = self._get_reply(message)
            except Exception, e:
                reply = self.get_fallback_handler()(message, e)

            # NOTE Commented no reply handling, there should always be given a reply
            # if not reply:
            #     return ''

            response.content_type = 'application/xml'
            return create_reply(reply, message=message)

        return app

    def run(self, server='auto', host='127.0.0.1', port=8888):
        self.wsgi.run(server=server, host=host, port=port)
