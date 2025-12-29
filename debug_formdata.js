// 创建一个简单的测试来验证FormData是否能正确获取time_slot字段的值

// 模拟表单数据
const form = document.createElement('form');
form.innerHTML = `
    <input type="text" name="dock_no" value="1">
    <input type="text" name="vehicle_type" value="Car">
    <input type="text" name="time_slot" value="">
`;

// 获取FormData
const formData = new FormData(form);
console.log('FormData entries:');
for (let [key, value] of formData.entries()) {
    console.log(`${key}: ${value}`);
}

// 检查time_slot是否存在
if (formData.has('time_slot')) {
    console.log('time_slot字段存在');
    console.log('time_slot值:', formData.get('time_slot'));
} else {
    console.log('time_slot字段不存在');
}