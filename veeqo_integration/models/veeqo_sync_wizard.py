import logging
import requests
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class VeeqoSyncWizard(models.TransientModel):
    _name = 'veeqo.sync.wizard'
    _description = 'Veeqo Sync Wizard'

    @api.model
    def sync_products(self):
        _logger.info("Starting Veeqo product sync")

        # Retrieve the API key from the Odoo settings
        api_key = self.env['ir.config_parameter'].sudo().get_param('api_key')
        if not api_key:
            _logger.error("API Key not found!")
            raise ValueError(_('API Key is not configured. Please set it in Settings.'))

        # Define the API headers
        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json',
        }

        # Define the URL and query parameters for fetching products
        url = 'https://api.veeqo.com/products'
        params = {
            'page_size': '100',  # Set to the maximum allowed value
        }

        try:
            all_products = []
            page = 1

            while True:
                params['page'] = page
                response = requests.get(url, headers=headers, params=params)

                if response.status_code == 200:
                    products = response.json()
                    if not products:
                        break  # Exit loop if no products are returned
                    all_products.extend(products)
                    _logger.info(f"Fetched page {page} with {len(products)} products")
                    page += 1
                else:
                    _logger.error(f"Error fetching data from Veeqo: {response.status_code} - {response.text}")
                    raise UserError(_('Error fetching data from Veeqo.'))

            _logger.info(f"Total products fetched: {len(all_products)}")

            # Process all products
            for product in all_products:
                sellables = product.get('sellables', [])
                main_sellable = sellables[0] if sellables else {}

                # Always use predefined values
                is_storable = True
                product_type = 'consu'

                # Calculate physical stock level on hand
                qty_on_hand = sum(
                    stock_entry.get('physical_stock_level_at_all_warehouses', 0) or 0
                    for stock_entry in main_sellable.get('stock_entries', [])
                )

                product_data = {
                    'name': product.get('title', 'Unnamed Product'),
                    'description': product.get('description', ''),
                    'default_code': main_sellable.get('sku_code', ''),
                    'list_price': main_sellable.get('price', 0),  # Sale price
                    'standard_price': main_sellable.get('cost_price', 0),  # Cost price
                    'qty_available': qty_on_hand,  # Physical stock level on hand
                    'type': product_type,  # 'consu' as required
                    'is_storable': is_storable,  # True as required
                    'uom_id': self.env.ref('uom.product_uom_unit').id,  # Default to Units
                    'uom_po_id': self.env.ref('uom.product_uom_unit').id,
                }

                # Check if product.template already exists
                existing_template = self.env['product.template'].search([
                    ('default_code', '=', product_data['default_code'])
                ], limit=1)

                if existing_template:
                    _logger.info(f"Product template already exists: {existing_template.name}")
                    # Update existing product template with cost and quantity
                    existing_template.write({
                        'standard_price': product_data['standard_price'],
                        'qty_available': product_data['qty_available'],
                    })
                    _logger.info(f"Updated product template: {existing_template.name}")
                    continue

                # Create product.template
                product_template = self.env['product.template'].create(product_data)
                _logger.info(f"Created product template: {product_template.name}")

                # Automatically creates product.product via Odoo ORM
                _logger.info(f"Created product: {product_template.product_variant_ids}")

            return True

        except Exception as e:
            _logger.error(f"An error occurred during the API request: {e}")
            raise UserError(_('An error occurred while syncing products from Veeqo.'))
