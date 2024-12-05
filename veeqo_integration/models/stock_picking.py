from odoo import models, fields, _
from datetime import datetime, timedelta
import logging
import requests

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    shipment = fields.Char(string="Shipment")
    first_eta = fields.Date(string="First ETA")
    to_country = fields.Char(string="To Country")
    shipping_line = fields.Char(string="Shipping Line")
    loading_date = fields.Date(string="Loading Date")
    arrival_date = fields.Date(string="Arrival Date")
    fal_bl_no = fields.Char('B/L Number')
    fal_date_of_arrive = fields.Date('Date of arrive')

    def action_fetch_from_ships_go_shipping_widget(self):
        """
        Fetch data from the ShipsGo API and update the fields of the stock picking record.
        Logs an error if the operation fails.
        """
        self.ensure_one()

        api_key = self.env['ir.config_parameter'].sudo().get_param('api_key')

        # API endpoint and parameters
        url = "https://shipsgo.com/api/v1.1/ContainerService/GetContainerInfo/"
        params = {
            'authCode': api_key,
            'requestId': self.fal_bl_no,
            'mapPoint': 'true',
            'co2': 'true',
            'containerType': 'true',
        }

        try:
            # Make the GET request to the ShipsGo API
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raise an HTTPError for bad responses
            data = response.json()

            # Process and update fields from API response
            if data and isinstance(data, list) and data[0].get('Message') == 'Success':
                result = data[0]
                self.shipment = result.get('ContainerNumber', self.shipment)
                self.first_eta = result.get('FirstETA', self.first_eta)
                self.fal_date_of_arrive = result.get('ArrivalDate', {}).get('Date', self.arrival_date)
                # arrival_date_str = result.get('ArrivalDate', {}).get('Date', self.arrival_date)
                #
                # # Convert the arrival date string to a datetime object
                # try:
                #     arrival_date = datetime.strptime(arrival_date_str, '%Y-%m-%d')  # Adjust format if needed
                # except ValueError:
                #     _logger.warning("Invalid date format for ArrivalDate in picking ID %s", self.id)
                #     arrival_date = datetime.strptime(self.arrival_date, '%Y-%m-%d')  # Fallback to existing value
                #
                # # Add 7 days
                # new_arrival_date = arrival_date + timedelta(days=7)
                #
                # # Convert the updated datetime object back to a string if needed
                # new_arrival_date_str = new_arrival_date.strftime('%Y-%m-%d')  # Adjust format if needed
                #
                # # Update the field with the new date
                # self.fal_date_of_arrive = new_arrival_date_str
                self.to_country = result.get('ToCountry', self.to_country)
                self.shipping_line = result.get('ShippingLine', self.shipping_line)
                self.loading_date = result.get('LoadingDate', {}).get('Date', self.loading_date)


                _logger.info("Successfully fetched and updated data for picking ID %s", self.id)
                return True
            else:
                _logger.warning("No result found in API response for picking ID %s", self.id)
                return {
                    'warning': {
                        'title': _('Warning'),
                        'message': _('No data found from ShipsGo API.'),
                    }
                }

        except requests.RequestException as req_error:
            _logger.error("RequestException while fetching data for picking ID %s: %s", self.id, str(req_error))
            return {
                'warning': {
                    'title': _('Request Error'),
                    'message': _('An error occurred while making the request: %s') % str(req_error),
                }
            }

        except Exception as e:
            _logger.error("Exception while fetching data for picking ID %s: %s", self.id, str(e))
            return {
                'warning': {
                    'title': _('Error'),
                    'message': _('An unexpected error occurred while fetching data: %s') % str(e),
                }
            }

    def _cron_fetch_shipsgo_data(self):
        """
        Cron job to fetch ShipsGo data for all delivery orders.
        """
        pickings = self.search([('state', '=', 'assigned')])  # Assuming 'assigned' state for delivery orders
        for picking in pickings:
            picking.action_fetch_from_ships_go_shipping_widget()
