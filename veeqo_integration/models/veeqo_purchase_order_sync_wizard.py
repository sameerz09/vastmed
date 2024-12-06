import logging
import requests
import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class VeeqoPurchaseOrderSyncWizard(models.TransientModel):
    _name = 'veeqo.purchase.order.sync.wizard'
    _description = 'Sync Purchase Orders from Veeqo'

    @api.model
    def sync_purchase_orders(self):
        """
        Fetch all purchase orders from the Veeqo API in one request and
        create or update them in Odoo.
        """
        _logger.info("Starting Veeqo purchase order sync")

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

        url = 'https://api.veeqo.com/purchase_orders'

        # Attempt to fetch all POs at once (adjust if needed)
        page_size = 100000
        params = {
            'page_size': page_size,
            'page': 1,
        }

        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            po_data = response.json()
            _logger.info(f"Fetched {len(po_data)} purchase orders in one request.")
        else:
            _logger.error(f"Error fetching purchase orders from Veeqo: {response.status_code} - {response.text}")
            raise UserError(_('Error fetching purchase orders from Veeqo.'))

        # Process and store purchase orders in Odoo
        for po in po_data:
            self._process_purchase_order(po)
        return True

    def _process_purchase_order(self, po):
        """
        Process a single purchase order dictionary from Veeqo and integrate it into Odoo.
        """
        PurchaseOrder = self.env['purchase.order']
        Partner = self.env['res.partner']

        veeqo_po_id = po.get('id')
        po_number = po.get('number')  # e.g. "PO-0000001"
        supplier_data = po.get('supplier', {})
        supplier_name = supplier_data.get('name', '')

        if not supplier_name:
            _logger.warning(f"PO {veeqo_po_id}: Supplier name not found, skipping.")
            return

        # Convert created_at from ISO 8601 to Odoo-compatible string
        raw_date = po.get('created_at')
        date_order = fields.Datetime.now()
        if raw_date:
            # raw_date example: "2024-02-04T06:38:35.908Z"
            try:
                # Parse using datetime with a known format
                # This pattern handles YYYY-MM-DDTHH:MM:SS.%fZ
                parsed_date = datetime.datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                date_order = fields.Datetime.to_string(parsed_date)
            except ValueError:
                _logger.warning(f"Failed to parse date {raw_date}, using current time.")
                date_order = fields.Datetime.now()

        # Find or create supplier as a vendor in Odoo
        supplier = Partner.search([('name', '=', supplier_name), ('supplier_rank', '>', 0)], limit=1)
        if not supplier:
            supplier = Partner.create({
                'name': supplier_name,
                'supplier_rank': 1,
                'street': supplier_data.get('address_line_1', ''),
                'street2': supplier_data.get('address_line_2', ''),
                'city': supplier_data.get('city', ''),
                'zip': supplier_data.get('post_code', ''),
                'country_id': self._get_country_id(supplier_data.get('country', '')),
            })
            _logger.info(f"Created new supplier: {supplier.name}")

        # Attempt to find an existing purchase order by reference (po_number)
        existing_po = PurchaseOrder.search([('name', '=', po_number)], limit=1)

        po_vals = {
            'partner_id': supplier.id,
            'date_order': date_order,
            'origin': f"Veeqo-{veeqo_po_id}",
            'name': po_number,
        }

        if existing_po:
            existing_po.write(po_vals)
            _logger.info(f"Updated existing PO {existing_po.name} (Veeqo ID: {veeqo_po_id})")
            po_record = existing_po
        else:
            po_record = PurchaseOrder.create(po_vals)
            _logger.info(f"Created PO {po_record.name} (Veeqo ID: {veeqo_po_id})")

        # Process line items
        self._process_po_lines(po_record, po.get('line_items', []))

    def _process_po_lines(self, po_record, line_items):
        """
        Create or update purchase order lines from the given line items.
        """
        POLine = self.env['purchase.order.line']
        Product = self.env['product.product']

        for line in line_items:
            cost = line.get('cost', 0)
            quantity = line.get('quantity', 0)
            variant = line.get('product_variant', {})
            sku = variant.get('sku_code', '')

            # Find product by SKU
            product = Product.search([('default_code', '=', sku)], limit=1)
            if not product:
                _logger.warning(f"No product found for SKU: {sku}, skipping line.")
                continue

            line_vals = {
                'order_id': po_record.id,
                'product_id': product.id,
                'name': product.name,
                'product_qty': quantity,
                'price_unit': cost,
                'date_planned': po_record.date_order or fields.Datetime.now(),
            }

            # Check if a line with the same product already exists
            existing_line = POLine.search([('order_id', '=', po_record.id), ('product_id', '=', product.id)], limit=1)
            if existing_line:
                existing_line.write(line_vals)
                _logger.info(f"Updated line for product {product.name} in PO {po_record.name}")
            else:
                POLine.create(line_vals)
                _logger.info(f"Created line for product {product.name} in PO {po_record.name}")

    def _get_country_id(self, country_code):
        """
        Find country ID by country code. Returns None if not found.
        """
        if not country_code:
            return None
        country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        return country.id if country else None
