from odoo import fields, models, _
from odoo.exceptions import ValidationError


class ProjectWizardImport(models.TransientModel):
    _name = 'project.wizard.import'

    file = fields.Many2many(
        comodel_name="ir.attachment",
        string="File Import",
        required=True,
    )
    file_name = fields.Char(string="File Name")

    def action_import(self):
        if not self.file:
            raise ValidationError(_("Please upload a file for data import."))

        file_data = self.file[0].datas  # Giả sử self.file là binary file field

        # Lấy active_id từ context để xác định phiếu kiểm kê đang thao tác
        active_id = self.env.context.get('active_id')
        if not active_id:
            raise ValidationError(_("Unable to locate inventory sheet for data entry."))

        inventory = self.env['intern_inventory.check'].browse(active_id)
        if not inventory.exists():
            raise ValidationError(_("Inventory sheet does not exist."))

        result = inventory.import_data(file_data)

        if result['status'] == 'success':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('File imported successfully.'),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'}
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': result['message'],
                    'type': 'danger',
                    'sticky': True
                }
            }