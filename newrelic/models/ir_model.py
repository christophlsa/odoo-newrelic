# -*- encoding: UTF-8 -*-
import importlib
import logging

from odoo import _, api, http, models, service
from odoo.tools import config
from werkzeug.exceptions import HTTPException

_logger = logging.getLogger(__name__)

try:
    import newrelic.agent

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
except ImportError:
    newrelic = None


class IrModel(models.Model):

    _inherit = 'ir.model'

    @api.model_cr
    def _register_hook(self):
        if not newrelic:
            _logger.warning('newrelic python module not installed or other '
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

        # Main WSGI Application
        target._nr_instrumented = True
        target.app = newrelic.agent.WSGIApplicationWrapper(target.app)

        # Workers new WSGI Application
        target = service.wsgi_server
        target.application_unproxied = newrelic.agent.WSGIApplicationWrapper(
            target.application_unproxied)

        # Error handling
        def should_ignore(exc, value, tb):
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

        def _nr_wrapper_call_function_(wrapped):
            def _call_function(self, *args, **kwargs):
                routes = self.endpoint.routing['routes']
                if routes:
                    route = routes[0][1:]
                    route = route.replace('string:', '').replace('int:', '')
                    newrelic.agent.set_transaction_name(route)
                return wrapped(self, *args, **kwargs)

            return _call_function

        def _nr_wrapper_dispatch_rpc_(wrapped):
            def dispatch_rpc(service_name, method, params):
                route = '%s/%s' % (service_name, method)
                newrelic.agent.set_transaction_name(
                    route, group='Python/rpc', priority=8)

                return wrapped(service_name, method, params)

            return dispatch_rpc

        def _nr_wrapper_execute_cr_(wrapped):
            def execute_cr(cr, uid, obj, method, *args, **kw):
                route = '%s/%s' % (obj, method)
                newrelic.agent.set_transaction_name(
                    route, group='Python/rpc', priority=9)

                return wrapped(cr, uid, obj, method, *args, **kw)

            return execute_cr

        def patch_function_traces():
            module_smtplib = importlib.import_module('smtplib')
            newrelic.agent.wrap_function_trace(module_smtplib, 'SMTP.sendmail')

            module_odoohttp = importlib.import_module('odoo.http')
            newrelic.agent.wrap_function_trace(
                module_odoohttp, 'Response.render')

            # we have to write a function returns a function so that we can
            # reuse it for all of the patch methods
            def _nr_wrapper_odoo_model_function():
                @api.model
                def wrapper(*args, **kwargs):
                    origin = newrelic.agent.FunctionTraceWrapper(
                        wrapper.origin)
                    return origin(*args, **kwargs)
                return wrapper

            self.env['ir.actions.report']._patch_method(
                '_run_wkhtmltopdf', _nr_wrapper_odoo_model_function())
            # maybe not needed as we already patch SMTP.sendmail
            self.env['ir.mail_server']._patch_method(
                'send_email', _nr_wrapper_odoo_model_function())

        target = http.WebRequest
        target._handle_exception = _nr_wrapper_handle_exception_(
            target._handle_exception)
        target._call_function = _nr_wrapper_call_function_(
            target._call_function)
        http.dispatch_rpc = _nr_wrapper_dispatch_rpc_(http.dispatch_rpc)
        service.model.execute_cr = _nr_wrapper_execute_cr_(
            service.model.execute_cr)

        patch_function_traces()

        return super(IrModel, self)._register_hook()
