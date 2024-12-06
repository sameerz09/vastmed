import logging
import requests
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class VeeqoCustomerSyncWizard(models.TransientModel):
    _name = 'veeqo.customer.sync.wizard'
    _description = 'Sync Customers from Veeqo'

    @api.model
    def sync_customers(self, query=None):
        """Fetch all customers from Veeqo in one go and create/update in Odoo."""
        _logger.info("Starting Veeqo customer sync")

        # Retrieve the API key from Odoo settings
        api_key = self.env['ir.config_parameter'].sudo().get_param('api_key')
        if not api_key:
            _logger.error("API Key not found!")
            raise ValueError(_('API Key is not configured. Please set it in Settings.'))

        # Prepare the request to Veeqo API
        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json',
        }
        url = 'https://api.veeqo.com/customers'

        # Set a large page_size to attempt to fetch all customers at once.
        # Adjust this number if you know the total number of customers.
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
            _logger.info(f"Fetched {len(customers)} customers in one request.")
        else:
            _logger.error(f"Error fetching data from Veeqo: {response.status_code} - {response.text}")
            raise UserError(_('Error fetching data from Veeqo.'))

        # Process and store customers in Odoo
        self._process_customers(customers)
        return True

    def _process_customers(self, customers):
        """
        Create or update customers in Odoo's res.partner model.
        We'll treat these Veeqo customers as Odoo contacts.
        """
        Partner = self.env['res.partner']

        for customer in customers:
            customer_id = customer.get('id')
            email = customer.get('email', '')
            phone = customer.get('phone', '')
            mobile = customer.get('mobile', '')
            full_name = customer.get('full_name') or self._get_full_name(customer)

            # Extract billing address info
            billing_addr = customer.get('billing_address', {})
            street = billing_addr.get('address1', '')
            street2 = billing_addr.get('address2', '')
            city = billing_addr.get('city', '')
            zip_code = billing_addr.get('zip', '')
            country_code = billing_addr.get('country', '')

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
                _logger.info(f"Updated partner for customer {customer_id}: {existing_partner.name}")
            else:
                new_partner = Partner.create(partner_vals)
                _logger.info(f"Created new partner for customer {customer_id}: {new_partner.name}")

    def _get_full_name(self, customer):
        """
        Helper method to construct a full name if 'full_name' is not provided.
        For example, try using the billing_address fields.
        """
        billing_addr = customer.get('billing_address', {})
        first_name = billing_addr.get('first_name', '')
        last_name = billing_addr.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip()
        return full_name or "No Name"
