from odoo import models, fields, api

class ResPartner2(models.Model):
    _inherit = 'res.partner'

    shipsgo_payment = fields.Boolean(string='Shipsgo Payment')
    # offer_start_time = fields.Datetime(string='Offer Start Time')
    # offer_end_time = fields.Datetime(string='Offer End Time')

    # @api.constrains('offer_start_time', 'offer_end_time')
    # def _check_offer_times(self):
    #     for record in self:
    #         if record.offer_start_time and record.offer_end_time:
    #             if record.offer_end_time < record.offer_start_time:
    #                 raise exceptions.ValidationError(
    #                     "The offer end time must be greater than or equal to the start time."
    #                 )
    #
    # def generate_new_quotation(self):
    #     for partner in self:
    #         # Check if the offer has ended
    #         if partner.offer_end_time and partner.offer_end_time < fields.Datetime.now():
    #             # Create a new quotation
    #             quotation = self.env['sale.order'].create({
    #                 'partner_id': partner.id,
    #                 'state': 'draft',
    #                 'order_line': [(0, 0, {
    #                     'product_id': some_product_id,  # Specify the product ID or other fields as needed
    #                     'product_uom_qty': 1,  # Specify quantity or other fields
    #                     'price_unit': 100.0,  # Specify the unit price or other fields
    #                 })],
    #             })
    #             # Send the quotation by email
    #             quotation.action_send_quotation()  # Use appropriate method to send the quotation
    #
    # @api.model
    # def _cron_send_expired_offer_quotations(self):
    #     partners_with_expired_offers = self.search([
    #         ('offer_end_time', '<', fields.Datetime.now())
    #     ])
    #     if partners_with_expired_offers:
    #         partners_with_expired_offers.generate_new_quotation()



class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """
        Triggered when the partner is changed in the sales order form.
        It checks the partner's `shipsgo_payment` field and sets the payment term accordingly.
        """
        if self.partner_id:
            if self.partner_id.shipsgo_payment:
                # Set payment term to 'Cash Against Documents (CAD)'
                payment_term = self.env['account.payment.term'].search([('name', '=', 'Cash Against Documents (CAD)')], limit=1)
            else:
                # Set payment term to 'Letter of Credit (LC)'
                payment_term = self.env['account.payment.term'].search([('name', '=', 'Letter of Credit (LC)')], limit=1)

            if payment_term:
                self.payment_term_id = payment_term.id

