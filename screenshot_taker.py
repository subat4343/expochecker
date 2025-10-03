# screenshot_taker.py
import time

def take_full_page_screenshot(driver, save_path):
    """
    ブラウザのページ全体を撮影し、指定されたパスに保存する。

    :param driver: SeleniumのWebDriverインスタンス
    :param save_path: 画像を保存するファイルパス
    :return: (成功:True/失敗:False, 成功時は保存パス/失敗時はエラーメッセージ) のタプル
    """
    print("ページ全体のスクリーンショット処理を開始します...")
    original_size = None
    try:
        # 元のウィンドウサイズを取得
        original_size = driver.get_window_size()
        
        # JavaScriptでページ全体の高さを取得
        required_height = driver.execute_script('return document.body.parentNode.scrollHeight')
        
        # ウィンドウの高さをページ全体が入るようにリサイズ
        driver.set_window_size(original_size['width'], required_height)
        time.sleep(1)  # リサイズ後の描画を待つ

        # スクリーンショットを撮影
        driver.save_screenshot(save_path)
        
        return True, save_path

    except Exception as e:
        return False, str(e)

    finally:
        # 撮影後、ウィンドウサイズを必ず元に戻す
        if original_size:
            driver.set_window_size(original_size['width'], original_size['height'])
            print("ウィンドウサイズを元に戻しました。")