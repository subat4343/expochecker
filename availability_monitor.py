# availability_monitor.py (リーダブルコード適用版)
import time
import traceback
from datetime import datetime
import re
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException, NoSuchWindowException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config_loader import load_config
from driver_setup import setup_driver
from notifier import send_notification
from message_formatter import create_success_message
from screenshot_taker import take_full_page_screenshot
from gmail_reader import fetch_otp_from_gmail

# --- 定数定義 (マジックナンバー/マジックストリングの排除) ---
# 役割が明確な名前を付ける
TARGET_APPLY_TIMES = ["9:00-", "10:00-","11:00-","12:00-"]
MAX_APPLY_ATTEMPTS = 3
REFRESH_MODE= 0
TICKET_MODE= 0

# XPathセレクタを定数化
MONTH_DISPLAY_CLASS = "style_year_month__iqQQH"
NEXT_MONTH_BUTTON_XPATH = "//button[.//img[@alt='1か月先に進む']]"
DATE_ELEMENT_XPATH_TPL = "//time[@datetime='{}']/ancestor::div[contains(@class, 'style_selector_item')]"
TIMETABLE_CLASS = "style_main__timetable___J5AG"
CLICKABLE_TIME_CONTAINER_XPATH = "//div[contains(@class, 'style_main__button') and not(@data-disabled='true')]"
APPLY_BUTTON_XPATH = "//button[.//span[@data-message-code='SW_GP_DL_101_0118']]"
FAILURE_MODAL_XPATH = "//h2[@id='reservation_fail_modal_title']"
MODAL_CLOSE_BUTTON_XPATH = "//a[contains(@class, 'modal-close')]"

# --- ログインフロー用の定数 ---
LOGIN_START_URL = "https://www.expo2025.or.jp/tickets-index/"
LOGIN_BUTTON_ON_TOP_XPATH = "//a[@id='top_header_ticket_icon_ver2']"
USER_ID_INPUT_ID = "username"
PASSWORD_INPUT_ID = "password"
LOGIN_SUBMIT_BUTTON_ID = "kc-login"
OTP_INPUT_ID = "otp"
OTP_SUBMIT_BUTTON_ID = "kc-login"
RESERVE_BUTTON_ON_MYPAGE_XPATH = "//button[.//span[@data-message-code='SW_GP_DL_018_0302']]"
ADD_OTHER_TICKET_BUTTON_XPATH = "//a[.//span[@data-message-code='SW_GP_DL_108_0042']]"
SINGLE_TICKET_CHECKBOX_XPATH_TPL = "//dd[text()='{}']/ancestor::li//input[@type='checkbox']"
TICKET_ID_INPUT_ID = "agent_ticket_id_register"
ADD_TICKET_ID_BUTTON_XPATH = "//button[./span[text()='追加']]"
ADD_TO_SELECTION_BUTTON_XPATH =  "//button[.//span[@data-message-code='SW_GP_DL_167_0401']]"
SELECT_ALL_CHECKBOX_XPATH = "//label[contains(@class, 'select-all')]/input[@type='checkbox']"
PROCEED_WITH_SELECTION_BUTTON_XPATH = "//a[contains(@class, 'style_ticket_selection__submit')]"


# --- 関数分割 (巨大な関数を小さくする) ---

