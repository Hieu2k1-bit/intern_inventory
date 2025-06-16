# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api

class InventoryCheck(models.Model):
    _name = 'inventory.check'
    _description = 'Phiếu kiểm kê kho'

    name = fields.Text(string='Check Name')
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse ID')
    location_id =  fields.Many2one('stock.location', string='Warehouse Location ID')
    employeeCheck = fields.Many2one('res.users', string='Employee Check')
    company = fields.Many2one('res.company', string='Company')
    state = fields.Selection([('ready', 'Ready'), ('done', 'Done')], default='ready', string='State')
    create_datetime = fields.Datetime(string='Create Date', required=True, default=lambda self: fields.Datetime.now())
    check_date = fields.Date(string='Check Date', required=True, default=lambda self: fields.Date.today())
    line_ids = fields.One2many('inventory.line', 'check_id', string='Product Check Lines')

    display_warehouse_name = fields.Char(string ='Warehouse', compute='_compute_display_warehouse_name', store=True)
    display_warehouse_location = fields.Char(string='Warehouse Location', compute='_compute_display_warehouse_location', store=True)

    # @api.depends('warehouse_id')
    def _compute_display_warehouse_name(self):
        for rec in self:
            if rec.warehouse_id:
                rec.display_warehouse_name = rec.warehouse_id.name
            else:
                rec.display_warehouse_name = "All Warehouse"

    # @api.depends('location_id')
    def _compute_display_warehouse_location(self):
        for rec in self:
            if rec.location_id:
                rec.display_warehouse_location = rec.location_id.name
            else:
                rec.display_warehouse_location = "All Location"

    def action_complete(self):
        self.ensure_one()   # Dam bao chi xu ly mot form mot luc
        self.write({'state': 'done',
                    'create_datetime': fields.Datetime.now()})   # Tu dong luu cac thay doi
        return True
        # self.env.ref('intern_inventory.action_inventory_check').read())[0] # Luu form va thoat ra man hinh view

    def action_apply_all(self):
        self.ensure_one()
        for line in self.line_ids:
            line.diff_quantity = abs((line.quantity or 0.0) - (line.inventory_quantity or 0.0))

    def action_open_product_selection(self):
        self.ensure_one()
        return {
            'name': 'Chose Products',
            'type': 'ir.actions.act_window',
            'res_model': 'product.selection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_check_id': self.id,
            }
        }

