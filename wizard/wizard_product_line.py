from odoo import models, fields, api

class ProductSelectionLineWizard(models.TransientModel):
    _name = 'product.selection.line.wizard'
    _description = ''

    wizard_id = fields.Many2one('product.selection.wizard', string='Wizard')
    product_id = fields.Many2one('product.product', string='Product')
    internal_reference = fields.Char(string='Internal Reference')
    location_id = fields.Many2one('stock.location', string='Location')
    check_id = fields.Many2one('intern_inventory.check', string="Inventory")


    def action_confirm(self):
        check_id = self.env.context.get('default_check_id')
        if not check_id:
            return

        check = self.env['intern_inventory.check'].browse(check_id)

        for line in self:
            lot_id = False
            quant = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id', '=', line.location_id.id),
                ('lot_id', '!=', False),
            ], limit=1)
            if quant:
                lot_id = quant.lot_id.id

            self.env['inventory.line'].create({
                'check_id': check.id,
                'product_id': line.product_id.id,
                'location_id': line.location_id.id,
                'lot_id': lot_id,
                'uom_id': line.product_id.uom_id.id,
                'quantity_counted': 0.0,
            })

        return {'type': 'ir.actions.act_window_close'}