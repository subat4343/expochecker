# driver_setup.py (修正版)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver(headless=True, debugger_address=None):
    """
    Selenium WebDriverをセットアップする共通関数
    :param headless: Trueならブラウザ非表示、Falseなら表示 (debugger_address指定時は無視)
    :param debugger_address: (例: "127.0.0.1:9222") 指定した場合、既存のブラウザに接続
    """
    options = Options()
    
    if debugger_address:
        # ★★★ 変更点(1/2) ★★★
        # 既存ブラウザへの接続時は、接続に必要なオプションのみを指定する
        print(f"既存のブラウザ ({debugger_address}) へのアタッチを試みます...")
        options.add_experimental_option("debuggerAddress", debugger_address)
    else:
        # ★★★ 変更点(2/2) ★★★
        # 新しいブラウザを起動する場合にのみ、自動化を隠すオプションなどを設定する
        if headless:
            options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        options.add_argument('--dns-prefetch-disable')
        options.add_argument('--disable-infobars')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # 新規起動時のみbot検知対策スクリプトを実行
    if not debugger_address:
        driver.execute_cdp_cmd(
            'Page.addScriptToEvaluateOnNewDocument',
            {'source': '''Object.defineProperty(navigator, 'webdriver', {get: () => undefined});'''}
        )

    return driver