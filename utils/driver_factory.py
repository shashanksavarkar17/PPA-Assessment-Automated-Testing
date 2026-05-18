from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

def get_chrome_driver(headless=False):
    """
    Sets up and returns a Chrome WebDriver instance using webdriver-manager.
    """
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-infobars")
    
    # Resolves issue with some environments
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    # Automatically install and setup ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Explicitly set window size to avoid "Mobile View Not Supported" overlay
    driver.set_window_size(1920, 1080)
    driver.maximize_window()

    # Inject CDP-based proctoring bypass script at document start level
    bypass_script = """
        Object.defineProperty(document, 'visibilityState', {get: () => 'visible', configurable: true});
        Object.defineProperty(document, 'hidden', {get: () => false, configurable: true});
        
        const originalAddEventListener = window.addEventListener;
        window.addEventListener = function(type, listener, options) {
            if (['blur', 'visibilitychange', 'focusout', 'mouseleave', 'copy', 'cut', 'paste', 'contextmenu'].includes(type)) {
                return;
            }
            return originalAddEventListener.apply(this, arguments);
        };
        
        const originalDocAddEventListener = document.addEventListener;
        document.addEventListener = function(type, listener, options) {
            if (['blur', 'visibilitychange', 'focusout', 'mouseleave', 'copy', 'cut', 'paste', 'contextmenu'].includes(type)) {
                return;
            }
            return originalDocAddEventListener.apply(this, arguments);
        };
        
        window.onblur = null;
        document.onblur = null;
        window.onfocus = null;
        document.onfocus = null;
        window.oncopy = null;
        document.oncut = null;
        window.onpaste = null;
        document.oncontextmenu = null;
    """
    try:
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': bypass_script})
    except Exception:
        pass
    
    return driver
