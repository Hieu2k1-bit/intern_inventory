import base64
import io
from io import BytesIO
from odoo import models, fields, api, _
from openpyxl.reader.excel import load_workbook
# from reportlab.graphics.shapes import translate
import xlsxwriter
from odoo.exceptions import UserError

try:
    import openpyxl
except ImportError:
    openpyxl = None


class InternInventory(models.Model):
    _name = 'intern_inventory.check'
    _description = 'Inventory Check Sheet'

    name = fields.Char(string='Name', required=True)

    # warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse")
    warehouse_ids = fields.Many2many('stock.warehouse', 'intern_inventory_warehouse_rel',
                                     'check_id','warehouse_id', string='Warehouses')
    location_ids = fields.Many2many('stock.location','intern_inventory_location_rel',
                                   'check_id','location_id', string="Location")
    user_id = fields.Many2one('res.users', string="Employee check")
    create_date = fields.Datetime(string="Create date", required=True, default=fields.Datetime.now)
    inventory_date = fields.Date(string="Inventory date", required=True, default=fields.Date.today)
    state = fields.Selection([('ready', 'READY'), ('done', 'DONE')],
                             string='Status', default='ready', readonly=True)
    company = fields.Many2one('res.company', string='Company')

    product_id = fields.Many2one('product.product', string="Product List")
    lot_id = fields.Many2one('stock.lot', string="Lot/Serial Number")
    uom_id = fields.Many2one('uom.uom', string="Unit of Measure")
    quantity = fields.Float(string="Available Quantity")
    quantity_counted = fields.Float(string="Quantity Counted")
    line_ids = fields.One2many('inventory.line', 'check_id',
                               string='Product Check Lines')
    is_imported = fields.Boolean(string='Imported', default=False)

    warehouse_display_name = fields.Char(
        string='Warehouses',
        compute='_compute_warehouse_display_name',
        store=True
    )

    location_display_name = fields.Char(
        string='Locations',
        compute='_compute_location_display_name',
        store=True
    )
    state_display_name = fields.Char(
        string='Status',
        compute='_compute_state_display_name',
        store=True
    )

    @api.depends('state')
    def _compute_state_display_name(self):
        for rec in self:
            if rec.state == 'ready':
                rec.state_display_name = "Ready"
            else:
                rec.state_display_name = "Done"

    @api.depends('warehouse_ids.name')  # Cập nhật dependencies
    def _compute_warehouse_display_name(self):
        for record in self:
            if record.warehouse_ids:
                record.warehouse_display_name = ", ".join(record.warehouse_ids.mapped('name'))
            else:
                record.warehouse_display_name = "All Warehouses"

    @api.depends('location_ids.name')
    def _compute_location_display_name(self):
        for record in self:
            if record.location_ids:
                record.location_display_name = ", ".join(record.location_ids.mapped('name'))
            else:
                record.location_display_name = "All Locations"

    # @api.onchange('warehouse_id')
    # def _onchange_warehouse_id(self):
    #     if self.warehouse_id:
    #         # Lọc các vị trí thuộc kho đã chọn
    #         self.location_id = False  # Xóa vị trí cũ nếu kho thay đổi
    #         return {
    #             'domain': {'location_id': [('warehouse_id', '=', self.warehouse_id.id)]}
    #         }
    #     else:
    #         # Nếu không chọn kho: lọc tất cả location trong tất cả các kho
    #         all_warehouses = self.env['stock.warehouse'].search([])
    #         warehouse_view_locations = all_warehouses.mapped('view_location_id')
    #         all_locations = self.env['stock.location'].search([
    #             ('location_id', 'child_of', warehouse_view_locations.ids),
    #             ('usage', '=', 'internal')
    #         ])
    #         return {
    #             'domain': {'location_id': [('id', 'in', all_locations.ids)]}
    #         }

    @api.onchange('warehouse_ids')
    def _onchange_warehouses_ids(self):
        # When warehouse_ids change, reset location_ids and update domain
        self.location_ids = [(5, 0, 0)]  # Delete all selected location

        if self.warehouse_ids:
            # Lấy tất cả view_location_id từ các kho đã chọn
            warehouse_view_locations = self.warehouse_ids.mapped('view_location_id')
            if warehouse_view_locations:
                # Tìm tất cả internal locations là con của các view_location_id này
                all_locations_in_selected_warehouses = self.env['stock.location'].search([
                    ('location_id', 'child_of', warehouse_view_locations.ids),
                    ('usage', '=', 'internal')
                ])
                return {
                    'domain': {'location_ids': [('id', 'in', all_locations_in_selected_warehouses.ids)]}
                }
            else:
                # Không tìm thấy view_location_id cho các kho đã chọn
                return {'domain': {'location_ids': [('id', '=', False)]}}  # Không có location nào để chọn
        else:
            # Nếu không chọn kho nào, cho phép chọn tất cả các internal locations
            all_warehouses = self.env['stock.warehouse'].search([])
            warehouse_view_locations = all_warehouses.mapped('view_location_id')
            all_locations = self.env['stock.location'].search([
                ('location_id', 'child_of', warehouse_view_locations.ids),
                ('usage', '=', 'internal')
            ])
            return {
                'domain': {'location_ids': [('id', 'in', all_locations.ids)]}
            }

    def action_ready(self):
        self.ensure_one()
        self.write({'state': 'ready'})

    def action_done(self):
        self.ensure_one()
        self.write({'state': 'done'})


    def action_open_product_selection(self):
        self.ensure_one()
        # Xóa các dòng wizard cũ liên quan đến phiếu kiểm kê này
        self.env['product.selection.line.wizard'].search([('check_id', '=', self.id)]).unlink()

        # Khởi tạo domain quants
        quant_domain = [('quantity', '>', 0)]

        # Lấy danh sách ID các vị trí hợp lệ
        valid_location_ids = []

        if self.location_ids:  # Nếu có locations được chọn (Many2Many)
            # Lấy các ID của các vị trí đã chọn trực tiếp
            valid_location_ids = self.location_ids.ids
        elif self.warehouse_ids:  # Nếu không có vị trí cụ thể được chọn, nhưng có KHO được chọn (Many2Many)
            # Lấy tất cả các internal location thuộc các warehouse đã chọn
            warehouse_view_locations = self.warehouse_ids.mapped('view_location_id')
            all_locations_in_selected_warehouses = self.env['stock.location'].search([
                ('location_id', 'child_of', warehouse_view_locations.ids),
                ('usage', '=', 'internal')
            ])
            valid_location_ids = all_locations_in_selected_warehouses.ids
        else:
            # Nếu không có cả kho và vị trí nào được chọn trên phiếu kiểm kê,
            all_internal_locations = self.env['stock.location'].search([('usage', '=', 'internal')])
            valid_location_ids = all_internal_locations.ids

        quant_domain.append(('location_id', 'in', valid_location_ids))


        # Truy vấn các quants phù hợp
        quants = self.env['stock.quant'].search(quant_domain)

        for quant in quants:
            # Đảm bảo chỉ thêm các quant có số lượng > 0 và chưa tồn tại trong line_ids
            # Kiểm tra trùng lặp để tránh thêm một sản phẩm/lot/location vào wizard nhiều lần
            existing_line = self.env['product.selection.line.wizard'].search([
                ('check_id', '=', self.id),
                ('product_id', '=', quant.product_id.id),
                ('location_id', '=', quant.location_id.id),
                ('lot_id', '=', quant.lot_id.id if quant.lot_id else False),
            ], limit=1)

            if not existing_line:
                self.env['product.selection.line.wizard'].create({
                    'product_id': quant.product_id.id,
                    'internal_reference': quant.product_id.default_code,
                    'location_id': quant.location_id.id,
                    'lot_id': quant.lot_id.id if quant.lot_id else False,
                    'quantity': quant.quantity,  # Hiển thị số lượng hiện có trong wizard
                    'check_id': self.id,
                })

        return {
            'name': 'Chọn sản phẩm từ tồn kho',
            'type': 'ir.actions.act_window',
            'res_model': 'product.selection.line.wizard',
            'view_mode': 'tree,form',
            'domain': [('check_id', '=', self.id)],
            'target': 'new',
            'context': {
                'default_check_id': self.id,
            },
        }
    # Bao
    #     def action_export_excel(self):
    #         for rec in self:
    #             output = BytesIO()
    #             workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    #             sheet = workbook.add_worksheet('Kiểm kê kho')
    #
    #             sheet.set_column(0, 0, 20)
    #             sheet.set_column(1, 1, 15)
    #             sheet.set_column(2, 2, 20)
    #             sheet.set_column(3, 3, 15)
    #             sheet.set_column(4, 4, 20)
    #             sheet.set_column(5, 5, 25)
    #             sheet.set_column(6, 6, 20)
    #             sheet.set_column(7, 7, 10)
    #             sheet.set_column(8, 8, 15)
    #             sheet.set_column(9, 9, 15)
    #
    #             header_format = workbook.add_format({
    #                 'bold': True,
    #                 'font_color': 'red',
    #                 'align': 'center',
    #                 'valign': 'vcenter',
    #                 'bg_color': '#F9F9F9',
    #                 'border': 1
    #             })
    #
    #             headers = [
    #                 'Phiếu kiểm kê', 'Ngày kiểm kê', 'Người kiểm kê',
    #                 'Kho', 'Vị trí', 'Sản phẩm', 'Số lô/serial',
    #                 'ĐVT', 'Số lượng hiện có', 'Số lượng đã đếm'
    #             ]
    #             for col_num, header in enumerate(headers):
    #                 sheet.write(0, col_num, header, header_format)
    #
    #             row = 1
    #             for line in rec.line_ids:
    #                 sheet.write(row, 0, rec.name or '')
    #                 sheet.write(row, 1, str(rec.inventory_date or ''))
    #                 sheet.write(row, 2, rec.user_id.name or '')
    #                 # Hiển thị tên kho từ dòng kiểm kê, hoặc các kho được chọn trên phiếu
    #                 sheet.write(row, 3, line.warehouse_id.name if line.warehouse_id else (
    #                     ", ".join(rec.warehouse_ids.mapped('name')) if rec.warehouse_ids else 'Tất cả kho'))
    #                 sheet.write(row, 4, line.location_id.display_name or line.location_id.complete_name or '')
    #                 sheet.write(row, 5, line.product_id.name or '')
    #                 sheet.write(row, 6, line.lot_id.name if line.lot_id else '')
    #                 sheet.write(row, 7, line.uom_id.name if line.uom_id else '')
    #                 sheet.write(row, 8, line.quantity or 0)
    #                 sheet.write(row, 9, line.quantity_counted or 0)
    #                 row += 1
    #
    #             workbook.close()
    #             output.seek(0)
    #             data = output.read()
    #
    #             export_attachment = self.env['ir.attachment'].create({
    #                 'name': f'PhieuKiemKe_{rec.name}.xlsx',
    #                 'type': 'binary',
    #                 'datas': base64.b64encode(data),
    #                 'res_model': 'intern_inventory.check',
    #                 'res_id': rec.id,
    #             })
    #
    #             return {
    #                 'type': 'ir.actions.act_url',
    #                 'url': f'/web/content/{export_attachment.id}?download=true',
    #                 'target': 'self',
    #             }

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

                # CẬP NHẬT LOGIC HIỂN THỊ KHO
                warehouse_info = line.warehouse_id.name if line.warehouse_id else ""
                if not warehouse_info and rec.warehouse_ids:
                    warehouse_info = ", ".join(rec.warehouse_ids.mapped('name'))
                elif not warehouse_info:  # Nếu không có cả line.warehouse_id và rec.warehouse_ids
                    warehouse_info = 'Tất cả kho'
                sheet.write(row, 3, warehouse_info)

                # CẬP NHẬT LOGIC HIỂN THỊ VỊ TRÍ
                location_info = line.location_id.display_name or line.location_id.complete_name or ""
                if not location_info and rec.location_ids:
                    location_info = ", ".join(rec.location_ids.mapped('name'))
                elif not location_info:  # Nếu không có cả line.location_id và rec.location_ids
                    location_info = 'Tất cả vị trí'
                sheet.write(row, 4, location_info)

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

    # Đạt
    def action_complete(self):
        self.ensure_one()  # Dam bao chi xu ly mot form mot luc
        self.write({'state': 'done',
                    'create_date': fields.Datetime.now()})  # Tu dong luu cac thay doi
        return True
        # self.env.ref('intern_inventory.action_inventory_check').read())[0] # Save and move to list view

    def action_apply_all(self):
        self.ensure_one()
        for line in self.line_ids:
            line.diff_quantity = abs((line.quantity or 0.0) - (line.quantity_counted or 0.0))

