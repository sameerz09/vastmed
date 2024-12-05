import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    product_from_rest_of_components = fields.Many2one(
        'product.product',
        string='Product from Rest of Components',
        required=False,
        default=lambda self: self._default_product(),
        readonly=False
    )

    rest_of_components_weight = fields.Float(
        string='Rest of Components Weight',
        readonly=False
    )

    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        default=lambda self: self._default_uom_id(),
        required=True,
        readonly=True
    )

    process_type = fields.Selection(
        [
            ('refining', 'Refining'),
            ('production', 'Production'),
            ('assembly', 'Assembly')  # Added Assembly
        ],
        string='Process Type',
        default='production',  # Default to 'Production'
        required=True
    )

    additional_products = fields.Many2many(
        'product.product',
        string='Additional Products',
        help="Select additional products to include in the production."
    )

    show_action_confirm_button = fields.Boolean(
        compute="_compute_show_action_confirm_button",
        string="Show Confirm Button",
        store=True
    )
    show_button_mark_done = fields.Boolean(
        compute="_compute_show_button_mark_done",
        string="Show Mark Done Button",
        store=True
    )

    @api.depends('state', 'process_type')
    def _compute_show_action_confirm_button(self):
        """Control the visibility of the action_confirm button based on the production state and process type."""
        for record in self:
            if record.state == 'draft' and record.process_type == 'production':
                record.show_action_confirm_button = True
            else:
                record.show_action_confirm_button = False

    @api.depends('state', 'process_type')
    def _compute_show_button_mark_done(self):
        """Control the visibility of the button_mark_done button based on state and process type."""
        for record in self:
            # Show the button only if state is not 'draft' and process_type is not 'production'
            record.show_button_mark_done = record.state != 'draft' and record.process_type != 'production'

    # def action_confirm(self):
    #     """Override the action_confirm button behavior and update process_type to 'assembly'."""
    #     _logger.info("Confirming production order.")
    #
    #     # Call the super method to handle the default Odoo behavior
    #     res = super(MrpProduction, self).action_confirm()
    #
    #     # Ensure the state has transitioned correctly and update process_type
    #     for record in self:
    #         if record.state == 'confirmed':  # Adjust the state based on Odoo's workflow
    #             _logger.info(
    #                 f"Production order {record.id} confirmed successfully. Updating process_type to 'assembly'.")
    #             record.write({'process_type': 'assembly'})  # Use `write` to ensure the field is updated in the database
    #         else:
    #             _logger.warning(f"Production order {record.id} failed to confirm. Current state: {record.state}")
    #
    #     return res

    def _default_product(self):
        _logger.info("Searching for the default product 'Brass'.")
        brass_product = self.env['product.product'].search([('name', '=', 'Brass')], limit=1)
        if brass_product:
            _logger.info(f"Default product found: {brass_product.name} (ID: {brass_product.id})")
        else:
            _logger.warning("Default product 'Brass' not found.")
        return brass_product.id if brass_product else False

    def _default_uom_id(self):
        _logger.info("Searching for the default UOM 't' (ton).")
        ton_uom = self.env['uom.uom'].search([('name', '=', 't')], limit=1)
        if ton_uom:
            _logger.info(f"Default UOM found: {ton_uom.name} (ID: {ton_uom.id})")
        else:
            _logger.warning("Default UOM 't' not found.")
        return ton_uom.id if ton_uom else False

    def button_mark_done(self):
        _logger.info("Marking production order as done.")
        res = super(MrpProduction, self).button_mark_done()

        # Perform the check only for refining process type
        if self.process_type == 'refining':
            _logger.info("Process type is 'refining'. Checking product and weight.")
            if self.product_from_rest_of_components and self.rest_of_components_weight > 0:
                brass_product = self.product_from_rest_of_components
                _logger.info(f"Updating stock for product: {brass_product.name} (ID: {brass_product.id}).")
                _logger.info(
                    f"Current quantity available: {brass_product.qty_available}. Adding weight: {self.rest_of_components_weight}.")

                # Use stock movement logic to update stock safely
                location = self.env['stock.location'].search([('usage', '=', 'internal')], limit=1)  # Example location
                if not location:
                    raise UserError("No valid stock location found for updating quantities.")

                self.env['stock.quant'].sudo().create({
                    'product_id': brass_product.id,
                    'location_id': location.id,
                    'quantity': self.rest_of_components_weight,
                })
                _logger.info(f"Updated stock quantity for product {brass_product.name}.")
            else:
                _logger.error("Either 'Brass' product is not set or the weight is invalid.")
                raise UserError("Either 'Brass' product is not set or the weight is invalid.")
        else:
            _logger.info(f"Process type is '{self.process_type}'. Skipping quantity check for 'Brass'.")

        return res

    # def action_confirm(self):
    #     _logger.info("Confirming production order.")
    #     res = super(MrpProduction, self).action_confirm()
    #
    #     # Fetch the target company
    #     target_company = self.env['res.company'].search([('name', '=', 'Netaj Rubber Industrial Company')], limit=1)
    #     if not target_company:
    #         raise UserError("The company 'Netaj Rubber Industrial Company' does not exist.")
    #
    #     for production in self:
    #         _logger.info(
    #             f"Processing production order ID: {production.id} with process type: {production.process_type}.")
    #         if production.process_type == 'refining':
    #             if production.product_from_rest_of_components and production.rest_of_components_weight > 0:
    #                 brass_product = production.product_from_rest_of_components
    #                 _logger.info(f"Updating stock for product: {brass_product.name} (ID: {brass_product.id}).")
    #
    #                 # Switch to the target company's context
    #                 location = self.env['stock.location'].sudo().search([
    #                     ('name', '=', 'WH/Stock'),
    #                     ('company_id', '=', target_company.id)
    #                 ], limit=1)
    #                 if not location:
    #                     raise UserError(
    #                         f"The location 'WH/Stock' does not exist in the company 'Netaj Rubber Industrial Company'.")
    #
    #                 quant = self.env['stock.quant'].sudo().search([
    #                     ('product_id', '=', brass_product.id),
    #                     ('location_id', '=', location.id)
    #                 ], limit=1)
    #
    #                 if quant:
    #                     _logger.info(f"Found stock.quant for product {brass_product.name} in location {location.name}.")
    #                     quant.sudo().write({'quantity': quant.quantity + production.rest_of_components_weight})
    #                     _logger.info(f"Updated quantity for product {brass_product.name} to {quant.quantity}.")
    #                 else:
    #                     _logger.info(
    #                         f"No existing stock.quant found for product {brass_product.name} in location {location.name}. Creating a new one.")
    #                     self.env['stock.quant'].sudo().create({
    #                         'product_id': brass_product.id,
    #                         'location_id': location.id,
    #                         'quantity': production.rest_of_components_weight,
    #                         'company_id': target_company.id,
    #                     })
    #                     _logger.info(
    #                         f"Created new stock.quant for product {brass_product.name} with quantity {production.rest_of_components_weight}.")
    #             else:
    #                 _logger.warning("No valid product or weight provided for stock update.")
    #         else:
    #             _logger.info(f"Process type is '{production.process_type}'. Skipping stock updates for 'Brass'.")
    #
    #     return res
    def action_confirm(self):
        """Consolidated action_confirm button behavior."""
        _logger.info("Confirming production order.")

        # Call the super method to handle the default Odoo behavior
        res = super(MrpProduction, self).action_confirm()

        # Ensure the state has transitioned correctly and update process_type
        for record in self:
            # Log the state and process type
            _logger.info(
                f"Processing production order ID: {record.id} with state: {record.state} and process type: {record.process_type}.")

            # Update process_type to 'assembly' if state is confirmed and process_type is not 'refining'
            if record.state == 'confirmed':
                if record.process_type != 'refining':
                    _logger.info(
                        f"Production order {record.id} confirmed successfully. Updating process_type to 'assembly'.")
                    record.write({'process_type': 'assembly'})
                else:
                    _logger.info(
                        f"Production order {record.id} confirmed successfully. Keeping process_type as 'refining'.")

            # Handle specific logic for refining process type
            if record.process_type == 'refining':
                if record.product_from_rest_of_components and record.rest_of_components_weight > 0:
                    brass_product = record.product_from_rest_of_components
                    _logger.info(f"Updating stock for product: {brass_product.name} (ID: {brass_product.id}).")

                    # Fetch the target company
                    target_company = self.env['res.company'].search([('name', '=', 'Netaj Rubber Industrial Company')],
                                                                    limit=1)
                    if not target_company:
                        raise UserError("The company 'Netaj Rubber Industrial Company' does not exist.")

                    # Switch to the target company's context
                    location = self.env['stock.location'].sudo().search([
                        ('name', '=', 'Netaj/Stock'),
                        ('company_id', '=', target_company.id)
                    ], limit=1)
                    if not location:
                        raise UserError(
                            f"The location 'Netaj/Stock' does not exist in the company 'Netaj Rubber Industrial Company'.")

                    # Update or create stock.quant
                    quant = self.env['stock.quant'].sudo().search([
                        ('product_id', '=', brass_product.id),
                        ('location_id', '=', location.id)
                    ], limit=1)
                    if quant:
                        _logger.info(f"Found stock.quant for product {brass_product.name} in location {location.name}.")
                        quant.sudo().write({'quantity': quant.quantity + record.rest_of_components_weight})
                        _logger.info(f"Updated quantity for product {brass_product.name} to {quant.quantity}.")
                    else:
                        _logger.info(
                            f"No existing stock.quant found for product {brass_product.name} in location {location.name}. Creating a new one.")
                        self.env['stock.quant'].sudo().create({
                            'product_id': brass_product.id,
                            'location_id': location.id,
                            'quantity': record.rest_of_components_weight,
                            'company_id': target_company.id,
                        })
                        _logger.info(
                            f"Created new stock.quant for product {brass_product.name} with quantity {record.rest_of_components_weight}.")
                else:
                    _logger.warning("No valid product or weight provided for stock update.")

        return res

    # @api.model
    # def create(self, vals):
    #     _logger.info("Creating a new production order.")
    #     if self.env.context.get('default_process_type') == 'refining':
    #         vals['process_type'] = 'refining'
    #         _logger.info("Default process type set to 'refining'.")
    #
    #     return super(MrpProduction, self).create(vals)

    @api.model
    def create(self, vals):
        _logger.info("Attempting to create a new production order.")
        _logger.debug("Initial values (vals): %s", vals)

        # Check if the process type is 'refining'
        if vals.get('process_type') == 'refining':
            _logger.info("Detected process type 'refining'. Attempting to set default product to 'Raw Rubber'.")

            # Search for the product 'Raw Rubber'
            raw_rubber_product = self.env['product.product'].search([('name', '=', 'Raw Rubber')], limit=1)

            if raw_rubber_product:
                _logger.info(
                    "Found product 'Raw Rubber': %s (ID: %s). Assigning to 'product_from_rest_of_components'.",
                    raw_rubber_product.name,
                    raw_rubber_product.id
                )
                vals['product_from_rest_of_components'] = raw_rubber_product.id
            else:
                _logger.warning("Product 'Raw Rubber' not found. Ensure it exists in the product catalog.")

        # Log the final vals before calling the super method
        _logger.debug("Final values (vals) before creation: %s", vals)

        # Call the super method and handle any exceptions
        try:
            production_order = super(MrpProduction, self).create(vals)
            _logger.info("Production order created successfully with ID: %s", production_order.id)
            return production_order
        except Exception as e:
            _logger.error("Failed to create production order. Error: %s", str(e))
            raise e
