from email.policy import default

from odoo import fields, models, api


class InventoryLine(models.Model):
    _name = 'inventory.line'
    _description = 'Inventory Check Line'

    check_id = fields.Many2one('intern_inventory.check', string='Inventory Check line', ondelete='cascade')
    warehouse_id = fields.Many2one("stock.warehouse", string='Warehouse', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', ondelete='cascade')
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial Number')
    uom_id = fields.Many2one('uom.uom', string='Unit')
    location_id = fields.Many2one('stock.location', string='Location',
                                  ondelete='cascade')
    quant_id = fields.Many2one('stock.quant', string='Quantity')
    quantity = fields.Float(string='Available Quantity')
    quantity_counted = fields.Float(string='Quantity Counted', digits=(16, 0))
    diff_quantity = fields.Float(string='Difference', digits=(16, 0), compute='_compute_difference', store=True,
                                 default='0')
    warehouse_display_name = fields.Char(string='Warehouse Name', compute='_compute_warehouse_display_name',

                                         store=False)
    location_display_name = fields.Char(string='Location Name', compute='_compute_location_display_name',
                                        store=False)

    @api.depends('quantity', 'quantity_counted')
    def _compute_difference(self):
        for line in self:
            line.diff_quantity = abs((line.quantity or 0.0) - (line.quantity_counted or 0.0))

    def action_history(self):
        return True

    def action_apply(self):
        self._compute_difference()

    def action_delete(self):
        return True

    @api.depends('warehouse_id')
    def _compute_warehouse_display_name(self):
        for record in self:
            record.warehouse_display_name = record.warehouse_id.name if record.warehouse_id else "All Warehouses"

    @api.depends('location_id')
    def _compute_location_display_name(self):
        for record in self:
            record.location_display_name = record.location_id.name if record.location_id else "All Locations"
