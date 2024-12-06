import logging
import requests
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class VeeqoPurchaseOrderSyncWizard(models.TransientModel):
    _name = 'veeqo.purchase.order.sync.wizard'
    _description = 'Sync Purchase Orders from Veeqo'

    @api.model
    def sync_purchase_orders(self, po_data):
        """
        Given a list of purchase orders (as Python dicts from the Veeqo API),
        create or update them in Odoo.
        """
        # Example: po_data is a Python list parsed from your JSON snippet
        # e.g. po_data = response.json()

        # We'll iterate through each PO and process it
        for po in po_data:
            self._process_purchase_order(po)

        return True

    def _process_purchase_order(self, po):
        """
        Process a single purchase order dictionary from Veeqo and integrate it into Odoo.
        """
        PurchaseOrder = self.env['purchase.order']
        Partner = self.env['res.partner']
        Product = self.env['product.product']

        # Extract top-level PO info
        veeqo_po_id = po.get('id')
        po_number = po.get('number')  # E.g. "PO-0000001"
        supplier_data = po.get('supplier', {})
        supplier_name = supplier_data.get('name', '')

        if not supplier_name:
            _logger.warning(f"PO {veeqo_po_id}: Supplier name not found, skipping.")
            return

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
                # Add more fields as needed
            })
            _logger.info(f"Created new supplier: {supplier.name}")

        # Attempt to find an existing purchase order by reference (po_number)
        # We can store the veeqo_po_id in a custom field if you wish
        existing_po = PurchaseOrder.search([('name', '=', po_number)], limit=1)

        po_vals = {
            'partner_id': supplier.id,
            'date_order': po.get('created_at'),  # Set order date to created_at or adjust as needed
            'origin': f"Veeqo-{veeqo_po_id}",  # For traceability
            # If you use 'name' as the PO reference, ensure it's unique or handle duplicates
            # Odoo automatically assigns names if left empty, but here we use the Veeqo PO number.
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

            # Find product by SKU or by other unique fields
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
                'date_planned': po_record.date_order or fields.Datetime.now(),  # Delivery date
            }

            # Check if a line with the same product already exists; if so, update it instead of creating new
            existing_line = POLine.search([('order_id', '=', po_record.id), ('product_id', '=', product.id)], limit=1)
            if existing_line:
                existing_line.write(line_vals)
                _logger.info(f"Updated line for product {product.name} in PO {po_record.name}")
            else:
                new_line = POLine.create(line_vals)
                _logger.info(f"Created line for product {product.name} in PO {po_record.name}")

    def _get_country_id(self, country_code):
        """
        Find country ID by country code. Returns None if not found.
        """
        if not country_code:
            return None
        country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        return country.id if country else None


# Usage example:
# Suppose you have the JSON data stored in `po_data` variable:
# po_data = [...]  # The JSON you provided above as a Python list/dict
#
# In Odoo shell or a server action:
# self.env['veeqo.purchase.order.sync.wizard'].sync_purchase_orders(po_data)
