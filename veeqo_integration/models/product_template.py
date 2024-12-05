from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Update the selection field to include new options
    service_type = fields.Selection(
        selection=[
            ('manual', "Manually set quantities on order"),
            ('customs_clearance', 'Customs Clearance'),
            ('shipping_service', 'Shipping Service'),
        ],
        string="Track Service",
        compute='_compute_service_type',
        store=True,
        readonly=False,
        help="Manually set quantities on order: Invoice based on the manually entered quantity, without creating an analytic account.\n"
             "Timesheets on contract: Invoice based on the tracked hours on the related timesheet.\n"
             "Create a task and track hours: Create a task on the sales order validation and track the work hours."
    )

    @api.depends('type')
    def _compute_service_type(self):
        for record in self:
            if record.type == 'consu' or not record.service_type:
                record.service_type = 'manual'
