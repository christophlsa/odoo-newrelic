from odoo import http
from odoo.addons.web.controllers.main import DataSet

try:
    import newrelic
    import newrelic.agent
except ImportError:
    newrelic = None


class NewRelicDataSet(DataSet):

    @http.route()
    def search_read(self, model, fields=False, offset=0, limit=False,
                    domain=None, sort=None):
        if newrelic:
            route = '%s/%s' % ('search_read', model)
            newrelic.agent.set_transaction_name(
                route, group='Python/rpc', priority=10)

        return super(NewRelicDataSet, self).search_read(
            model, fields=fields, offset=offset, limit=limit,
            domain=domain, sort=sort)

    @http.route()
    def call(self, model, method, args, domain_id=None, context_id=None):
        if newrelic:
            route = '%s/%s' % (model, method)
            newrelic.agent.set_transaction_name(
                route, group='Python/rpc', priority=10)

        return super(NewRelicDataSet, self).call(
            model, method, args, domain_id=domain_id, context_id=context_id)

    @http.route()
    def call_kw(self, model, method, args, kwargs, path=None):
        if newrelic:
            route = '%s/%s' % (model, method)
            newrelic.agent.set_transaction_name(
                route, group='Python/rpc', priority=10)

        return super(NewRelicDataSet, self).call_kw(
            model, method, args, kwargs, path=path)

    @http.route()
    def call_button(self, model, method, args, domain_id=None,
                    context_id=None):
        if newrelic:
            route = '%s/%s' % (model, method)
            newrelic.agent.set_transaction_name(
                route, group='Python/rpc', priority=10)

        return super(NewRelicDataSet, self).call_button(
            model, method, args, domain_id=domain_id, context_id=context_id)
