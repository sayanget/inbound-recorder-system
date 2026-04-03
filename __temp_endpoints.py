
@app.route('/api/sorting-schedule', methods=['GET'])
def get_sorting_schedule():
    """获取最新的分拣排班配置"""
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT config_json FROM sorting_schedule_config ORDER BY updated_at DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return jsonify(json.loads(result[0] if USE_POSTGRES else result[0]))
        else:
            return jsonify({}) # Return empty object if no config exists
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sorting-schedule', methods=['POST'])
def save_sorting_schedule():
    """保存分拣排班配置"""
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401
    
    # Check edit permission
    if not check_user_permission('sorting-schedule', 'edit'):
        return jsonify({'error': '无权限编辑'}), 403
        
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        # 获取当前洛杉矶时间
        la_tz = pytz.timezone('America/Los_Angeles')
        current_la_time = datetime.now(la_tz)
        current_la_time_str = current_la_time.strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("INSERT INTO sorting_schedule_config (config_json, updated_at) VALUES (?, ?)", 
                      (json.dumps(data), current_la_time_str))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
