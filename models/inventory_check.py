# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
import base64
import io
from io import BytesIO
from openpyxl.reader.excel import load_workbook

try:
    import openpyxl
except ImportError:
    openpyxl = None

class InventoryCheck(models.Model):
    _name = 'inventory.check'
    _description = 'Phiếu kiểm kê kho'

    name = fields.Text(string='Check Name')
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse ID')
    location_id =  fields.Many2one('stock.location', string='Warehouse Location ID')
    employeeCheck_id = fields.Many2one('res.users', string='Employee Check')
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

    # def _compute_display_employeeCheck(self):
    #     for rec in self:
    #         if rec.employeeCheck_id:
    #             rec.display_arehouswe_location = rec.location_id.name
    #         else:
    #             rec.display_warehouse_location = "All Location"

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

    def import_data(self, file):
        if not openpyxl:
            return {'status': 'error', 'message': _('Library openpyxl is not installed.')}
        try:
            file_content = base64.b64decode(file)
            data = BytesIO(file_content)
            workbook = load_workbook(filename=data)
            if 'Phiếu kiểm kê' not in workbook.sheetnames:
                return {
                    'status': 'error',
                    'message': _("Sheet 'Phiếu kiểm kê' không tìm thấy trong file Excel")
                }
            project_sheet = workbook['Phiếu kiểm kê']
            # Extract headers and rows for 'Phiếu kiểm kê' sheet
            project_header = [
                cell.value.strip() if isinstance(cell.value, str) else cell.value
                for cell in next(project_sheet.iter_rows(min_row=1, max_row=1))
            ]  # lấy giá trị dòng đầu của cel (header)
            project_rows = list(project_sheet.iter_rows(min_row=2, values_only=True))  # lấy giá trị trong ô thay vì cel
            print('project_header', project_header)
            print('Number of project rows', project_rows)

            # Required fields for 'Phiếu kiểm kê' sheet
            required_project_field = ['Phiếu kiểm kê', 'Người kiểm kê', 'Sản phẩm']
            for field in required_project_field:
                if field not in project_header:
                    return {
                        'status': 'error',
                        'message': _(f"Thiếu cột bắt buộc: '{field}' trong sheet'Phiếu kiểm kê'")
                    }
            # Header mapping for 'Phiếu kiểm kê' sheet
            project_header_mapping = {
                'Phiếu kiểm kê': 'name',
                'Ngày kiểm kê': 'check_date',
                'Người kiểm kê': 'employeeCheck_id',
                'Kho': 'warehouse_id',
                'Vị trí': 'location_id',
                'Sản phẩm': 'product.id',
                'Số lô/serial': 'lot_id',
                'ĐVT': 'unit_id',
                'Số lượng hiện có': 'quantity',
                'Số lượng đã đếm': 'inventory_quantity',
            }
            # Collect all project codes from 'Phiếu kiểm kê' sheet
            project_codes = set()
            for row in project_rows:
                row_data = {project_header[i]: row[i] for i in range(len(project_header)) if i < len(row)}
                code = row_data.get('Phiếu kiểm kê')
                if code is not None:
                    project_codes.add(str(code).strip())  # convert to string and strip
                else:
                    return {
                        'status': 'error',
                        'message': f"Thiếu 'Phiếu kiểm kê' trong dòng dữ liệu của sheet 'Phiếu kiểm kê': {row_data}"
                    }
            projects = {}
            for row in project_rows:
                row_data = {project_header[i]: row[i] for i in range(len(project_header)) if i < len(row)}
                project_data = self._prepare_project_data(row_data, project_header_mapping)
                if isinstance(project_data, dict) and project_data.get('status') == 'error':
                    return project_data
                project = self._update_or_create_project(project_data)
                if isinstance(project, dict) and project.get('status') == 'error':
                    return project
                projects[project_data['name']] = project
            return {
                'status': 'success',
                'message': 'Nhập dữ liệu thành công!'
            }
        except Exception as e:
            self.env.cr.rollback()
            return {
                "status": "error",
                "message": f"Lỗi khi nhập dữ liệu: {str(e)}"
            }

    def _prepare_project_data(self, row_data, mapping):
        result = {}
        for excel_col, field_name in mapping.items():
            value = row_data.get(excel_col)
            if not value:
                continue
            if field_name in ['user_id', 'warehouse_id', 'location_id', 'uom_id', 'lot_id', 'product.id']:
                model = {
                    'employeeCheck_id': 'res.users',
                    'warehouse_id': 'stock.warehouse',
                    'location_id': 'stock.location',
                    'unit_id': 'uom.uom',
                    'lot_id': 'stock.lot',
                    'product.id': 'product.product',
                }[field_name]
                record = self.env[model].search([('name', '=', value)], limit=1)
                if not record:
                    return {
                        'status': 'error',
                        'message': f"Không tìm thấy '{value}' trong '{excel_col}' (model {model})"
                    }
                result[field_name if field_name != 'product.id' else 'product_id'] = record.id
            else:
                result[field_name] = value
        result['name'] = str(row_data.get('Phiếu kiểm kê')).strip()  # dùng làm mã kiểm kê duy nhất
        return result

    def _update_or_create_project(self, vals):
        # Kiểm tra nếu đã có thì cập nhật, nếu chưa thì tạo mới
        existing = self.search([('name', '=', vals.get('name'))], limit=1)
        if existing:
            existing.write(vals)
            return existing
        else:
            return self.create(vals)
