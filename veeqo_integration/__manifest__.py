{
    'name': 'Veeqo integration',
    'version': '18.0.1.0',
    'summary': 'Veeqo integration',
    'description': 'Shipsgo integration',
    'license': 'LGPL-3',
    'author': 'Netframe',
    'depends': ['base', 'stock', 'sale', 'mrp'],
    'support': 'odoo@netframe.org',
    'website': 'https://www.netframe.org/',
    'data': [
        # 'data/shedule_action.xml',
        # 'data/scheduled_action2.xml',
        'views/veeqo_integration.xml',
        # 'views/stock_picking_views.xml',
        # 'views/account_move_view.xml',
        # 'views/res_partner_view.xml',
        # 'views/mrp_production_views.xml',
        # 'views/product_template_views.xml',
        # 'views/mrp_production_menu.xml',
        # 'views/mrp_production_views.xml',
        # 'data/ir_cron_data_fetchshipsgo.xml'
        'data/sync_veeqo_products.xml',
        'data/veeqo_customer_cron.xml'

    ],
    'images': [
        # 'static/description/icon.png'
        'static/description/banner.gif'
    ],
    # 'assets': {
    #         'web.assets_backend': [
    #             'shipsgo_integration/static/src/css/custom_button_styles.css',
    #             # 'shipsgo_integration/static/src/js/mrp_production.js',
    #         ],
    #     },
    'installable': True,
    'auto_install': False,
    'application': False,
}
