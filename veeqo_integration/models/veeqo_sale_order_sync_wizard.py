import logging
import requests
import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json

_logger = logging.getLogger(__name__)

class VeeqoSaleOrderSyncWizard(models.TransientModel):
    _name = 'veeqo.sale.order.sync.wizard'
    _description = 'Sync Sales Orders from Veeqo'

    # @api.model
    # def sync_sales_orders(self):
    #     """
    #     Fetch all sales orders from Veeqo's /orders endpoint in one large request
    #     and create/update them in Odoo as sale.orders.
    #     """
    #     _logger.info("Starting Veeqo sales order sync")
    #
    #     api_key = self.env['ir.config_parameter'].sudo().get_param('api_key')
    #     if not api_key:
    #         _logger.error("API Key not found!")
    #         raise ValueError(_('API Key is not configured. Please set it in Settings.'))
    #
    #     headers = {
    #         'x-api-key': api_key,
    #         'Content-Type': 'application/json',
    #     }
    #
    #     url = 'https://api.veeqo.com/orders'
    #     page_size = 100000
    #     since_id = 587138115
    #     params = {
    #         'page_size': page_size,
    #         'page': 1,
    #         'since_id': since_id,
    #     }
    #
    #     response = requests.get(url, headers=headers, params=params)
    #     if response.status_code == 200:
    #         orders_data = response.json()
    #         # Ensure orders_data is always a list
    #         if isinstance(orders_data, dict):
    #             orders_data = [orders_data]
    #         _logger.info("Fetched %d sales orders from Veeqo.", len(orders_data))
    #     else:
    #         _logger.error("Error fetching sales orders from Veeqo: %s - %s", response.status_code, response.text)
    #         raise UserError(_('Error fetching sales orders from Veeqo.'))
    #
    #     for order_data in orders_data:
    #         self._process_sale_order(order_data)
    #
    #     return True

    @api.model
    def sync_sales_orders(self):
        """
        Fetch all sales orders from Veeqo's /orders endpoint in one large request
        and create/update them in Odoo as sale.orders. Afterward, update the latest_order_id
        with the ID of the latest order to avoid fetching duplicates.
        """
        _logger.info("Starting Veeqo sales order sync")

        # Fetch the API key from system parameters
        api_key = self.env['ir.config_parameter'].sudo().get_param('api_key')
        if not api_key:
            _logger.error("API Key not found!")
            raise ValueError(_('API Key is not configured. Please set it in Settings.'))

        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json',
        }

        url = 'https://api.veeqo.com/orders'
        page_size = 100000

        # Get the current latest_order_id from system parameters
        try:
            latest_order_id = int(self.env['ir.config_parameter'].sudo().get_param('latest_order_id', '0'))
        except ValueError:
            _logger.warning("Invalid latest_order_id in system parameters. Defaulting to 0.")
            latest_order_id = 0

        params = {
            'page_size': page_size,
            'page': 1,
            'since_id': latest_order_id,
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()  # Raise an exception for HTTP errors
        except requests.exceptions.RequestException as e:
            _logger.error("Error fetching sales orders from Veeqo: %s", str(e))
            raise UserError(_('Error fetching sales orders from Veeqo: %s') % str(e))

        # Parse the response data
        orders_data = response.json()
        if isinstance(orders_data, dict):  # Ensure orders_data is always a list
            orders_data = [orders_data]

        _logger.info("Fetched %d sales orders from Veeqo.", len(orders_data))

        # Process each order and track the latest ID
        latest_id = latest_order_id + 1  # Increment the latest_order_id by 1
        for order_data in orders_data:
            # Log the order ID and SKU details
            sku_details = [
                {
                    "sku": item.get('product', {}).get('sku', 'N/A'),
                    "available_stock": item.get('sellable', {}).get('available_stock_level_at_all_warehouses', 'N/A'),
                    "title": item.get('title', 'No Title')
                }
                for item in order_data.get('line_items', [])
            ]
            _logger.info("Processing order ID: %s with Item Details: %s", order_data.get('id', 'Unknown'), sku_details)

            for item in order_data.get('line_items', []):
                sku = item.get('sellable', {}).get('sku_code', 'N/A')
                available_stock = item.get('sellable', {}).get('available_stock_level_at_all_warehouses', 'N/A')
                title = item.get('title', 'No Title')

                # if sku == 'N/A' or not sku.strip():
                #     _logger.warning(
                #         "Invalid SKU in Order ID: %s. Title: %s, Available Stock: %s. Skipping line.",
                #         order_data.get('id', 'Unknown'),
                #         title,
                #         available_stock
                #     )
                #     continue

                product = self.env['product.product'].sudo().search([('barcode', '=', sku)], limit=1)
                if product:
                    on_hand_qty = product.qty_available
                    _logger.info(
                        "Product  test found for SKU: %s | Product Name: %s | On-Hand Qty: %s | API Available Stock: %s",
                        sku, product.name, on_hand_qty, available_stock
                    )
                else:
                    _logger.warning(
                        "No product test found for SKU: %s in Order ID: %s. Title: %s, Available Stock: %s. Skipping line.",
                        sku, order_data.get('id', 'Unknown'), title, available_stock
                    )

            self._process_sale_order(order_data)
            # Update the latest_id if the current order ID is greater
            latest_id = max(latest_id, order_data.get('id', latest_order_id + 1))

        # Update the config parameter for latest_order_id
        self.env['ir.config_parameter'].sudo().set_param('latest_order_id', str(latest_id))
        _logger.info("Updated 'latest_order_id' to %s", latest_id)

        _logger.info("Sync complete. Updated latest_order_id to %d", latest_id)

        return True
    def _process_sale_order(self, order_data):
        """
        Convert a Veeqo order dict into Odoo sale.order and sale.order.line records.
        Fallback to a default customer if no 'customer' data is provided.
        """
        SaleOrder = self.env['sale.order']

        veeqo_order_id = order_data.get('id')
        order_number = order_data.get('number') or f"Veeqo-{veeqo_order_id}"

        # Parse created_at safely
        raw_date = order_data.get('created_at')
        date_order = fields.Datetime.now()
        if raw_date:
            try:
                parsed_date = datetime.datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                date_order = fields.Datetime.to_string(parsed_date)
            except ValueError:
                _logger.warning("Failed to parse date %s, using current time.", raw_date)
                date_order = fields.Datetime.now()

        # Handle customer data
        customer_info = order_data.get('customer')
        if not customer_info or not isinstance(customer_info, dict):
            # No customer info given, use default customer
            partner = self._get_default_customer()
            shipping_partner = partner
        else:
            # We have a customer dictionary
            partner, shipping_partner = self._get_customer_and_shipping_partners(customer_info, order_data, veeqo_order_id)

        # Attempt to find an existing sale order by name
        existing_order = SaleOrder.search([('name', '=', order_number)], limit=1)
        order_vals = {
            'partner_id': partner.id,
            'date_order': date_order,
            'origin': f"Veeqo-{veeqo_order_id}",
            'name': order_number,
            'partner_shipping_id': shipping_partner.id,
        }

        if existing_order:
            existing_order.write(order_vals)
            _logger.info("Updated existing Sale Order %s (Veeqo ID: %s)", existing_order.name, veeqo_order_id)
            so_record = existing_order
        else:
            so_record = SaleOrder.create(order_vals)
            _logger.info("Created Sale Order %s (Veeqo ID: %s)", so_record.name, veeqo_order_id)

        # Print quantity on hand for products in the order
        for line in so_record.order_line:
            product = line.product_id
            if product.exists():
                _logger.info("Product: %s, Quantity on Hand: %s", product.display_name, product.qty_available)
            else:
                _logger.warning("Product not found for Sale Order %s", so_record.name)

        # Process line items
        line_items = order_data.get('line_items', []) or []
        self._process_order_lines(so_record, line_items)
        if so_record.order_line:
            so_record.write({'state': 'draft'})
            so_record.sudo().action_confirm()
            # Correct stock picking search
            stock_picking = self.env['stock.picking'].search([('sale_id', '=', so_record.id)], limit=1)
            stock_picking.button_validate()
            if stock_picking:
                _logger.info("Stock Picking found: %s for Sale Order %s", stock_picking.name, so_record.name)
            else:
                _logger.warning("No Stock Picking found for Sale Order %s", so_record.name)

    def _get_customer_and_shipping_partners(self, customer_info, order_data, veeqo_order_id):
        """
        Create or update the customer partner and handle the shipping address.

        If billing_address or deliver_to is missing, handle gracefully.
        """
        Partner = self.env['res.partner']

        billing_addr = customer_info.get('billing_address') or {}
        customer_email = customer_info.get('email') or f"customer_{veeqo_order_id}@example.com"
        first_name = billing_addr.get('first_name', '')
        last_name = billing_addr.get('last_name', '')
        partner_name = (f"{first_name} {last_name}".strip()) or "No Name"

        # Create or update the customer partner
        partner = Partner.search([('email', '=', customer_email)], limit=1)
        partner_vals = {
            'name': partner_name,
            'email': customer_email,
            'phone': billing_addr.get('phone', ''),
            'street': billing_addr.get('address1', ''),
            'street2': billing_addr.get('address2', ''),
            'city': billing_addr.get('city', ''),
            'zip': billing_addr.get('zip', ''),
        }
        country_id = self._get_country_id(billing_addr.get('country', ''))
        if country_id:
            partner_vals['country_id'] = country_id

        if partner:
            partner.write(partner_vals)
        else:
            partner = Partner.create(partner_vals)
            _logger.info("Created new customer partner: %s", partner.name)

        # Shipping address (deliver_to)
        deliver_to = order_data.get('deliver_to') or {}
        if isinstance(deliver_to, dict) and deliver_to:
            shipping_partner = self._get_or_create_child_address(partner, deliver_to)
        else:
            # If no separate shipping address, use billing partner
            shipping_partner = partner

        return partner, shipping_partner

    def _get_default_customer(self):
        """
        Returns a default customer partner to use when no customer data is available.
        If not found, creates it.
        """
        Partner = self.env['res.partner']
        default_email = 'default_customer@example.com'
        default_partner = Partner.search([('email', '=', default_email)], limit=1)
        if not default_partner:
            default_partner = Partner.create({
                'name': 'Default Customer',
                'email': default_email,
            })
            _logger.info("Created a default customer partner as fallback.")
        return default_partner

    def _process_order_lines(self, so_record, line_items):
        SaleOrderLine = self.env['sale.order.line']
        Product = self.env['product.product']

        for line in line_items:
            price_unit = line.get('price_per_unit', 0.0)
            quantity = line.get('quantity', 1)
            tax_rate = line.get('tax_rate', 0.0)
            discount_amount = line.get('taxless_discount_per_unit', 0.0)
            sellable = line.get('sellable', {}) or {}
            sku = sellable.get('sku_code', '')

            # Find product by SKU
            product = Product.search([('barcode', '=', sku)], limit=1)
            if not product:
                _logger.warning("No product found for SKU: %s, skipping line.", sku)
                continue

            discount_percentage = 0.0
            if discount_amount > 0 and price_unit > 0:
                discount_percentage = (discount_amount / price_unit) * 100.0

            line_vals = {
                'order_id': so_record.id,
                'product_id': product.id,
                'name': product.name,
                'product_uom_qty': quantity,
                'price_unit': price_unit,
                'discount': discount_percentage,
            }

            # (Optional) Handle taxes if you have a method to match tax_rate to a tax record

            # Check if a line with the same product exists
            existing_line = SaleOrderLine.search([('order_id', '=', so_record.id), ('product_id', '=', product.id)],
                                                 limit=1)
            if existing_line:
                existing_line.write(line_vals)
                _logger.info("Updated line for product %s in SO %s | Barcode: %s", product.name, so_record.name,
                             product.barcode)
            else:
                new_line = SaleOrderLine.create(line_vals)
                _logger.info("Created line for product %s in SO %s | Barcode: %s", product.name, so_record.name,
                             product.barcode)

    def _get_or_create_child_address(self, parent_partner, addr):
        """
        Create or update a shipping address as a child contact of the main partner if needed.
        """
        Partner = self.env['res.partner']
        name = (f"{addr.get('first_name', '')} {addr.get('last_name', '')}").strip() or "No Name"
        email = addr.get('email', parent_partner.email)
        phone = addr.get('phone', parent_partner.phone)

        existing_child = Partner.search([
            ('parent_id', '=', parent_partner.id),
            ('name', '=', name),
            ('email', '=', email),
        ], limit=1)

        vals = {
            'name': name,
            'parent_id': parent_partner.id,
            'type': 'delivery',
            'street': addr.get('address1', ''),
            'street2': addr.get('address2', ''),
            'city': addr.get('city', ''),
            'zip': addr.get('zip', ''),
            'phone': phone,
            'email': email,
        }
        country_id = self._get_country_id(addr.get('country', ''))
        if country_id:
            vals['country_id'] = country_id

        if existing_child:
            existing_child.write(vals)
            return existing_child
        else:
            return Partner.create(vals)

    def _get_country_id(self, country_code):
        """
        Find country ID by country code. Returns None if not found.
        """
        if not country_code:
            return None
        country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        return country.id if country else None
