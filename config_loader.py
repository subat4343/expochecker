# config_loader.py
import sys
import configparser
import os

def load_config():
    """設定ファイル(config.ini)を読み込み、辞書として返す"""
    config_file = 'config.ini'
    if not os.path.exists(config_file):
        print(f"エラー: 設定ファイル '{config_file}' が見つかりません。")
        sys.exit(1)

    config = configparser.RawConfigParser()
    config.read(config_file, 'utf-8')

    try:
        settings = {
            'interval': config.getint('SETTINGS', 'CheckIntervalSeconds'),
            'notification_method': config.get('SETTINGS', 'NotificationMethod', fallback='none').lower(),
            'refresh_mode': config.getint('SETTINGS', 'RefreshMode', fallback=0),
            'ticket_mode': config.getint('SETTINGS', 'TicketMode', fallback=0),
            'target_date': config.get('MONITOR', 'TargetDate'),
            'full_icon_src': config.get('MONITOR', 'FullIconSrc'),
            'available_time_icon_src': config.get('MONITOR', 'AvailableTimeIconSrc'),

            'debugger_address': config.get('BROWSER', 'DebuggerAddress'),
        }

        method = settings['notification_method']
        if method == 'discord':
            settings['webhook_url'] = config.get('DISCORD', 'WebhookURL')
        # --- ログイン機能のための設定読み込み ---
        # ログイン情報はオプションとする
        if config.has_section('LOGIN'):
            settings['expo_id'] = config.get('LOGIN', 'ExpoID', fallback=None)
            settings['password'] = config.get('LOGIN', 'Password', fallback=None)
            settings['gmail_app_password'] = config.get('LOGIN', 'GmailAppPassword', fallback=None)

        if config.has_section('TICKET_INFO'):
            settings['ticket_id'] = config.get('TICKET_INFO', 'TicketID', fallback=None)

        required_keys = ['target_date', 'full_icon_src', 'available_time_icon_src']
        for key in required_keys:
            if not settings.get(key):
                raise ValueError(f"MONITORセクションの {key} が設定されていません。")

        if settings['notification_method'] == 'discord' and not settings.get('webhook_url'):
            raise ValueError("DISCORDセクションの WebhookURL が設定されていません。")
            
        return settings
    except Exception as e:
        print(f"エラー: 設定ファイル '{config_file}' の読み込みに失敗しました: {e}")
        sys.exit(1)