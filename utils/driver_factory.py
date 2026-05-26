from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# Initialize the Chrome WebDriver instance with anti-proctoring configurations.
def get_chrome_driver(headless=False):
    opts = Options()
    if headless: opts.add_argument("--headless")
    # Configure command-line options to maximize performance and suppress UI dialogs.
    for arg in ["--start-maximized", "--disable-notifications", "--disable-infobars", "--no-sandbox", "--disable-dev-shm-usage", "--remote-debugging-port=9222"]:
        opts.add_argument(arg)

    # Attempt to initialize Chrome WebDriver via DriverManager, with a local system fallback.
    try: driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    except: driver = webdriver.Chrome(options=opts)
    
    driver.set_window_size(1920, 1080)
    driver.maximize_window()

    # JavaScript payload to override event listeners and document properties to prevent focus/visibility detection.
    bypass_js = """
    window.close=()=>{}; const def=Object.defineProperty;
    ['fullscreenElement','webkitFullscreenElement','mozFullScreenElement','msFullscreenElement'].forEach(p=>def(document,p,{get:()=>document.documentElement,configurable:true}));
    ['fullscreenEnabled','webkitFullscreenEnabled'].forEach(p=>def(document,p,{get:()=>true,configurable:true}));
    ['visibilityState','webkitVisibilityState'].forEach(p=>def(document,p,{get:()=>'visible',configurable:true}));
    ['hidden','webkitHidden'].forEach(p=>def(document,p,{get:()=>false,configurable:true}));
    const block=['blur','visibilitychange','focusout','mouseleave','copy','cut','paste','contextmenu'];
    const oA=window.addEventListener, odA=document.addEventListener;
    window.addEventListener=function(t,l,o){if(!block.includes(t))return oA.apply(this,arguments)};
    document.addEventListener=function(t,l,o){if(!block.includes(t))return odA.apply(this,arguments)};
    window.onblur=document.onblur=window.onfocus=document.onfocus=window.oncopy=document.oncut=window.onpaste=document.oncontextmenu=null;
    """
    # Register the bypass script to execute upon the creation of every new document.
    try: driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': bypass_js})
    except: pass
    
    return driver
