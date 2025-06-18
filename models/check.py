import base64
import io
from io import BytesIO

from odoo import models, fields, api, _
from openpyxl.reader.excel import load_workbook
from reportlab.graphics.shapes import translate
import xlsxwriter

try:
    import openpyxl
except ImportError:
    openpyxl = None


class InternInventory(models.Model):
    _name = 'intern_inventory.check'
    _description = 'Inventory Check Sheet'

    name = fields.Char(string='Name', required=True)

    warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse")
    location_id = fields.Many2one('stock.location', string="Location")
    user_id = fields.Many2one('res.users', string="Responsible Person", default=lambda self: self.env.user)
    create_date = fields.Datetime(string="Create date", required=True, default=fields.Datetime.now)
    inventory_date = fields.Date(string="Inventory date", required=True, default=fields.Date.today)
    state = fields.Selection([
        ('ready', 'READY'),
        ('done', 'DONE'),
    ], string='Status', default='ready', readonly=True)
    company_name = fields.Char(string="Company", default="My Company1")

    warehouse_display_name = fields.Char(
        string='Warehouse',
        compute='_compute_warehouse_display_name',
        store=True
    )

    location_display_name = fields.Char(
        string='Location',
        compute='_compute_location_display_name',
        store=True
    )
    state_display_name = fields.Char(
        string='Status',
        compute='_compute_state_display_name',
        store=True
    )
    product_id = fields.Many2one('product.product', string="Product List")
    lot_id = fields.Many2one('stock.lot', string="Lot/Serial Number")
    uom_id = fields.Many2one('uom.uom', string="Unit of Measure")
    quantity = fields.Float(string="Available Quantity")
    quantity_counted = fields.Float(string="Quantity Counted")
    line_ids = fields.One2many('inventory.line', 'check_id', string='Product Check Lines')
    line_ids_visible = fields.One2many(
        'inventory.line',
        'check_id',
        string='Visible Product Lines',
        compute='_compute_line_ids_visible',
        store=False
    )

    @api.depends('warehouse_id', 'line_ids.product_id', 'location_id')
    def _compute_line_ids_visible(self):
        for record in self:
            visible_lines = record.line_ids
            if record.warehouse_id:
                visible_lines = visible_lines.filtered(lambda l: l.warehouse_id.id == record.warehouse_id.id)
            if record.location_id:
                visible_lines = visible_lines.filtered(lambda l: l.location_id.id == record.location_id.id)
            record.line_ids_visible = visible_lines

    @api.depends('state')
    def _compute_state_display_name(self):
        for rec in self:
            if rec.state == 'ready':
                rec.state_display_name = "Ready"
            else:
                rec.state_display_name = "Done"

    @api.onchange('location_id')
    def _onchange_location_id(self):
        # Trigger logic lại (dù không bắt buộc nếu bạn để compute đúng)
        for rec in self:
            rec._compute_line_ids_visible()

    @api.depends('warehouse_id')
    def _compute_warehouse_display_name(self):
        for record in self:
            record.warehouse_display_name = record.warehouse_id.name if record.warehouse_id else "All Warehouses"

    @api.depends('location_id')
    def _compute_location_display_name(self):
        for record in self:
            record.location_display_name = record.location_id.name if record.location_id else "All Locations"

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        self.ensure_one()

        self.location_id = False

        if self.warehouse_id:
            # Lấy tất cả vị trí nội bộ trong kho
            internal_locations = self.env['stock.location'].search([
                ('location_id', 'child_of', self.warehouse_id.view_location_id.id),
                ('usage', '=', 'internal')
            ])

            # Tìm các sản phẩm có trong các vị trí đó
            product_ids = self.env['stock.quant'].search([
                ('location_id', 'in', internal_locations.ids)
            ]).mapped('product_id').ids

            # Cập nhật warehouse_id cho các dòng con
            for line in self.line_ids:
                line.warehouse_id = self.warehouse_id.id

            # Lọc lại dòng chỉ chứa sản phẩm trong kho
            self.line_ids = self.line_ids.filtered(lambda l: l.product_id.id in product_ids)

            domain_location = [('id', 'in', internal_locations.ids)]
        else:
            # Nếu không chọn kho
            all_locations = self.env['stock.location'].search([
                ('usage', '=', 'internal')
            ])
            domain_location = [('id', 'in', all_locations.ids)]

        return {
            'domain': {
                'location_id': domain_location,
                # Không trả domain product_id nếu nó nằm trong dòng con
            }
        }

    def action_ready(self):
        self.ensure_one()
        self.write({'state': 'ready'})

    def action_done(self):
        self.ensure_one()
        self.write({'state': 'done'})

    def get_warehouse_from_location(self, loc):
        current_loc = loc
        while current_loc and current_loc.usage != 'view':
            current_loc = current_loc.location_id
        if current_loc:
            return self.env['stock.warehouse'].search([('view_location_id', '=', current_loc.id)], limit=1)
        return False

    def import_data(self, file):
        self.ensure_one()
        if not openpyxl:
            return {'status': 'error', 'message': _('Library openpyxl is not installed.')}
        try:
            file_content = base64.b64decode(file)
            data = BytesIO(file_content)
            workbook = load_workbook(filename=data)
            if 'Phiếu kiểm kê' not in workbook.sheetnames:
                return {
                    'status': 'error',
                    'message': _("Sheet 'Phiếu kiểm kê' not found in Excel file")
                }
            project_sheet = workbook['Phiếu kiểm kê']
            # Extract headers and rows for 'Phiếu kiểm kê' sheet
            project_header = [
                str(cell.value or '').strip()
                for cell in next(project_sheet.iter_rows(min_row=1, max_row=1))
            ]  # lấy giá trị dòng đầu của cel (header)
            project_rows = list(project_sheet.iter_rows(min_row=2, values_only=True))  # lấy giá trị trong ô thay vì cel
            print('project_header', project_header)
            print('Number of project rows', project_rows)

            # Required fields for 'Phiếu kiểm kê' sheet
            required_project_field = ['Kho', 'Vị trí', 'Sản phẩm']
            for field in required_project_field:
                if field not in project_header:
                    return {
                        'status': 'error',
                        'message': _(f"Thiếu cột bắt buộc: '{field}' trong sheet'Phiếu kiểm kê'")
                    }
            # Header mapping for 'Phiếu kiểm kê' sheet
            project_header_mapping = {
                'Kho': 'warehouse_id',
                'Vị trí': 'location_id',
                'Sản phẩm': 'product_id',
                'Số lô/serial': 'lot_id',
                'ĐVT': 'uom_id',
                'Số lượng hiện có': 'quantity',
                'Số lượng đã đếm': 'quantity_counted',
            }
            # Collect all project codes from 'Phiếu kiểm kê' sheet
            project_codes = set()
            for row in project_rows:
                # Đảm bảo tất cả các giá trị trong row_data là chuỗi
                row_data = {}
                for i in range(len(project_header)):
                    if i < len(row):
                        header_key = project_header[i]
                        cell_value = row[i]
                        row_data[header_key] = str(cell_value or '').strip()
                    else:
                        # Gán chuỗi rỗng nếu hàng có ít cột hơn tiêu đề
                        row_data[project_header[i]] = ''
                code = row_data.get('Sản phẩm')
                if code is not None:
                    project_codes.add(str(code).strip())
                else:
                    return {
                        'status': 'error',
                        'message': f"Missing 'Sản phẩm' in the data row of the 'Phiếu kiểm kê' sheet: {row_data}"
                    }
            # Gom nhóm dữ liệu theo 'Phiếu kiểm kê'
            line_vals = []
            processed_products = set()
            for row in project_rows:
                # Tạo dict row_data từ dòng Excel
                row_data = {}
                for i in range(len(project_header)):
                    if i < len(row):
                        header_key = project_header[i]
                        cell_value = row[i]
                        row_data[header_key] = str(cell_value or '').strip()
                    else:
                        row_data[project_header[i]] = ''

                # --- Xử lý Kho ---
                warehouse = False
                warehouse_name_from_excel = row_data.get('Kho')
                warehouse_name_from_excel = warehouse_name_from_excel.strip() if warehouse_name_from_excel else ''

                if warehouse_name_from_excel:
                    warehouse = self.env['stock.warehouse'].search([('name', '=', warehouse_name_from_excel)], limit=1)
                    if not warehouse:
                        return {'status': 'error', 'message': f"No warehouse found: '{warehouse_name_from_excel}'."}

                # --- Xử lý Vị trí ---
                location = False
                location_name_from_excel = row_data.get('Vị trí')
                location_name_from_excel = location_name_from_excel.strip() if location_name_from_excel else ''

                location_provided_in_excel = False
                if location_name_from_excel:
                    location_provided_in_excel = True
                    location_domain = [('name', '=', location_name_from_excel)]

                    if warehouse:
                        warehouse_view_location = warehouse.view_location_id
                        if warehouse_view_location:
                            location_domain.append(('location_id', 'child_of', warehouse_view_location.id))
                        else:
                            return {'status': 'error', 'message': f"Warehouse '{warehouse.name}' no main position."}

                    location = self.env['stock.location'].search(location_domain, limit=1)
                    if not location:
                        warehouse_part = f"trong kho '{warehouse.name}'" if warehouse else ""
                        return {'status': 'error',
                                'message': f"Location not found: '{location_name_from_excel}' {warehouse_part}."}

                # Kiểm tra vị trí thuộc kho không
                if warehouse and location_provided_in_excel and location:
                    warehouse_of_location = self.get_warehouse_from_location(location)
                    if not warehouse_of_location or warehouse_of_location.id != warehouse.id:
                        return {'status': 'error',
                                'message': f"Location '{location.name}' is not in the warehouse '{warehouse.name}'."}

                # --- Xử lý sản phẩm ---
                product_name = row_data.get('Sản phẩm')
                if not product_name or not isinstance(product_name, str):
                    return {'status': 'error', 'message': _("Invalid or missing product name.")}
                product_key = product_name.strip().lower()
                if product_key in processed_products:
                    continue
                processed_products.add(product_key)
                product = self.env['product.product'].search([('default_code', '=', product_name)], limit=1)
                if not product:
                    return {'status': 'error', 'message': f"Product code not found: {product_name}"}

                # Tìm lot, uom
                lot_name = row_data.get('Số lô/serial')
                lot = False
                if lot_name and str(lot_name).strip():
                    lot = self.env['stock.lot'].search([('name', '=', str(lot_name).strip())], limit=1)
                uom_name = row_data.get('ĐVT')
                uom = False
                if uom_name and str(uom_name).strip():
                    uom = self.env['uom.uom'].search([('name', '=', str(uom_name).strip())], limit=1)

                # Nếu ô ĐVT trống hoặc không tìm thấy, lấy đơn vị tính mặc định của sản phẩm
                if not uom and product.uom_id:
                    uom = product.uom_id

                # Tìm quant
                quant_domain = [('product_id', '=', product.id)]
                if lot:
                    quant_domain.append(('lot_id', '=', lot.id))

                if location:
                    quant_domain.append(('location_id', '=', location.id))
                elif warehouse:
                    all_warehouse_internal_locations = self.env['stock.location'].search(
                        [('warehouse_id', '=', warehouse.id), ('usage', '=', 'internal')])
                    if all_warehouse_internal_locations:
                        quant_domain.append(('location_id', 'in', all_warehouse_internal_locations.ids))
                    else:
                        return {'status': 'error',
                                'message': f"No internal locations found in the warehouse: {warehouse.name}."}

                quant = self.env['stock.quant'].search(quant_domain, limit=1)
                if not quant:
                    error_message = f"Sản phẩm '{product.name}'"
                    if lot:
                        error_message += f" (Số lô/serial: '{lot.name}')"
                    if location:
                        error_message += f" not in location '{location.name}'."
                    elif warehouse:
                        error_message += f" not in warehouse '{warehouse.name}'."
                    else:
                        error_message += f" does not exist in any location."
                    return {'status': 'error', 'message': error_message}

                # Thêm dòng vào line_vals
                line_vals.append((0, 0, {
                    'product_id': product.id,
                    'lot_id': lot.id if lot else False,
                    'uom_id': uom.id if uom else False,
                    'quant_id': quant.id if quant else False,
                    'quantity': quant.quantity if quant else 0,
                    'quantity_counted': row_data.get('Số lượng đã đếm') or 0,
                    'warehouse_id': warehouse.id if warehouse else False,
                    'location_id': location.id if location else False,
                }))

            # Chuẩn bị dữ liệu phiếu kiểm kê từ dòng đầu
            first_row_data = {}
            for i in range(len(project_header)):
                if i < len(project_rows[0]):
                    header_key = project_header[i]
                    cell_value = project_rows[0][i]
                    first_row_data[header_key] = str(cell_value or '').strip()
                else:
                    first_row_data[project_header[i]] = ''

            main_data = self._prepare_project_data(first_row_data, project_header_mapping)
            if isinstance(main_data, dict) and main_data.get('status') == 'error':
                return main_data
            if not main_data.get('name'):
                main_data['name'] = self.name
            # Xóa kho và vị trí khỏi dữ liệu để không tự động ghi
            main_data.pop('warehouse_id', None)
            main_data.pop('location_id', None)
            # Viết dữ liệu phiếu kiểm kê
            self.write(main_data)
            self.line_ids.unlink()
            self.write({'line_ids': line_vals})

            return {
                'status': 'success',
                'message': 'Data import successful!'
            }
        except Exception as e:
            self.env.cr.rollback()
            return {
                "status": "error",
                "message": f"Error while entering data: {str(e)}"
            }

    def _prepare_project_data(self, row_data, mapping):
        result = {}
        for excel_col, field_name in mapping.items():
            value = row_data.get(excel_col)
            if not value:
                continue
            if field_name in ['warehouse_id', 'location_id', 'uom_id', 'lot_id', 'product_id']:
                model = {
                    'warehouse_id': 'stock.warehouse',
                    'location_id': 'stock.location',
                    'uom_id': 'uom.uom',
                    'lot_id': 'stock.lot',
                    'product_id': 'product.product',
                }[field_name]
                model_env = self.env[model].with_context(lang='en_US')
                if field_name == 'product_id':
                    domain = [('default_code', '=', str(value))]
                else:
                    domain = [('name', '=', str(value))]
                record = model_env.search(domain, limit=1)
                if not record:
                    return {
                        'status': 'error',
                        'message': f"Not found '{value}' in '{excel_col}' (model {model})"
                    }
                result[field_name if field_name != 'product_id' else 'product_id'] = record.id
            else:
                result[field_name] = value
        inventory_check_name = row_data.get('Phiếu kiểm kê')
        result['name'] = str(
            inventory_check_name).strip() if inventory_check_name is not None else ''  # dùng làm mã kiểm kê duy nhất
        return result

    def action_open_product_selection(self):
        self.ensure_one()

        # Nếu không có kho hoặc vị trí cụ thể nào được chọn, thêm trực tiếp tất cả sản phẩm có tồn kho
        if not self.warehouse_id and not self.location_id:
            all_quants = self.env['stock.quant'].search([])
            existing_product_location_ids = self.line_ids.read_group(
                [('check_id', '=', self.id)],
                ['product_id', 'location_id'],
                ['product_id', 'location_id']
            )
            existing_product_location_set = {
                (item['product_id'][0], item['location_id'][0]) for item in existing_product_location_ids
            }

            products_to_add = []
            for quant in all_quants:
                product_location_key = (quant.product_id.id, quant.location_id.id)
                if product_location_key not in existing_product_location_set:
                    products_to_add.append({
                        'check_id': self.id,
                        'product_id': quant.product_id.id,
                        'location_id': quant.location_id.id,
                        'lot_id': quant.lot_id.id if quant.lot_id else False,
                        'uom_id': quant.product_id.uom_id.id,
                        'quantity': quant.quantity,
                        'quantity_counted': 0.0,
                    })
                    existing_product_location_set.add(product_location_key)

            if products_to_add:
                self.env['intern_inventory.line'].create(products_to_add)

            # Tải lại chế độ xem biểu mẫu hiện tại để hiển thị các dòng mới được thêm
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'intern_inventory.check',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'current',
            }

        # Ngược lại, mở trình hướng dẫn để lựa chọn
        return {
            'name': 'Chọn Sản phẩm',
            'type': 'ir.actions.act_window',
            'res_model': 'product.selection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_check_id': self.id,
            }
        }

    def action_export_excel(self):
        for rec in self:
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet('Kiểm kê kho')

            sheet.set_column(0, 0, 20)
            sheet.set_column(1, 1, 15)
            sheet.set_column(2, 2, 20)
            sheet.set_column(3, 3, 15)
            sheet.set_column(4, 4, 20)
            sheet.set_column(5, 5, 25)
            sheet.set_column(6, 6, 20)
            sheet.set_column(7, 7, 10)
            sheet.set_column(8, 8, 15)
            sheet.set_column(9, 9, 15)

            header_format = workbook.add_format({
                'bold': True,
                'font_color': 'red',
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#F9F9F9',
                'border': 1
            })

            headers = [
                'Phiếu kiểm kê', 'Ngày kiểm kê', 'Người kiểm kê',
                'Kho', 'Vị trí', 'Sản phẩm', 'Số lô/serial',
                'ĐVT', 'Số lượng hiện có', 'Số lượng đã đếm'
            ]
            for col_num, header in enumerate(headers):
                sheet.write(0, col_num, header, header_format)

            row = 1
            for line in rec.line_ids:
                sheet.write(row, 0, rec.name or '')
                sheet.write(row, 1, str(rec.inventory_date or ''))
                sheet.write(row, 2, rec.user_id.name or '')
                sheet.write(row, 3, rec.warehouse_id.name if rec.warehouse_id else 'Tất cả kho')
                sheet.write(row, 4, line.location_id.display_name or line.location_id.complete_name or '')
                sheet.write(row, 5, line.product_id.name or '')
                sheet.write(row, 6, line.lot_id.name if line.lot_id else '')
                sheet.write(row, 7, line.uom_id.name if line.uom_id else '')
                sheet.write(row, 8, line.quantity or 0)
                sheet.write(row, 9, line.quantity_counted or 0)
                row += 1

            workbook.close()
            output.seek(0)
            data = output.read()

            export_attachment = self.env['ir.attachment'].create({
                'name': f'PhieuKiemKe_{rec.name}.xlsx',
                'type': 'binary',
                'datas': base64.b64encode(data),
                'res_model': 'intern_inventory.check',
                'res_id': rec.id,
            })

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{export_attachment.id}?download=true',
                'target': 'self',
            }
