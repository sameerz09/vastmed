import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class VeeqoCustomerSyncWizard(models.TransientModel):
    _name = 'veeqo.customer.sync.wizard'
    _description = 'Sync Customers from Veeqo'

    @api.model
    def sync_customers(self, query=None):
        """
        Fetch all customers from the Veeqo API in a single request (if possible)
        and create/update their records in Odoo's res.partner model.

        :param query: (optional) A free-text search query to filter results.
        """
        _logger.info("Starting Veeqo customer sync")

        api_key = self.env['ir.config_parameter'].sudo().get_param('api_key')
        if not api_key:
            _logger.error("API Key not found in system parameters!")
            raise ValueError(_('API Key is not configured. Please set it in Settings.'))

        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json',
        }
        url = 'https://api.veeqo.com/customers'

        # Try to fetch all customers at once by using a large page_size.
        # Adjust page_size if you know how many customers to expect.
        page_size = 100000
        params = {
            'page_size': page_size,
            'page': 1,
        }
        if query:
            params['query'] = query

        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            customers = response.json()
            _logger.info("Fetched %d customers from Veeqo.", len(customers))
        else:
            _logger.error("Error fetching data from Veeqo: %s - %s", response.status_code, response.text)
            raise UserError(_('Error fetching data from Veeqo.'))

        self._process_customers(customers)
        return True

    def _process_customers(self, customers):
        """
        Process each customer record from Veeqo and map it into Odoo's res.partner.

        :param customers: A list of customer dictionaries from Veeqo.
        """
        Partner = self.env['res.partner']

        for customer in customers:
            customer_id = customer.get('id')
            email = customer.get('email', '')
            phone = customer.get('phone', '')
            mobile = customer.get('mobile', '')
            full_name = customer.get('full_name') or self._get_full_name(customer)

            # Extract billing address details
            billing_addr = customer.get('billing_address', {}) or {}
            street = billing_addr.get('address1', '')
            street2 = billing_addr.get('address2', '')
            city = billing_addr.get('city', '')
            zip_code = billing_addr.get('zip', '')
            country_code = billing_addr.get('country', '')

            # Search for an existing partner by email. If email is empty,
            # consider using another unique field or skipping the search.
            existing_partner = Partner.search([('email', '=', email)], limit=1)

            partner_vals = {
                'name': full_name or f"Customer {customer_id}",
                'email': email,
                'phone': phone or mobile,
                'street': street,
                'street2': street2,
                'city': city,
                'zip': zip_code,
                'comment': customer.get('notes', ''),
            }

            if country_code:
                country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
                if country:
                    partner_vals['country_id'] = country.id

            if existing_partner:
                existing_partner.write(partner_vals)
                _logger.info("Updated partner for customer %s: %s", customer_id, existing_partner.name)
            else:
                new_partner = Partner.create(partner_vals)
                _logger.info("Created new partner for customer %s: %s", customer_id, new_partner.name)

    def _get_full_name(self, customer):
        """
        Construct a full name if 'full_name' is not provided by using billing address fields.

        :param customer: A dictionary representing a single Veeqo customer.
        :return: A full name string or 'No Name' if no name fields are found.
        """
        billing_addr = customer.get('billing_address', {}) or {}
        first_name = billing_addr.get('first_name', '')
        last_name = billing_addr.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip()
        return full_name or "No Name"
