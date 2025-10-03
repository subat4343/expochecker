# gmail_reader.py
import imaplib
import email
from email.header import decode_header
import re
import time

def fetch_otp_from_gmail(username, app_password):
    """Gmailに接続し、最新のワンタイムパスワードを取得する。"""
    
    IMAP_SERVER = "imap.gmail.com"
    FROM_EMAIL = "no-reply@accounts.expo2025.or.jp"

    for i in range(10):
        try:
            print(f"Gmailに接続中... ({i+1}/5)")
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            mail.login(username, app_password)
            mail.select("inbox")

            search_criteria = f'(FROM "{FROM_EMAIL}" UNSEEN)'
            status, messages = mail.search(None, search_criteria)
                    
            if status != "OK" or not messages[0]:
                print(" -> 新しい認証コードメールが見つかりません。10秒後に再試行します。")
                mail.logout()
                time.sleep(10)
                continue

            latest_id = messages[0].split()[-1]
            status, msg_data = mail.fetch(latest_id, "(RFC822)")
            
            if status == "OK":
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        # ★★★★★【最重要】変数を「空」の状態で初期化します ★★★★★
                        body = None 
                        
                        # メールの本文を取得
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    charset = part.get_content_charset()
                                    try:
                                        body = part.get_payload(decode=True).decode(charset or 'utf-8', 'ignore')
                                        break
                                    except:
                                        continue
                        else:
                            # ★★★ シングルパートメールの処理を復活させます ★★★
                            charset = msg.get_content_charset()
                            body = msg.get_payload(decode=True).decode(charset or 'utf-8', 'ignore')

                        print(body)
                        # ★★★★★【最重要】本文が取得できた場合のみ、中身を検索します ★★★★★
                        if body:
                            # 正規表現で6桁の数字を抽出
                            match = re.search(r'ワンタイムパスワード\s*[:：]\s*(\d{6})', body)
                            print(match)
                            if match:
                                otp = match.group(1)
                                print(f" -> 認証コード [{otp}] を取得しました。")
                                mail.logout()
                                return otp
            mail.logout()

        except imaplib.IMAP4.error as e:
            if "AUTHENTICATIONFAILED" in str(e):
                raise Exception("Gmailのログインに失敗しました。IDまたはアプリパスワードが間違っている可能性があります。")
            else:
                print(f"Gmail接続中にエラーが発生: {e}")
        except Exception as e:
            print(f"予期せぬエラーが発生: {e}")
        
        time.sleep(10)

    raise Exception("Gmailから認証コードを取得できませんでした。")