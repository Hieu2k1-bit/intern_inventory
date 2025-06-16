# -*- coding: utf-8 -*-
{
    'name': 'Intern Inventory',
    'category': 'Inventory',
    'version': '1.0',
    'author': "Nguyen Tien Dat",
    'sequence': "1",
    'description': """
    This module adds Inventory checks
    """,
    'depends':[
        'base', 'stock', 'web',
    ],
    'data': [
        "wizard/wizard_import_kiemke_view.xml",
        "views/inventory_check_view.xml",
        "security/ir.model.access.csv",
        "wizard/wizard_product_view.xml",
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}


