from email.policy import default

from odoo import fields, models, api, _
from odoo.exceptions import UserError

class InventoryLine(models.Model):
    _name = 'inventory.line'
    _description = 'Inventory Check Line'

    check_id = fields.Many2one('intern_inventory.check', string='Inventory Check line', ondelete='cascade')
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        related='location_id.warehouse_id',
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one('product.product', string='Product', ondelete='cascade')
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial Number')
    uom_id = fields.Many2one('uom.uom', string='Unit')
    location_id = fields.Many2one('stock.location', string='Location', ondelete='cascade')
    quant_id = fields.Many2one('stock.quant', string='Quantity')
    quantity = fields.Float(string='Available Quantity', compute='_compute_quantities')
    quantity_counted = fields.Float(string='Quantity Counted', digits=(16, 0))
    diff_quantity = fields.Float(string='Difference', digits=(16, 0), store=True,
                                 default='0')

    # Đạt
    def action_apply(self):
        self.ensure_one()
        for line in self:
            line.diff_quantity = abs((line.quantity or 0.0) - (line.quantity_counted or 0.0))

    # Việt

    def action_history(self):
        self.ensure_one()
        action = {
            'name': _('History'),
            'view_mode': 'list,form',
            'res_model': 'stock.move.line',
            'views': [(self.env.ref('stock.view_move_line_tree').id, 'list'), (False, 'form')],
            'type': 'ir.actions.act_window',
            'domain': [
                ('product_id', '=', self.product_id.id),
                ('state', '=', 'done'),]

        }
        return action

    def action_delete(self):
        self.ensure_one()
        product_name = self.product_id.display_name
        if self.diff_quantity == 0:
            raise UserError(
                _("Unable to delete unapplied line checklist . Please apply or modify before deleting.."))
        self.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _("Dòng kiểm kê cho sản phẩm '%s' đã được xóa thành công." % product_name),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
    @api.depends('product_id', 'location_id', 'lot_id')
    def _compute_quantities(self):
        for line in self:
            if not line.product_id or not line.location_id:
                line.quantity = 0.0
            else:
                domain = [
                    ('product_id', '=', line.product_id.id),
                    ('location_id', '=', line.location_id.id),
                ]
                if line.lot_id:
                    domain.append(('lot_id', '=', line.lot_id.id))

                quants = self.env['stock.quant'].search(domain)
                line.quantity = sum(quants.mapped('quantity'))