class WaitingRoomHandler:
    """
    仮想待合室（Queue-it）の検出と待機を管理するクラス。
    """
    # --- クラス変数として定数を定義 ---
    WAITING_ROOM_TITLE = "Queue-it"
    PAGE_LOAD_BUFFER_SECONDS = 3

    def __init__(self, driver):
        """
        コンストラクタ。操作対象のWebDriverインスタンスを受け取る。
        :param driver: Selenium WebDriverのインスタンス
        """
        if not driver:
            raise ValueError("WebDriverインスタンスが必要です。")
        self.driver = driver

    def _is_in_waiting_room(self):
        """
        現在のページが仮想待合室かどうかを判定する。（プライベートメソッド）
        """
        try:
            return self.WAITING_ROOM_TITLE in self.driver.title
        except WebDriverException:
            # ウィンドウが閉じられているなどの例外時は待合室ではないと判断
            return False

    def _wait_for_turn(self, check_interval_seconds):
        """
        仮想待合室を通過するまでループ処理で待機する。（プライベートメソッド）
        """
        print(f"\n--- 仮想待合室を検出しました。通過まで{check_interval_seconds}秒ごとに確認します ---")
        
        while self._is_in_waiting_room():
            current_time = datetime.now().strftime('%H:%M:%S')
            # メッセージを同じ行に上書き表示し、コンソールが流れるのを防ぐ
            print(f"({current_time}) 待機中... ", end="\r")
            time.sleep(check_interval_seconds)
        
        print("\n--- 仮想待合室を通過しました。処理を再開します ---")
        time.sleep(self.PAGE_LOAD_BUFFER_SECONDS)

    def handle(self, check_interval_seconds=30):
        """
        仮想待合室を処理するメインの公開メソッド。
        必要に応じて待機処理を呼び出す。
        """
        time.sleep(2)  # ページ遷移直後の一時的な状態を避けるため、少し待機
        # ガード節：待合室でなければ、何もせずすぐに関数を終了
        if not self._is_in_waiting_room():
            return

        try:
            self._wait_for_turn(check_interval_seconds)
        except NoSuchWindowException:
            print("\nエラー: 待機中にブラウザウィンドウが閉じられました。")
            # スクリプト全体を正常に停止させるため、例外を再度送出
            raise
        except Exception as e:
            print(f"\nエラー: 待合室の処理中に予期せぬエラーが発生しました: {e}")
            pass

def get_displayed_month(driver):
    """ブラウザに表示されている年月をdatetimeオブジェクトとして取得する。"""
    try:
        month_element = driver.find_element(By.CLASS_NAME, MONTH_DISPLAY_CLASS)
        match = re.search(r'(\d{4})年(\d{1,2})月', month_element.text)
        if match:
            year, month = map(int, match.groups())
            return datetime(year, month, 1)
    except (NoSuchElementException, AttributeError):
        return None
    return None

def sync_to_target_month(driver, target_date_str):
    """ブラウザの表示をターゲットの月に同期させる。"""
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    target_month = target_date.replace(day=1)

    # 無限ループを避けるための安全装置
    for _ in range(12): 
        displayed_month = get_displayed_month(driver)
        if not displayed_month:
            print("WARN: 表示されている月を特定できません。1秒待機します。")
            time.sleep(1)
            continue

        if displayed_month == target_month:
            return True # 目的の月に到達

        if displayed_month > target_month:
            print(f" -> 目的の月({target_month.strftime('%Y-%m')})を通り過ぎました。リフレッシュしてやり直します。")
            driver.refresh()
            time.sleep(2)
            # 再帰呼び出しで最初からやり直す
            return sync_to_target_month(driver, target_date_str)

        if displayed_month < target_month:
            try:
                next_month_button = driver.find_element(By.XPATH, NEXT_MONTH_BUTTON_XPATH)
                driver.execute_script("arguments[0].click();", next_month_button)
                print(f" -> {target_month.strftime('%Y-%m')}に移動中 ({displayed_month.strftime('%Y-%m')})")
                time.sleep(1)
            except NoSuchElementException:
                print("ERROR: 「次の月へ」ボタンが見つかりません。")
                return False
    
    print("ERROR: 12回試行しても目的の月に到達できませんでした。")
    return False

