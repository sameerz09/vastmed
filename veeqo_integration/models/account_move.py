from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    shipment_date = fields.Date(string='Shipment Date')
    arrival_date = fields.Date(string='Arrival Date')
    shipping_policy_sending_date = fields.Date(string='Shipping Policy Sending Date')

    @api.onchange('invoice_date')
    def _onchange_shipping_policy_sending_date(self):
        if self.invoice_date and not self.partner_id.shipsgo_payment:
            self.invoice_date_due = self.invoice_date

    def action_get_latest_arrival_date(self):
        # Ensure this method is called from a single record
        self.ensure_one()

        # Check if the partner's `shipsgo_payment` field is True
        if self.partner_id.shipsgo_payment:
            # Extract the sales order name from the invoice's invoice_origin field
            sales_order_name = self.invoice_origin

            # Find the corresponding sales order based on the name
            sales_order = self.env['sale.order'].search([('name', '=', sales_order_name)], limit=1)

            if sales_order:
                # Find the latest related stock.picking record using the sale_id field
                latest_picking = self.env['stock.picking'].search(
                    [('sale_id', '=', sales_order.id)],
                    order='id desc',
                    limit=1
                )

                if latest_picking:
                    # Extract the arrival_date and shipment_date
                    arrival_date = latest_picking.fal_date_of_arrive
                    shipment_date = latest_picking.loading_date

                    # Ensure dates exist before proceeding
                    if arrival_date and shipment_date:
                        # Add 7 days to the arrival_date
                        updated_arrival_date = arrival_date + relativedelta(days=7)
                        self.arrival_date = updated_arrival_date  # Update the arrival_date with the added 7 days

                        # Update the shipment_date field
                        self.shipment_date = shipment_date

                        # Calculate the difference between arrival_date and shipment_date
                        difference_days = (updated_arrival_date - shipment_date).days

                        # Adjust the due date based on the difference
                        if difference_days < 60:
                            calculated_due_date = shipment_date + relativedelta(days=61)
                        else:
                            calculated_due_date = shipment_date + relativedelta(days=difference_days)

                        # Determine the final due date based on the conditions
                        if 1 <= calculated_due_date.day < 3:
                            final_due_date = calculated_due_date.replace(day=3)
                        elif 3 <= calculated_due_date.day < 17:
                            final_due_date = calculated_due_date.replace(day=17)
                        else:
                            final_due_date = (calculated_due_date + relativedelta(months=1)).replace(day=3)

                        # Set the calculated due date as the invoice date due
                        self.invoice_date_due = final_due_date

                        # Notify the user of the success
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': 'Arrival Date Found',
                                'message': f"Final Due Date: {final_due_date.strftime('%Y-%m-%d')}",
                                'type': 'success',
                                'sticky': False,
                            }
                        }
                    else:
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': 'Dates Missing',
                                'message': 'Either arrival date or shipment date is missing.',
                                'type': 'warning',
                                'sticky': False,
                            }
                        }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'No Picking Found',
                            'message': 'No related stock picking records found for this sale order.',
                            'type': 'warning',
                            'sticky': False,
                        }
                    }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Sales Order Not Found',
                        'message': 'The related sales order could not be found.',
                        'type': 'danger',
                        'sticky': False,
                    }
                }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'ShipsGo Payment Not Enabled',
                    'message': 'The partner does not have ShipsGo payment enabled.',
                    'type': 'warning',
                    'sticky': False,
                }
            }