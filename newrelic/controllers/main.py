# -*- coding: utf-8 -*-

from odoo import http
import odoo.addons.bus.controllers.main

try:
    import newrelic
    import newrelic.agent
except ImportError:
    newrelic = None


class BusController(odoo.addons.bus.controllers.main.BusController):

    @http.route()
    def send(self, channel, message):
        if newrelic:
            newrelic.agent.ignore_transaction()
        return super(BusController, self).send(channel, message)

    @http.route()
    def poll(self, channels, last, options=None):
        if newrelic:
            newrelic.agent.ignore_transaction()
        return super(BusController, self).poll(channels, last, options)
