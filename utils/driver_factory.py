from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

def get_chrome_driver(headless=False):
    """Sets up Chrome WebDriver with proctoring bypass."""
    opts = Options()
    if headless: opts.add_argument("--headless")
    for a in ["--start-maximized", "--disable-notifications", "--disable-infobars", "--no-sandbox", "--disable-dev-shm-usage"]:
        opts.add_argument(a)

    try: driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    except: driver = webdriver.Chrome(options=opts)
    
    driver.set_window_size(1920, 1080)
    driver.maximize_window()

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
    try: driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': bypass_js})
    except: pass
    
    return driver
