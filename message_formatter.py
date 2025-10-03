# message_formatter.py
import json
import os
import sys

def _load_templates():
    """メッセージテンプレートをJSONファイルから読み込む"""
    template_file = 'message_templates.json'
    if not os.path.exists(template_file):
        print(f"エラー: メッセージテンプレートファイル '{template_file}' が見つかりません。")
        sys.exit(1)
    
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            templates = json.load(f)
        return templates
    except Exception as e:
        print(f"エラー: テンプレートファイル '{template_file}' の読み込みに失敗しました: {e}")
        sys.exit(1)

MESSAGE_TEMPLATES = _load_templates()

def _format_message(template_lines, params):
    """テンプレートとパラメータから最終的なメッセージ文字列を生成する内部関数"""
    if not template_lines:
        return "メッセージテンプレートが設定されていません。"
    message = "\n".join(template_lines)
    return message.format(**params)

def create_availability_message(notification_method, url, times):
    """空き発見の通知メッセージを作成する"""
    template_lines = MESSAGE_TEMPLATES.get('availability_found', {}).get(notification_method, [])
    
    # 時間のリストを見やすい文字列にフォーマットする
    if times:
        times_list_str = "\n".join([f"- {t}" for t in times])
    else:
        times_list_str = "見つかりませんでした。"
        
    params = {
        'url': url,
        'times_list': times_list_str
    }
    return _format_message(template_lines, params)
def create_success_message(notification_method, url, date, time):
    """応募成功の通知メッセージを作成する"""
    template_lines = MESSAGE_TEMPLATES.get('application_success', {}).get(notification_method, [])
    
    params = {
        'url': url,
        'date': date,
        'time': time
    }
    return _format_message(template_lines, params)