def attempt_application(driver, wait, config, target_time):
    """指定された時間帯の応募処理を最大3回試行する。"""
    for attempt in range(MAX_APPLY_ATTEMPTS):
        print(f" -> 応募を試行します... ({attempt + 1}/{MAX_APPLY_ATTEMPTS})")
        try:
            apply_button = wait.until(EC.presence_of_element_located((By.XPATH, APPLY_BUTTON_XPATH)))
            driver.execute_script("arguments[0].click();", apply_button)
            
            # 失敗ポップアップが出現するかを短時間待つ
            failure_wait = WebDriverWait(driver, 4)
            failure_wait.until(EC.presence_of_element_located((By.XPATH, FAILURE_MODAL_XPATH)))
            
            # 失敗した場合
            print(" -> 応募失敗（満員）。ポップアップを閉じてリトライします。")
            close_button = driver.find_element(By.XPATH, MODAL_CLOSE_BUTTON_XPATH)
            driver.execute_script("arguments[0].click();", close_button)
            time.sleep(1) # ポップアップが閉じるのを待つ
        
        except TimeoutException:
            # 失敗ポップアップが出なかった場合、成功とみなす
            print(" -> 応募成功を確認しました！")
            current_page_url = driver.current_url
            message = create_success_message(config['notification_method'], current_page_url, config['target_date'], target_time)
            ss_success, result = take_full_page_screenshot(driver, "application_success.png")
            send_notification(config, message, result if ss_success else None)
            print("\n🎉 通知が完了しました。プログラムを終了します。")
            return True # 成功したことを呼び出し元に伝える

    print(f" -> {MAX_APPLY_ATTEMPTS}回のリトライ後も応募に成功しませんでした。")
    return False # 失敗したことを呼び出し元に伝える

def perform_login_and_setup(driver, wait, config, waiting_room_handler):
    """起動時に一度だけ実行される、ログインと事前設定の全自動フロー"""
    print("\n--- 自動ログインと事前設定を開始します ---")

    # ステップ1: メインページからマイチケットログインを押下
    print("STEP 1: ログインページへ移動します...")
    driver.get(LOGIN_START_URL)
    
    # 元のタブのウィンドウハンドルを保存
    original_window = driver.current_window_handle
    
    wait.until(EC.element_to_be_clickable((By.XPATH, LOGIN_BUTTON_ON_TOP_XPATH))).click()

    # --- ▼▼▼ 修正箇所 ▼▼▼ ---
    # 新しいタブが開くまで待機し、そのタブに切り替える
    print(" -> 新しいログインタブが開くのを待っています...")
    wait.until(EC.number_of_windows_to_be(2)) # ウィンドウ(タブ)が2つになるのを待つ

    for window_handle in driver.window_handles:
        if window_handle != original_window:
            driver.switch_to.window(window_handle)
            break
            
    print(" -> 新しいログインタブに切り替えました。")
    # --- ▲▲▲ 修正完了 ▲▲▲ ---
    waiting_room_handler.handle()
    # ステップ2: IDとパスワードを入力してログイン
    print("STEP 2: IDとパスワードを入力します...")
    wait.until(EC.presence_of_element_located((By.ID, USER_ID_INPUT_ID))).send_keys(config['expo_id'])
    driver.find_element(By.ID, PASSWORD_INPUT_ID).send_keys(config['password'])
    driver.find_element(By.ID, LOGIN_SUBMIT_BUTTON_ID).click()
    waiting_room_handler.handle()
    # ステップ3: 多要素認証 (Gmailから自動取得)
    print("STEP 3: 多要素認証を処理します...")
    wait.until(EC.presence_of_element_located((By.ID, OTP_INPUT_ID)))
    otp_code = fetch_otp_from_gmail("to.suba02tin@gmail.com", config['gmail_app_password'])
    if not otp_code:
        print("ERROR: GmailからOTPコードを取得できませんでした。プログラムを終了します。")
        return False # 失敗したことを明確に返す
    driver.find_element(By.ID, OTP_INPUT_ID).send_keys(otp_code)
    driver.find_element(By.ID, OTP_SUBMIT_BUTTON_ID).click()

    # ステップ4: マイチケット画面から来場日時予約へ
    print("STEP 4: マイチケット画面から来場日時予約へ進みます...")
    reserve_button = wait.until(EC.element_to_be_clickable((By.XPATH, RESERVE_BUTTON_ON_MYPAGE_XPATH)))
    driver.execute_script("arguments[0].click();", reserve_button)
    waiting_room_handler.handle()

    if config['ticket_mode'] != 0:
        if config['ticket_mode'] == 1:
            # ステップ5: チケット選択画面で「他のチケットもまとめて」を押下
            print("STEP 5: 「他の方がお持ちのチケットもまとめて申し込む」をクリックします...")
            add_other_ticket_button = wait.until(EC.element_to_be_clickable((By.XPATH, ADD_OTHER_TICKET_BUTTON_XPATH)))
            driver.execute_script("arguments[0].click();", add_other_ticket_button)

            # ステップ6: チケットIDを入力
            print("STEP 6: チケットIDを入力します...")
            ticket_id_input = wait.until(EC.presence_of_element_located((By.ID, TICKET_ID_INPUT_ID)))
            ticket_id_input.send_keys(config['ticket_id'])
            add_button = driver.find_element(By.XPATH, ADD_TICKET_ID_BUTTON_XPATH)
            driver.execute_script("arguments[0].click();", add_button)

            # ステップ7: 「チケット選択画面に追加する」を押下
            print("STEP 7: 「チケット選択画面に追加する」をクリックします...")
            add_to_selection_button = wait.until(EC.element_to_be_clickable((By.XPATH, ADD_TO_SELECTION_BUTTON_XPATH)))
            driver.execute_script("arguments[0].click();", add_to_selection_button)
            
        # ステップ8: 「すべて選択」のチェックボックスをON
        print("STEP 8: 「すべて選択」にチェックを入れます...")
        select_all_checkbox = wait.until(EC.presence_of_element_located((By.XPATH, SELECT_ALL_CHECKBOX_XPATH)))
        driver.execute_script("arguments[0].click();", select_all_checkbox)
        waiting_room_handler.handle()
    else:
        # 指定されたチケット名のチェックボックスをONにする
        # テンプレートにチケットIDを埋め込んで、クリック対象のXPATHを生成
        print("STEP 8: 「チケット」にチェックを入れます...")
        checkbox_xpath = SINGLE_TICKET_CHECKBOX_XPATH_TPL.format(config['ticket_id'])
        select_all_checkbox = wait.until(EC.presence_of_element_located((By.XPATH, checkbox_xpath)))
        driver.execute_script("arguments[0].click();", select_all_checkbox)
        waiting_room_handler.handle()  

    # ステップ9: 「選択したチケットで申し込む」を押下
    print("STEP 9: 「選択したチケットで申し込む」をクリックします...")
    proceed_button = wait.until(EC.element_to_be_clickable((By.XPATH, PROCEED_WITH_SELECTION_BUTTON_XPATH)))
    driver.execute_script("arguments[0].click();", proceed_button)
    waiting_room_handler.handle()
    # ステップ10: チケット応募画面(#7)に遷移したことを確認
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "style_main__calendar__HRSsz")))
    print("--- 事前設定が完了しました。監視ループを開始します。 ---")
    return True

