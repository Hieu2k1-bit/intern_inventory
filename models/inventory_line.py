from pip._internal.utils._jaraco_text import _

from odoo import fields, models, api

class InventoryLine(models.Model):
    _name = 'inventory.line'
    _description = 'Inventory Check Line'
    _rec_name = 'product_id'
    check_id = fields.Many2one('inventory.check', string='Inventory Check line', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', ondelete='cascade')
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial Number')
    unit_id = fields.Many2one('product.product', string='Unit')
    location_id = fields.Many2one('stock.location', string='Location', related='check_id.location_id', store=True)
    quantity = fields.Float(string='Quantity Available', compute='_compute_quantities', store=False, digits=(16,0))
    inventory_quantity = fields.Float(string='Counted Quantity', digits=(16,0), store=True)
    diff_quantity = fields.Float(string='Difference', digits=(16,0), default='0')

    @api.depends('product_id', 'location_id')
    def _compute_quantities(self):
        for line in self:
            if not line.product_id or not line.location_id:
                line.quantity = 0.0
            else:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', line.product_id.id),
                    ('location_id', '=', line.location_id.id),
                ])
                line.quantity = sum(quants.mapped('quantity'))

    # @api.depends('quantity', 'inventory_quantity')
    # def _compute_difference(self):
    #     for line in self:
    #         line.diff_quantity = abs((line.quantity or 0.0) - (line.inventory_quantity or 0.0))

    def action_history(self):
        self.ensure_one()
        action = {
            'name': _('History'),
            'view_mode': 'list,form',
            'res_model': 'stock.move.line',
            'views': [(self.env.ref('stock.view_move_line_tree').id, 'list'), (False, 'form')],
            'type': 'ir.actions.act_window',
            'context': {
                'search_default_inventory': 1,
                'search_default_done': 1,
                'search_default_product_id': self.product_id.id,
            }
        }
        return action

    def action_apply(self):
        self.ensure_one()
        for line in self:
            line.diff_quantity = abs((line.quantity or 0.0) - (line.inventory_quantity or 0.0))

    def action_delete(self):
        self.ensure_one()
        self.unlink()  # Xóa dòng kiểm kê hiện tại
        return {'type': 'ir.actions.client', 'tag': 'reload'}