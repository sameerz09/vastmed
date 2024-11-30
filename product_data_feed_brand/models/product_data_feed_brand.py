# Copyright © 2022 Garazd Creation (https://garazd.biz)
# @author: Yurii Razumovskyi (support@garazd.biz)
# @author: Iryna Razumovska (support@garazd.biz)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).

from odoo import fields, models


class ProductDataFeedBrand(models.Model):
    _name = "product.data.feed.brand"
    _description = 'Product Brands for Feeds'

    name = fields.Char(translate=True)

    _sql_constraints = [('product_data_feed_brand_uniq', 'UNIQUE (name)', 'Product Brand Name must be unique.')]
