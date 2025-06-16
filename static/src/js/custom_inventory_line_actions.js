//odoo.define('intern_inventory.custom_inventory_line_actions', function (require) {
//    "use strict";
//
//    var FormController = require('web.FormController'); // Import FormController của Odoo
//    var core = require('web.core');
//    var _t = core._t; // Biến dịch thuật cho các thông báo
//
//    FormController.include({
//        /**
//         * Ghi đè phương thức _onButtonClicked để xử lý các nút tùy chỉnh trên dòng One2many.
//         * Được gọi mỗi khi một nút trên form được nhấn.
//         */
//        _onButtonClicked: function (ev) {
//            var self = this; // Tham chiếu đến FormController hiện tại
//            var attrs = ev.data.attrs; // Lấy thuộc tính (attributes) của nút được nhấn
//            var record = ev.data.record; // Lấy bản ghi mà nút được nhấn thuộc về (ví dụ: một dòng inventory.line)
//
//            // Log để gỡ lỗi: Xem nút nào được nhấn và trên model nào
//            console.log("Button clicked:", attrs.name, "on model:", record.model);
//
//            // Kiểm tra nút click vào có phải là 'action_apply' và rec có thuộc model 'inventory.line' không
//            if (attrs.name === 'action_apply' && record.model === 'inventory.line') {
//                // RẤT QUAN TRỌNG: Ngăn chặn hành vi mặc định của Odoo cho nút type="object".
//                ev.stopPropagation();
//                // console.log("Detected action_apply on inventory.line. Stopping propagation.");
//
//                // Lấy controller của form cha (inventory.check).
//                // this.renderer.el là phần tử DOM của form hiện tại (FormRenderer).
//                // closest('.o_form_view') tìm phần tử cha gần nhất có class 'o_form_view'
//                // .dataset.controller truy cập đối tượng controller JavaScript của form cha
//                var parentFormControllerEl = this.renderer.el.closest('.o_form_view');
//                var parentFormController = parentFormControllerEl ? $(parentFormControllerEl).data('controller') : null;
//
//
//                if (!parentFormController) {
//                    console.warn("Could not find parent FormController. Default action will be executed.");
//                    // Nếu không tìm thấy, gọi lại phương thức gốc để tránh lỗi
//                    return this._super.apply(this, arguments);
//                }
//
//
//                // Kích hoạt quá trình lưu toàn bộ form cha.
//                // parentFormController.saveRecord() trả về một Promise.
//                // Promise này sẽ được resolve nếu việc lưu thành công, hoặc reject nếu có lỗi.
//                parentFormController.saveRecord().then(function () {
//                    // Nếu quá trình lưu form cha thành công, thì mới gọi hàm Python 'action_apply' trên dòng 'inventory.line'.
//                    // self._rpc là hàm gọi RPC (Remote Procedure Call) tới server Odoo.
//                    console.log("Parent record saved successfully! Calling Python RPC for action_apply.");
//                    return self._rpc({
//                        model: record.model,    // Model của bản ghi dòng ('inventory.line')
//                        method: attrs.name,     // Tên phương thức Python được gọi ('action_apply')
//                        args: [[record.res_id]], // Đối số: ID của bản ghi dòng hiện tại trong một danh sách
//                        kwargs: {},             // Đối số từ khóa (nếu có)
//                    }).then(function (result) {
//                        // Bước 3: Xử lý kết quả trả về từ hàm Python.
//                        console.log("Python action_apply RPC successful. Result:", result);
//                        // Nếu hàm Python trả về một action (ví dụ: {'type': 'ir.actions.client', 'tag': 'reload'}),
//                        // chúng ta sẽ thực thi action đó.
//                        if (result && result.type) {
//                            return self.do_action(result); // Thực thi action trả về từ server
//                        } else {
//                            // Nếu hàm Python không trả về action nào,
//                            // chỉ cần làm mới view hiện tại để đảm bảo dữ liệu được cập nhật.
//                            self.reload();
//                        }
//                    }).catch(function (error) {
//                        // Xử lý lỗi nếu RPC call tới Python thất bại
//                        console.error("Error in Python action_apply RPC:", error);
//                        self.displayNotification({
//                            type: 'danger',
//                            message: error.data.message || _t("An error occurred while processing the 'Apply' action."),
//                        });
//                    });
//                }).catch(function (error) {
//                    // Xử lý lỗi nếu quá trình lưu form cha thất bại (ví dụ: lỗi validation, thiếu trường bắt buộc)
//                    console.error("Failed to save form before applying action:", error);
//                    // Odoo thường tự động hiển thị thông báo lỗi validation trên các trường,
//                    // nhưng bạn có thể thêm thông báo tổng quát ở đây nếu cần.
//                    self.displayNotification({
//                        type: 'danger',
//                        message: error.data.message || _t("Failed to save the form. Please correct errors and try again."),
//                    });
//                });
//            } else {
//                // Nếu nút không phải là 'action_apply' trên 'inventory.line',
//                // chúng ta để Odoo xử lý nó theo hành vi mặc định (gọi phương thức _super).
//                console.log("Button is not action_apply on inventory.line. Executing default behavior.");
//                return this._super.apply(this, arguments);
//            }
//        },
//    });
//});