def scan_and_apply_time_slots(driver, wait, config):
    """時間帯ページをスキャンし、対象の時間があれば応募処理を呼び出す。"""
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, TIMETABLE_CLASS)))
    time.sleep(1)

    clickable_time_containers = driver.find_elements(By.XPATH, CLICKABLE_TIME_CONTAINER_XPATH)
    
    for container in clickable_time_containers:
        try:
            time_text = container.find_element(By.XPATH, ".//dt/span").text
            if time_text in TARGET_APPLY_TIMES:
                print(f" -> 応募対象の時間帯 ({time_text}) を発見。応募処理を開始します。")
                driver.execute_script("arguments[0].click();", container)
                time.sleep(0.5)

                # 応募処理を呼び出し、成功したらTrueが返る
                if attempt_application(driver, wait, config, time_text):
                    return True # 応募成功
                else:
                    # リトライに全て失敗した場合、この時間帯は諦めて次の時間帯を探す
                    break

        except Exception as e:
            print(f"WARN: 時間帯の処理中にエラーが発生しました: {e}")
            pass
    
    print(" -> 有効な応募に至らなかったため、ページを更新して監視を続けます。")
    return False # 応募に至らなかった


def start_monitoring_loop(driver, wait, config, waiting_room_handler,monitoring_start_url):
    """
    ログインと事前設定が完了した後の、メインの監視・応募ループ。
    """
    # この関数が呼び出された時点で、すでに目的のページにいる想定
    # 初回のリフレッシュと月同期は不要なため、すぐにループを開始
    
    initial_sync_done = False
    while True:
        try:                # ページの鮮度を保つため、ループの最初にリフレッシュする
            if config['refresh_mode'] == 0:
                print(f"\nURLに再アクセスしてページを更新します ({datetime.now().strftime('%H:%M:%S')})...")
                driver.get(monitoring_start_url)
            else: # デフォルトまたは'refresh'が指定されている場合
                print(f"\nページをリフレッシュします ({datetime.now().strftime('%H:%M:%S')})...")
                driver.refresh()
            time.sleep(2)

            # ステップ1: 正しい月に移動する
            if not sync_to_target_month(driver, config['target_date']):
                raise Exception("目的の月への移動に失敗しました。")
            print(f" -> {config['target_date']}の月に到達しました。空き状況をチェックします。")

            # ステップ2: 目的の日付を探す
            date_element_xpath = DATE_ELEMENT_XPATH_TPL.format(config['target_date'])
            date_element = wait.until(EC.presence_of_element_located((By.XPATH, date_element_xpath)))

            # ステップ3: 目的の日付が予約可能かチェック
            is_full = len(date_element.find_elements(By.XPATH, f".//img[contains(@src, '{config['full_icon_src']}')]")) > 0
            is_disabled = "style_selector_item_disabled" in date_element.get_attribute("class")
            
            if not is_full and not is_disabled:
                print(f"✅ {config['target_date']}が予約可能な状態です。クリックして時間帯をスキャンします...")
                driver.execute_script("arguments[0].click();", date_element)

                # ステップ4: 時間帯をスキャンし、応募を試みる
                if scan_and_apply_time_slots(driver, wait, config):
                    break # 応募に成功したらメインループを終了
            else:
                print(f"{datetime.now().strftime('%H:%M:%S')}: 指定日に空きはありません。")
        except TimeoutException:
            print(f"{datetime.now().strftime('%H:%M:%S')}: 指定日が見つかりません。")
        except (WebDriverException, NoSuchWindowException) as e:
            print(f"\nエラー: ブラウザとの接続が失われました。({e.__class__.__name__})")
            break
        except KeyboardInterrupt:
            print("\nユーザーによって監視が中断されました。")
            break
        except Exception as e:
            print(f"\nループ中に予期せぬエラーが発生しました: {e}")
            traceback.print_exc()
        
        print(f"{config['interval']}秒後に再試行します。")
        time.sleep(config['interval'])
