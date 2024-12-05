import logging
from odoo import models, fields, api, exceptions
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta  # Importing relativedelta

_logger = logging.getLogger(__name__)  # Set up logging


class ResPartnerOffer(models.Model):
    _inherit = 'res.partner'

    offer_start_time = fields.Datetime(string='Offer Start Time')
    offer_end_time = fields.Datetime(string='Offer End Time')
    service_provider = fields.Selection(
        selection=[('customs_clearance', 'Customs Clearance'),
                   ('shipping_service', 'Shipping Service')],
        string='Service Provider'
    )

    @api.constrains('offer_start_time', 'offer_end_time')
    def _check_offer_times(self):
        for record in self:
            _logger.info(f"Checking offer times for partner {record.id}...")
            if record.offer_start_time and record.offer_end_time:
                if record.offer_end_time < record.offer_start_time:
                    _logger.error("Offer end time is earlier than start time.")
                    raise ValidationError("The offer end time must be greater than or equal to the start time.")
            _logger.info(f"Offer times valid for partner {record.id}.")

    def generate_rfq_for_service_providers(self):
        """
        Method to generate RFQ for contacts with specific service providers
        """
        for partner in self:
            _logger.info(f"Generating RFQ for service providers for partner {partner.id}...")
            product_service_type = partner.service_provider
            _logger.info(f"Service provider for partner {partner.id}: {product_service_type}")

            # Find all appropriate products based on the service_provider field
            products = self.env['product.template'].search([
                ('service_type', '=', product_service_type)
            ])

            if not products:
                _logger.warning(
                    f"No products found for service provider '{product_service_type}' for partner {partner.id}.")
                raise ValidationError(f"No products found with service type '{product_service_type}'")

            _logger.info(
                f"Found {len(products)} products for partner {partner.id} with service type '{product_service_type}'.")

            # Calculate contract start and end dates
            contract_start_date = fields.Datetime.now()
            contract_end_date = contract_start_date + relativedelta(months=3)

            # Prepare order lines for the RFQ
            order_lines = []
            for product in products:
                order_lines.append((0, 0, {
                    'product_id': product.id,  # Automatically select based on service_type
                    'product_qty': 1,  # Quantity
                    'price_unit': product.list_price,  # Unit price from product
                    'date_planned': contract_start_date,
                }))

            # Create RFQ (Request for Quotation)
            rfq = self.env['purchase.order'].create({
                'partner_id': partner.id,
                'state': 'draft',
                'order_line': order_lines,  # Use the prepared order lines
                'contract_start_date': contract_start_date,  # Set contract start date
                'contract_end_date': contract_end_date,  # Set contract end date
                'service_provided': True,  # Set service_provided to True
            })

            if rfq:
                _logger.info(f"RFQ {rfq.id} created for partner {partner.id}.")

            # If you want to send the RFQ by email, you can call the appropriate method
            if hasattr(rfq, 'action_rfq_send'):
                _logger.info(f"Sending RFQ {rfq.id} for partner {partner.id}.")
                rfq.action_rfq_send()
            else:
                _logger.warning(f"No send method found for RFQ {rfq.id} for partner {partner.id}.")

    # @api.model
    # def _cron_send_rfq_for_service_providers(self):
    #     """
    #     Scheduled action that checks contacts and sends RFQs based on the service provider
    #     """
    #     _logger.info("Scheduled action: Checking contacts for RFQs based on service providers...")
    #     contacts_with_service_providers = self.search([
    #         ('service_provider', 'in', ['customs_clearance', 'shipping_service'])
    #     ])
    #
    #     if contacts_with_service_providers:
    #         _logger.info(f"Found {len(contacts_with_service_providers)} contacts with valid service providers.")
    #         for partner in contacts_with_service_providers:
    #             partner.generate_rfq_for_service_providers()
    #     else:
    #         _logger.info("No contacts found with 'customs_clearance' or 'shipping_service'.")
    @api.model
    def _cron_send_rfq_for_service_providers(self):
        """
        Scheduled action that checks contacts and sends RFQs based on the service provider and offer_end_time
        """
        _logger.info("Scheduled action: Checking contacts for RFQs based on service providers and offer end time...")

        # Find partners whose offer_end_time has passed
        today = fields.Datetime.now()
        contacts_with_service_providers = self.search([
            ('service_provider', 'in', ['customs_clearance', 'shipping_service']),
            ('offer_end_time', '<=', today)  # Check if offer_end_time is in the past or today
        ])

        if contacts_with_service_providers:
            _logger.info(
                f"Found {len(contacts_with_service_providers)} contacts with valid service providers and expired offers.")
            for partner in contacts_with_service_providers:
                partner.generate_rfq_for_service_providers()
        else:
            _logger.info("No contacts found with expired offers and valid service providers.")


