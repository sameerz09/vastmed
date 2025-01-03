from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = "product.product"

    om_barcode = fields.Char(
        string="OM Barcode",
        help="International Article Number used for product identification.",
        compute="_compute_barcodes",
        store=True,
    )
    jv_barcode = fields.Char(
        string="JV Barcode",
        help="International Article Number used for product identification.",
        compute="_compute_barcodes",
        store=True,
    )

    @api.depends("barcode")
    def _compute_barcodes(self):
        for record in self:
            barcode = record.barcode or ""
            record.om_barcode = f"OM-{barcode}" if barcode else ""
            record.jv_barcode = f"JV-{barcode}" if barcode else ""