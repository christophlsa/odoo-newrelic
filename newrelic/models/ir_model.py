# -*- encoding: UTF-8 -*-
import logging

from odoo import _, api, http, models, service
from odoo.tools import config


_logger = logging.getLogger(__name__)


class IrModel(models.Model):

    _inherit = 'ir.model'

    @api.model_cr
    def _register_hook(self):
        try:
            import newrelic.agent
        except ImportError:
            _logger.warn('newrelic python module not installed or other '
                         'missing module')
            return super(IrModel, self)._register_hook()

        target = service.server.server

        try:
            instrumented = target._nr_instrumented
        except AttributeError:
            instrumented = target._nr_instrumented = False

        if instrumented:
            _logger.info("NewRelic instrumented already")
            return super(IrModel, self)._register_hook()

        try:
            newrelic.agent.initialize(config['new_relic_config_file'],
                                      config['new_relic_environment'])
        except KeyError:
            try:
                newrelic.agent.initialize(
                    config['new_relic_config_file'])
            except KeyError:
                _logger.info('NewRelic setting up from env variables')
                newrelic.agent.initialize()

        # Main WSGI Application
        target._nr_instrumented = True
        target.app = newrelic.agent.WSGIApplicationWrapper(target.app)

        # Workers new WSGI Application
        target = service.wsgi_server
        target.application_unproxied = newrelic.agent.WSGIApplicationWrapper(
            target.application_unproxied)

        # Error handling
        def should_ignore(exc, value, tb):
            from werkzeug.exceptions import HTTPException

            # Werkzeug HTTPException can be raised internally by
            # Odoo or in user code if they mix Odoo with Werkzeug. Filter based
            # on the HTTP status code.

            if isinstance(value, HTTPException):
                if newrelic.agent.ignore_status_code(value.code):
                    return True

        def _nr_wrapper_handle_exception_(wrapped):
            def _handle_exception(*args, **kwargs):
                transaction = newrelic.agent.current_transaction()

                if transaction is None:
                    return wrapped(*args, **kwargs)

                transaction.record_exception(ignore_errors=should_ignore)

                name = newrelic.agent.callable_name(args[1])
                with newrelic.agent.FunctionTrace(transaction, name):
                    return wrapped(*args, **kwargs)

            return _handle_exception

        target = http.WebRequest
        target._handle_exception = _nr_wrapper_handle_exception_(
            target._handle_exception)

        return super(IrModel, self)._register_hook()
