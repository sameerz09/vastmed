# -*- coding: utf-8 -*-


from odoo import models, fields, api
from datetime import datetime, timedelta
import requests
import json


class EtaUpdate(models.Model):
    _inherit = "stock.picking"

    fal_bl_no = fields.Char('B/L Number')
    fal_date_of_arrive = fields.Date('Date of arrive')


    @api.model
    def eta_update(self):
        ten_days_ago = fields.Date.today() - timedelta(days=20)
        for code in self.env['res.config.settings'].search([('api_key', '!=', False)]):
            for stock in self.search([('fal_bl_no', '!=', False), ('sale_id.state', '=', 'sale')]):
                if ((stock.fal_date_of_arrive == False) or  (stock.fal_date_of_arrive > ten_days_ago)):
                    params1 = {'authCode': code.api_key, 'requestId': stock.fal_bl_no}
                    url1 = 'https://shipsgo.com/api/v1.1/ContainerService/GetContainerInfo/'
                    response = requests.get(url1, params1)
                    if response:
                        data = json.loads(response.text)
                        if data[0]['ArrivalDate']:
                            arrivalDate = data[0]['ArrivalDate']['Date']
                            deadline = datetime.strptime(arrivalDate, "%Y-%m-%d")
                            stock.fal_date_of_arrive = deadline


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    api_key = fields.Char('Api key', config_parameter="api_key")
