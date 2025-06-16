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

        attachment = self.file[0]
        file_data = attachment.datas
        result = self.env['inventory.check'].import_data(file_data)

        if result['status'] == 'success':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params':{
                    'title': _('Success'),
                    'message': _('Successfully imported file!'),
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.act_window_close',
                        'next': {'type': 'ir.actions.client', 'tag': 'reload'}
                    }
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Errorx`'),
                    'message': result['message'],
                    'type': 'danger',
                    'sticky': True,
                    'next': {
                        'type': 'ir.actions.act_window_close',
                    }
                }
            }


