from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    api_key = fields.Char('API Key', config_parameter='api_key')

    latest_order_id = fields.Char(string='Latest Order', config_parameter='latest_order_id')