def main():
    """メインの実行関数。全体の流れを制御する。"""
    print("--- イベント自動応募プログラム (自動ログイン対応版) ---")
    config = load_config()
    driver = None

    try:
        # Selenium WebDriverを起動
        # アタッチではなく、常に新しいブラウザで開始する
        driver = setup_driver(headless=False) # 動作確認のため、ヘッドレスはFalseを推奨
        wait = WebDriverWait(driver, 20) # ページ遷移が多いため長めに待つ

        waiting_room_handler = WaitingRoomHandler(driver)
        # ステップ1: 自動ログインと事前設定の実行
        login_success = perform_login_and_setup(driver, wait, config,waiting_room_handler)

        if login_success:
            monitoring_start_url = driver.current_url
            # ステップ2: 既存の監視ループを開始
            start_monitoring_loop(driver, wait, config,waiting_room_handler,monitoring_start_url)
        else:
            raise Exception("自動ログイン・事前設定プロセスに失敗しました。")
    except KeyboardInterrupt:
        print("\nプログラムを終了します。")
    except Exception as e:
        print(f"\nプログラム全体で予期せぬエラーが発生しました: {e}")
        traceback.print_exc()
    finally:
        if driver:
            driver.quit()
        print("--- プログラム終了 ---")

if __name__ == '__main__':
    main()