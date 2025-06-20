# -*- coding: utf-8 -*-
{
    'name': "intern_inventory",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,
    'sequence': '1',
    'author': "My Company",
    'website': "https://www.yourcompany.com",
    'category': 'Inventory',
    'version': '0.1',
    'depends': ['base','stock'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/wizard_import_kiemke_view.xml',
        'views/inventory_check.xml',
        'wizard/wizard_product_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
