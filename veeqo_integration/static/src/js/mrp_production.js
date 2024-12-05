odoo.define('shipsgo_integration.mrp_production', function (require) {
    "use strict";

    var FormController = require('web.FormController');

    FormController.include({
        _onFieldChanged: function (event) {
            this._super.apply(this, arguments);

            // Check if the process_type field has been updated
            if (event.data.changes.process_type) {
                var processType = event.data.changes.process_type;

                // Show or hide fields based on process_type value
                if (processType === 'refining') {
                    this.$('[name="product_from_rest_of_components"]').closest('.o_field_widget').show();
                    this.$('[name="rest_of_components_weight"]').closest('.o_field_widget').show();
                    this.$('[name="uom_id"]').closest('.o_field_widget').show();
                } else {
                    this.$('[name="product_from_rest_of_components"]').closest('.o_field_widget').hide();
                    this.$('[name="rest_of_components_weight"]').closest('.o_field_widget').hide();
                    this.$('[name="uom_id"]').closest('.o_field_widget').hide();
                }
            }
        },
    });
});
