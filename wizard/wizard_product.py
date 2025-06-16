from odoo import models, fields, api

class ProductSelectionWizard(models.TransientModel):
    _name = 'product.selection.wizard'
    _description = 'Wizard choose products'

    check_id = fields.Many2one('inventory.check', string="Inventory check")
    line_ids = fields.Many2many('product.product', string="Product")


    def action_confirm(self):
        for product in self.line_ids:
            self.env['inventory.line'].create({
                'check_id': self.check_id.id,
                'product_id': product.id,
                'quantity': 0.0,
            })
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        check_id = self.env.context.get('default_check_id')
        if check_id:
            check = self.env['inventory.check'].browse(check_id)
            if check.warehouse_id and check.location_id:
                quants = self.env['stock.quant'].search([
                    ('location_id', '=', check.location_id.id)
                ])
                product_ids = quants.mapped('product_id').ids
                res['line_ids'] = [(6, 0, product_ids)]
        return res
