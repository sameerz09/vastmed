from odoo import models, fields

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _default_uom_id(self):
        # Set default UOM to 't' (ton)
        return self.env['uom.uom'].search([('name', '=', 't')], limit=1)

    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        default=_default_uom_id,
        required=True,
    )
