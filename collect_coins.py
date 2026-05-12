import time
import random
import os
import sys
import asyncio
import json
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys

# Import Telegram if configured
try:
    from telegram import Bot
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


# === FORCE UTF-8 OUTPUT ===
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Load environment variables from .env file
load_dotenv()

# Get credentials from environment variables
ALIEXPRESS_EMAIL = os.getenv("ALIEXPRESS_EMAIL")
ALIEXPRESS_PASSWORD = os.getenv("ALIEXPRESS_PASSWORD")
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
USER_DATA_DIR = os.getenv("USER_DATA_DIR")  # Default to None for local dev

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
USE_TELEGRAM = TELEGRAM_AVAILABLE and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID

COOKIE_FILE = os.getenv("COOKIE_FILE", "cookies/cookies.json")

# === CONFIGURATION PARAMETERS ===
CONFIG = {
    "URLS": {
        "HOME": "https://www.aliexpress.com/",
        "LOGIN_REDIRECT": "https://s.click.aliexpress.com/e/_DB2kEjh",
        "COIN_MOBILE": "https://s.click.aliexpress.com/e/_DB2kEjh",
        "COIN_DESKTOP": "https://www.aliexpress.com/p/coin-pc-index/index.html"
    },
    "SELECTORS": {
        "SHIP_TO": [
            "//div[contains(@class, 'ship-to--menuItem')]",
            "//div[contains(@class, 'ship-to--text')]",
            "//div[contains(@class, 'es--wrap')]/div/div[contains(@class, 'ship-to--menuItem')]"
        ],
        "FORM_TITLE": "//div[contains(@class, 'form-item--title')]",
        "SELECT_ITEM_CONTAINER": "//div[contains(@class, 'select--itemContainer')]",
        "SELECT_LABEL": "//div[contains(@class, 'select--label')]",
        "SELECT_TEXT": "//div[contains(@class, 'select--text')]",
        "SELECT_SEARCH_CONTAINER": "//*[contains(@class, 'select--search')]",
        "SELECT_ITEM": "//div[contains(@class, 'select--item')]",
        "SAVE_BTN": "//*[contains(@class, 'saveBtn')]",
        "COLLECT_BTN": [
            "//*[contains(@class, 'checkin-start')]//*[contains(@class, 'checkin-footer')]//*[contains(@class, 'checkin-button')]",
            "//*[@id='signButton' or contains(@class, 'checkin-button')]",
            "//div[contains(@class, 'button') and (contains(., 'Collect') or contains(., '출석') or contains(., '적립'))]",
            "//button[contains(@class, 'check-in') or contains(@class, 'checkin')]"
        ],
        "LOGIN": {
            "EMAIL": "input[placeholder*='Email'], input[label*='Email'], input[label*='이메일'], #fm-login-id, input[name='loginId'], .cosmos-input[type='text']",
            "CONTINUE_BTN": "//button[contains(@class, 'cosmos-btn-primary') and (contains(., 'Continue') or contains(., '계속'))]",
            "PASSWORD_CSS": "#fm-login-password, input[type='password']",
            "SIGN_IN_BTN": "//button[contains(@class, 'cosmos-btn-primary') and (contains(., 'Sign in') or contains(., '로그인'))]",
            "VERIFY_BTN": "//button[contains(., 'Verify') or contains(., 'Submit') or contains(., '확인') or contains(., 'OK')]",
            "CODE_INPUTS": [
                "input[placeholder*='code']", 
                "input[id*='checkcode']", 
                ".next-input.next-large input", 
                "input[name='checkCode']"
            ]
        },
        "ACCOUNT_INDICATORS": {
            "SIGNED_IN": ".account-signed, .user-account-port, .nav-user-account",
            "SIGNED_OUT": ".account-unsigned"
        },
        "MODAL_CLOSE": [
            ".image-poplayer-close",
            ".next-dialog-close",
            ".poplayer-close",
            "img.pop-close-btn",
            ".btn-close",
            ".close-button"
        ],
        "MODAL_OVERLAYS": ".image-poplayer-modal, .next-overlay-backdrop"
    },
    "KEYWORDS": {
        "ALREADY_COLLECTED": [
            'already', 'checked', 'collected', '받기 완료', '완료', '이미', 
            'guadagna più monete', 'get more coins', '코인 더 받기',
            'come back tomorrow to receive more coins', 'earn more coins'
        ],
        "LOGIN_INDICATORS": [
            "sign out", "logout", "로그아웃", "my orders", "my coupons", "내 주문", "내 쿠폰"
        ],
        "LOGOUT_INDICATORS": [
            "sign in", "register", "로그인", "가입"
        ],
        "2FA": ["verification code", "verify your identity", "enter code", "sent to your email", "인증 번호", "security verification"],
        "UI_TEXT": {
            "LANGUAGE_LABELS": ["language", "lingua", "언어", "idioma"],
            "COUNTRY_LABELS": ["ship to", "country", "paese", "배송지", "국가", "enviar a", "spedire a"],
            "ENGLISH_VARIANTS": ["english", "inglese"],
            "KOREA_INDICATORS": ['korea', '한국', '대한민국', ' south korea', 'republic of korea', 'ko/', 'kr/']
        }
    },
    "USER_AGENTS": {
        "DESKTOP": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "MOBILE": "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"
    }
}

# Check if credentials are available
if not ALIEXPRESS_EMAIL or not ALIEXPRESS_PASSWORD:
    print("Error: Environment variables for ALIEXPRESS_EMAIL and ALIEXPRESS_PASSWORD must be set.")
    print("Please create a .env file with these variables or set them in your environment.")
    exit(1)

def random_sleep(min_seconds=1, max_seconds=3):
    """Sleep for a random amount of time to mimic human behavior"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def move_mouse_randomly(driver, element):
    """Move mouse with human-like randomness before clicking - safer version"""
    try:
        actions = ActionChains(driver)
        actions.move_to_element(element)
        actions.perform()
        random_sleep(0.3, 0.7)
    except Exception as e:
        print(f"Warning: Simple mouse movement failed: {e}. Trying direct click.")

def type_like_human(element, text):
    """Type text with human-like timing and occasional mistakes that get corrected"""
    for char in text:
        if random.random() < 0.01:
            typo_char = random.choice('qwertyuiopasdfghjklzxcvbnm')
            element.send_keys(typo_char)
            random_sleep(0.1, 0.3)
            element.send_keys(Keys.BACKSPACE)
            random_sleep(0.2, 0.5)
        
        element.send_keys(char)
        random_sleep(0.05, 0.15)
        if random.random() < 0.05:
            random_sleep(0.5, 1.2)

def save_cookies(driver, path=COOKIE_FILE):
    """Save cookies from the current session to a JSON file"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        cookies = driver.get_cookies()
        with open(path, 'w') as f:
            json.dump(cookies, f)
        print(f"Cookies saved to {path}")
        return True
    except Exception as e:
        print(f"Failed to save cookies: {e}")
        return False

def load_cookies(driver, path=COOKIE_FILE):
    """Load cookies from a JSON file into the current session"""
    try:
        if not os.path.exists(path):
            print(f"No cookie file found at {path}")
            return 0
            
        with open(path, 'r') as f:
            cookies = json.load(f)
            
        print(f"Applying {len(cookies)} cookies from {path}...")
        
        # Ensure we are on the domain before adding cookies
        if "aliexpress" not in driver.current_url:
            driver.get(CONFIG["URLS"]["HOME"])
            random_sleep(2, 3)
        
        count = 0
        for cookie in cookies:
            try:
                # Remove sameSite if it's not one of the allowed values
                if 'sameSite' in cookie and cookie['sameSite'] not in ["Strict", "Lax", "None"]:
                    del cookie['sameSite']
                    
                if 'expiry' in cookie:
                    cookie['expiry'] = int(cookie['expiry'])
                
                driver.add_cookie(cookie)
                count += 1
            except Exception as e:
                # Log the error to help diagnose why it's failing
                cookie_name = cookie.get('name', 'unknown')
                cookie_domain = cookie.get('domain', 'unknown')
                print(f"DEBUG: Failed to add cookie '{cookie_name}' (domain: {cookie_domain}): {e}")
                continue
                
        print(f"Successfully loaded {count}/{len(cookies)} cookies.")
        if count > 0:
            driver.refresh()
            random_sleep(3, 5)
        return count
    except Exception as e:
        print(f"Failed to load cookies: {e}")
        return 0

async def send_telegram_screenshot(driver, caption=""):
    """Take a screenshot and send it via Telegram for debugging"""
    if not USE_TELEGRAM:
        return False
        
    try:
        screenshot_path = "debug_screenshot.png"
        driver.save_screenshot(screenshot_path)
        
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        with open(screenshot_path, 'rb') as photo:
            await bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=photo, caption=caption)
        
        os.remove(screenshot_path)
        return True
    except Exception as e:
        print(f"Failed to send screenshot to Telegram: {e}")
        return False

async def get_2fa_from_telegram():
    """Wait for a 2FA code to be sent via Telegram"""
    if not USE_TELEGRAM:
        return None
        
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        message = "🚨 *AliExpress 2FA Required*\n\nPlease check your email and send the verification code here."
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
        print(f"Sent 2FA request to Telegram chat {TELEGRAM_CHAT_ID}")
        
        last_update_id = -1
        updates = await bot.get_updates(offset=-1, timeout=10)
        if updates:
            last_update_id = updates[0].update_id
            
        print("Waiting for Telegram response...")
        start_time = time.time()
        timeout = 300
        
        while time.time() - start_time < timeout:
            updates = await bot.get_updates(offset=last_update_id + 1, timeout=30)
            for update in updates:
                if update.message and str(update.message.chat_id) == str(TELEGRAM_CHAT_ID) and update.message.text:
                    code = update.message.text.strip()
                    if code.isdigit() and (len(code) == 6 or len(code) == 4):
                        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"✅ Received code: {code}. Continuing login...")
                        return code
                    else:
                        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"⚠️ Received '{code}', but it doesn't look like a 6-digit or 4-digit code. Please try again.")
                last_update_id = update.update_id
            await asyncio.sleep(2)
            
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="❌ Timeout: No valid 2FA code received within 5 minutes.")
        return None
    except Exception as e:
        print(f"Error interacting with Telegram: {e}")
        return None

def is_session_active(driver):
    """Check if the current session is logged in using multiple indicators"""
    try:
        # 1. Check for specific session cookies first - most reliable
        cookies = driver.get_cookies()
        if any(c.get('name') in ['alf', 'ali_apache_id', 'xman_t'] for c in cookies):
            return True

        page_source = driver.page_source.lower()
        
        # 2. Check for positive UI indicators (sign out, etc)
        if any(indicator in page_source for indicator in CONFIG["KEYWORDS"]["LOGIN_INDICATORS"]):
            return True
        
        # 3. Check for specific CSS indicators for signed in
        try:
            driver.find_element(By.CSS_SELECTOR, CONFIG["SELECTORS"]["ACCOUNT_INDICATORS"]["SIGNED_IN"])
            return True
        except Exception:
            pass
            
        # 4. Check for negative indicators ONLY if no positive indicators were found
        if any(indicator in page_source for indicator in CONFIG["KEYWORDS"]["LOGOUT_INDICATORS"]):
            return False
            
        try:
            driver.find_element(By.CSS_SELECTOR, CONFIG["SELECTORS"]["ACCOUNT_INDICATORS"]["SIGNED_OUT"])
            return False
        except Exception:
            pass
        
        return False
    except Exception:
        return False

def login(driver):
    """Perform the login process with human-like behavior, checking for existing session first"""
    try:
        print("Checking if already logged in...")
        
        cookies_loaded = 0
        if os.path.exists(COOKIE_FILE):
            print("Found cookies.json, attempting to load session...")
            cookies_loaded = load_cookies(driver)
        else:
            driver.get(CONFIG["URLS"]["HOME"])
            random_sleep(5, 7)
        
        if is_session_active(driver):
            print("Detected existing session (Logged in).")
            save_cookies(driver)
            return True

        print("Not logged in. Starting login process...")
        driver.get(CONFIG["URLS"]["LOGIN_REDIRECT"])
        random_sleep(3, 5)

        wait = WebDriverWait(driver, 15)
        
        try:
            email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, CONFIG["SELECTORS"]["LOGIN"]["EMAIL"])))
            print("Found email input field")
        except Exception:
            if any(ind in driver.page_source.lower() for ind in CONFIG["KEYWORDS"]["LOGIN_INDICATORS"]):
                print("Bypassed login, login indicator detected.")
                return True
            if USE_TELEGRAM:
                asyncio.run(send_telegram_screenshot(driver, "⚠️ Could not find login fields."))
            print("Error: Could not find login fields.")
            return False
        
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", email_input)
        random_sleep(1, 2)
        
        try:
            email_input.click()
        except Exception:
            driver.execute_script("arguments[0].click();", email_input)
        
        random_sleep(0.5, 1.5)
        print("Entering email address...")
        type_like_human(email_input, ALIEXPRESS_EMAIL)
        random_sleep(1, 2)
        
        continue_button = wait.until(EC.element_to_be_clickable((By.XPATH, CONFIG["SELECTORS"]["LOGIN"]["CONTINUE_BTN"])))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", continue_button)
        random_sleep(0.5, 1)
        driver.execute_script("arguments[0].click();", continue_button)
        random_sleep(2, 3)
        
        password_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, CONFIG["SELECTORS"]["LOGIN"]["PASSWORD_CSS"])))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", password_input)
        random_sleep(0.5, 1)
        driver.execute_script("arguments[0].click();", password_input)
        random_sleep(0.5, 1)
        print("Entering password...")
        type_like_human(password_input, ALIEXPRESS_PASSWORD)
        random_sleep(1, 2)
        
        sign_in_button = wait.until(EC.element_to_be_clickable((By.XPATH, CONFIG["SELECTORS"]["LOGIN"]["SIGN_IN_BTN"])))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", sign_in_button)
        random_sleep(0.5, 1)
        driver.execute_script("arguments[0].click();", sign_in_button)
        
        random_sleep(3, 5)
        
        def check_for_2fa(driver):
            source = driver.page_source.lower()
            if any(k in source for k in CONFIG["KEYWORDS"]["2FA"]):
                return True
            for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
                try:
                    driver.switch_to.frame(iframe)
                    inner_source = driver.page_source.lower()
                    driver.switch_to.default_content()
                    if any(k in inner_source for k in CONFIG["KEYWORDS"]["2FA"]):
                        return True
                except Exception:
                    driver.switch_to.default_content()
            return False

        if check_for_2fa(driver):
            print("\nACTION REQUIRED: Email Verification Detected!")
            if USE_TELEGRAM:
                asyncio.run(send_telegram_screenshot(driver, "🚨 AliExpress 2FA Detected!"))
            
            def find_code_input(driver):
                for s in CONFIG["SELECTORS"]["LOGIN"]["CODE_INPUTS"]:
                    try:
                        el = driver.find_element(By.CSS_SELECTOR, s)
                        if el.is_displayed(): return el
                    except Exception: continue
                return None

            code_input = find_code_input(driver)
            if code_input:
                verification_code = asyncio.run(get_2fa_from_telegram()) if USE_TELEGRAM else (input("Enter verification code: ").strip() if not HEADLESS else None)
                if verification_code:
                    type_like_human(code_input, verification_code)
                    random_sleep(1, 2)
                    try:
                        verify_btn = driver.find_element(By.XPATH, CONFIG["SELECTORS"]["LOGIN"]["VERIFY_BTN"])
                        verify_btn.click()
                    except Exception:
                        code_input.send_keys(Keys.ENTER)
            else:
                if not HEADLESS:
                    input("Press Enter here once you have finished the verification in the browser...")

        random_sleep(5, 7)
        if is_session_active(driver):
            print("Login successful")
            save_cookies(driver)
            return True
        else:
            if USE_TELEGRAM:
                asyncio.run(send_telegram_screenshot(driver, "❌ Login failed."))
            return False
    
    except Exception as e:
        print(f"Login failed: {e}")
        return False

def close_modals(driver):
    """Attempt to close any blocking modals or popups"""
    try:
        found_any = False
        for selector in CONFIG["SELECTORS"]["MODAL_CLOSE"]:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        driver.execute_script("arguments[0].click();", el)
                        found_any = True
                        random_sleep(0.5, 1)
            except Exception: continue
        
        try:
            driver.execute_script(f"""
                const overlays = document.querySelectorAll('{CONFIG["SELECTORS"]["MODAL_OVERLAYS"]}');
                overlays.forEach(el => el.remove());
            """)
        except Exception: pass
        return found_any
    except Exception as e:
        print(f"DEBUG: Error in close_modals: {e}")
        return False

def change_country_to_korea(driver):
    """Change the country to Korea and language to English using the ship-to dropdown"""
    try:
        wait = WebDriverWait(driver, 15)
        
        def is_ship_to_menu_open():
            """Check if the ship-to dropdown menu is currently open"""
            try:
                # If we see select items or search box, it's open
                elements = driver.find_elements(By.XPATH, CONFIG["SELECTORS"]["SELECT_ITEM"])
                return any(el.is_displayed() for el in elements)
            except:
                return False

        def close_ship_to_menu():
            """Close the ship-to menu if it's open by clicking the toggle again"""
            if is_ship_to_menu_open():
                print("DEBUG: Closing ship-to menu...")
                try:
                    for selector in CONFIG["SELECTORS"]["SHIP_TO"]:
                        dropdown = driver.find_element(By.XPATH, selector)
                        driver.execute_script("arguments[0].click();", dropdown)
                        random_sleep(1, 2)
                        if not is_ship_to_menu_open(): return True
                except: pass
            return True

        def open_ship_to_menu(retries=3):
            for i in range(retries):
                try:
                    close_modals(driver)
                    
                    if is_ship_to_menu_open():
                        print("DEBUG: Ship-to menu already open.")
                        return True

                    print(f"DEBUG: Opening ship-to dropdown (Attempt {i+1})...")
                    ship_to_dropdown = None
                    for selector in CONFIG["SELECTORS"]["SHIP_TO"]:
                        try:
                            ship_to_dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                            break
                        except Exception: continue
                        
                    if not ship_to_dropdown:
                        if i < retries - 1:
                            random_sleep(2, 3)
                            continue
                        raise Exception("Could not find ship-to dropdown")
                        
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", ship_to_dropdown)
                    random_sleep(1, 2)
                    driver.execute_script("arguments[0].click();", ship_to_dropdown)
                    random_sleep(3, 4)
                    wait.until(EC.presence_of_element_located((By.XPATH, CONFIG["SELECTORS"]["SELECT_TEXT"])))
                    return True
                except Exception as e:
                    print(f"DEBUG: open_ship_to_menu attempt {i+1} failed: {e}")
                    random_sleep(2, 3)
            return False

        def find_selector_by_label(label_keywords):
            """Find a selector div by looking for title labels in siblings or parents"""
            try:
                # 1. Look for titles then find the following content's select
                titles = driver.find_elements(By.XPATH, CONFIG["SELECTORS"]["FORM_TITLE"])
                for title_el in titles:
                    try:
                        title_text = driver.execute_script("return arguments[0].innerText;", title_el).lower()
                        if any(k in title_text for k in label_keywords):
                            # In Italian/New UI, title and content are siblings. Try first 2 siblings.
                            for i in range(1, 3):
                                try:
                                    content = title_el.find_element(By.XPATH, f"following-sibling::div[{i}]")
                                    selector = content.find_element(By.XPATH, ".//" + CONFIG["SELECTORS"]["SELECT_TEXT"].lstrip("/"))
                                    if selector: return selector
                                except: continue
                    except Exception: pass
                
                # 2. Fallback to searching all selectors and checking their text/context
                selectors = driver.find_elements(By.XPATH, CONFIG["SELECTORS"]["SELECT_TEXT"])
                for sel in selectors:
                    try:
                        # Check text of the selector itself or its parent container for keywords
                        parent_text = driver.execute_script("return arguments[0].parentElement.innerText;", sel).lower()
                        if any(k in parent_text for k in label_keywords):
                            return sel
                    except: continue
            except Exception: pass
            return None

        def save_and_reload():
            print("DEBUG: Looking for Save button...")
            save_button = None
            try:
                # Try multiple approaches for Save button
                btns = driver.find_elements(By.XPATH, CONFIG["SELECTORS"]["SAVE_BTN"])
                for btn in btns:
                    if btn.is_displayed():
                        save_button = btn
                        break
                
                if not save_button:
                    # Look for text "Salva", "Save", etc.
                    save_button = driver.execute_script("""
                        return Array.from(document.querySelectorAll('div, button, span, a'))
                            .find(el => {
                                const t = el.innerText.trim().toLowerCase();
                                return (t === 'salva' || t === 'save' || t === 'apply' || t === '확인') && el.offsetParent !== null;
                            });
                    """)
            except Exception: pass

            if not save_button:
                print("DEBUG: Could not find Save button")
                return False
                
            print("DEBUG: Clicking Save button...")
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", save_button)
            random_sleep(1.5, 2)
            driver.execute_script("arguments[0].click();", save_button)
            print("DEBUG: Clicked Save button. Waiting for page reload...")
            random_sleep(10, 15)
            try: wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
            except Exception: pass
            return True

        # STAGE 1: SET LANGUAGE TO ENGLISH
        if open_ship_to_menu():
            print("DEBUG: Identifying language selector...")
            language_selector = find_selector_by_label(CONFIG["KEYWORDS"]["UI_TEXT"]["LANGUAGE_LABELS"])
            
            if not language_selector:
                print("DEBUG: Label-based language identification failed, using index fallback (Stage 1)...")
                selectors = driver.find_elements(By.XPATH, CONFIG["SELECTORS"]["SELECT_TEXT"])
                if len(selectors) >= 4: language_selector = selectors[3]
                elif len(selectors) >= 2: language_selector = selectors[1]
            
            if language_selector:
                try:
                    current_lang = language_selector.text.lower()
                    print(f"DEBUG: Current language detected: '{current_lang}'")
                    
                    if not any(v in current_lang for v in CONFIG["KEYWORDS"]["UI_TEXT"]["ENGLISH_VARIANTS"]) and current_lang != "":
                        print("STEP 1: Changing language to English...")
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", language_selector)
                        random_sleep(1, 2)
                        driver.execute_script("arguments[0].click();", language_selector)
                        random_sleep(2, 3)
                        
                        try:
                            # Search box logic - specifically find the one belonging to this dropdown
                            print("DEBUG: Identifying search input...")
                            search_input = None
                            try:
                                # Try finding search input within the active popup/context
                                search_input = language_selector.find_element(By.XPATH, "parent::*/following-sibling::div//input")
                            except:
                                try:
                                    search_input = wait.until(EC.presence_of_element_located((By.XPATH, CONFIG["SELECTORS"]["SELECT_SEARCH_CONTAINER"] + "//input")))
                                except: pass

                            if search_input and search_input.is_displayed():
                                print("DEBUG: Using search box for language...")
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", search_input)
                                random_sleep(0.5, 1)
                                search_input.send_keys(Keys.CONTROL + "a")
                                search_input.send_keys(Keys.BACKSPACE)
                                type_like_human(search_input, "English")
                                random_sleep(2, 3)
                            
                            # Select option
                            english_option = None
                            try:
                                options = driver.find_elements(By.XPATH, CONFIG["SELECTORS"]["SELECT_ITEM"])
                                print(f"DEBUG: Found {len(options)} list items")
                                for opt in options:
                                    try:
                                        text = opt.text.strip().lower()
                                        if any(v in text for v in CONFIG["KEYWORDS"]["UI_TEXT"]["ENGLISH_VARIANTS"]):
                                            english_option = opt
                                            break
                                    except Exception: continue
                            except Exception: pass

                            if english_option:
                                option_text = driver.execute_script("return arguments[0].innerText;", english_option)
                                print(f"DEBUG: Clicking option: '{option_text}'.")
                                driver.execute_script("arguments[0].click();", english_option)
                                random_sleep(2, 3)
                                if not save_and_reload():
                                    close_ship_to_menu()
                            else:
                                print("DEBUG: Could not find English option after filtering. Aborting language change.")
                                close_ship_to_menu()
                        except Exception as ie:
                            print(f"DEBUG: Inner language selection failed: {ie}")
                            close_ship_to_menu()
                except Exception as le:
                    print(f"DEBUG: Language stage failed: {le}")
                    close_ship_to_menu()
            else:
                print("DEBUG: Language selector not found.")
                close_ship_to_menu()

        # STAGE 2: SET COUNTRY TO KOREA
        random_sleep(3, 5)
        if open_ship_to_menu():
            print("DEBUG: Identifying country selector...")
            country_selector = find_selector_by_label(CONFIG["KEYWORDS"]["UI_TEXT"]["COUNTRY_LABELS"])
            
            if not country_selector:
                print("DEBUG: Label-based country identification failed, using index fallback (Stage 2)...")
                selectors = driver.find_elements(By.XPATH, CONFIG["SELECTORS"]["SELECT_TEXT"])
                country_selector = selectors[0] if selectors else None
            
            if country_selector:
                try:
                    print(f"STEP 2: Changing country to Korea (Current: {country_selector.text})...")
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", country_selector)
                    random_sleep(1, 2)
                    driver.execute_script("arguments[0].click();", country_selector)
                    random_sleep(2, 3)
                    
                    search_container = wait.until(EC.presence_of_element_located((By.XPATH, CONFIG["SELECTORS"]["SELECT_SEARCH_CONTAINER"])))
                    search_input = search_container.find_element(By.TAG_NAME, "input")
                    driver.execute_script("arguments[0].click(); arguments[0].focus();", search_input)
                    random_sleep(0.5, 1)
                    search_input.send_keys(Keys.CONTROL + "a")
                    search_input.send_keys(Keys.BACKSPACE)
                    type_like_human(search_input, "Korea")
                    random_sleep(2, 3)
                    
                    korea_found = False
                    try:
                        # Try finding by text or by the KR flag class
                        korea_option = None
                        options = driver.find_elements(By.XPATH, CONFIG["SELECTORS"]["SELECT_ITEM"])
                        for opt in options:
                            inner_html = driver.execute_script("return arguments[0].innerHTML;", opt)
                            inner_text = driver.execute_script("return arguments[0].innerText;", opt).lower()
                            if " KR" in inner_html or any(k in inner_text for k in CONFIG["KEYWORDS"]["UI_TEXT"]["KOREA_INDICATORS"]):
                                korea_option = opt
                                break
                        
                        if korea_option:
                            driver.execute_script("arguments[0].click();", korea_option)
                            korea_found = True
                    except Exception: pass
                    
                    if not korea_found:
                        print("DEBUG: Retrying with 'South Korea'...")
                        search_input.send_keys(Keys.CONTROL + "a")
                        search_input.send_keys(Keys.BACKSPACE)
                        type_like_human(search_input, "South Korea")
                        random_sleep(2, 3)
                        # Re-check options
                        options = driver.find_elements(By.XPATH, CONFIG["SELECTORS"]["SELECT_ITEM"])
                        for opt in options:
                            inner_html = driver.execute_script("return arguments[0].innerHTML;", opt)
                            inner_text = driver.execute_script("return arguments[0].innerText;", opt).lower()
                            if " KR" in inner_html or any(k in inner_text for k in CONFIG["KEYWORDS"]["UI_TEXT"]["KOREA_INDICATORS"]):
                                korea_option = opt
                                driver.execute_script("arguments[0].click();", korea_option)
                                korea_found = True
                                break
                    
                    if korea_found:
                        random_sleep(2, 3)
                        if not save_and_reload():
                            close_ship_to_menu()
                            return False
                        return True
                    else:
                        close_ship_to_menu()
                except Exception as ce:
                    print(f"DEBUG: Country stage failed: {ce}")
                    close_ship_to_menu()
        
        return False
    except Exception as e:
        print(f"DEBUG: change_country_to_korea failed: {e}")
        return False

def verify_korea_selected(driver):
    """Verify that Korea is currently selected as the country"""
    try:
        wait = WebDriverWait(driver, 10)
        ship_to_element = None
        for selector in CONFIG["SELECTORS"]["SHIP_TO"]:
            try:
                ship_to_element = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                break
            except Exception: continue
                
        if not ship_to_element:
            return False
            
        ship_to_text = driver.execute_script("return arguments[0].innerText;", ship_to_element).lower()
        
        if any(indicator in ship_to_text for indicator in CONFIG["KEYWORDS"]["UI_TEXT"]["KOREA_INDICATORS"]):
            print("Confirmation: Korea is already selected as the country.")
            return True
        else:
            print(f"Detected location text '{ship_to_text}', which does not match Korea indicators.")
            return False
    except Exception as e:
        print(f"Error verifying Korea selection: {e}")
        return False

def find_and_click_collect_button(driver):
    """Find and click the coin collect button with multiple approaches. 
    Returns: (success, already_collected)"""
    print("STEP 7: Looking for the Collect button...")
    wait = WebDriverWait(driver, 15)
    
    # Android emulation stuck fix: check if body is filled or canvas exists
    try:
        page_content_length = driver.execute_script("return document.body ? document.body.innerText.length : 0;")
        canvas_exists = driver.execute_script("return document.getElementsByTagName('canvas').length > 0;")
        if page_content_length < 100 and not canvas_exists:
            print("DEBUG: Page seems blank/stuck, refreshing...")
            driver.refresh()
            random_sleep(10, 15)
    except Exception: pass

    for selector in CONFIG["SELECTORS"]["COLLECT_BTN"]:
        try:
            collect_button = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
            button_text = driver.execute_script("return arguments[0].innerText;", collect_button).lower()
            
            if any(k in button_text for k in CONFIG["KEYWORDS"]["ALREADY_COLLECTED"]):
                print(f"Detected button text: '{button_text.strip()}'. Coins already redeemed.")
                return True, True # Success, already collected
            
            print(f"Found Collect button (Text: '{button_text.strip()}'). Clicking...")
            driver.execute_script("arguments[0].style.border='3px solid red'", collect_button)
            random_sleep(1, 2)
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", collect_button)
            random_sleep(1, 2)
            
            try:
                move_mouse_randomly(driver, collect_button)
                collect_button.click()
            except Exception:
                driver.execute_script("arguments[0].click();", collect_button)
            
            random_sleep(5, 7)
            return True, False # Success, newly collected
        except Exception: continue
    
    try:
        # Final keyword-based check of the whole page text for already collected status
        page_text = driver.execute_script("return document.body.innerText;").lower()
        if any(k in page_text for k in CONFIG["KEYWORDS"]["ALREADY_COLLECTED"]):
            print("DEBUG: Found 'already collected' keywords in page text.")
            return True, True

        potential_buttons = driver.execute_script("""
            return Array.from(document.querySelectorAll('div, button, a'))
                  .filter(el => {
                      const text = el.textContent.toLowerCase();
                      return (text.includes('collect') || text.includes('check') || text.includes('출석') || text.includes('적립')) && 
                             (el.className.includes('button') || el.tagName === 'BUTTON' || el.style.cursor === 'pointer');
                  });
        """)
        if potential_buttons:
            button = potential_buttons[0]
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
            random_sleep(1, 2)
            driver.execute_script("arguments[0].click();", button)
            print("Clicked potential collect button using JavaScript")
            random_sleep(5, 7)
            return True, False
    except Exception: pass
    return False, False

def enable_mobile_emulation(driver):
    """Enable mobile emulation to mimic an Android device with correct CDP parameters"""
    try:
        print("Switching to Android Mobile Emulation mode...")
        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {"width": 360, "height": 800, "deviceScaleFactor": 3, "mobile": True})
        driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {"enabled": True, "configuration": "mobile"})
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": CONFIG["USER_AGENTS"]["MOBILE"]})
        # Important: Refresh to apply mobile user agent and layout
        driver.get(CONFIG["URLS"]["COIN_MOBILE"])
        random_sleep(3, 5)
    except Exception as e:
        print(f"Warning: Failed to enable mobile emulation: {e}")

def disable_mobile_emulation(driver):
    """Switch back to desktop mode correctly"""
    try:
        print("Switching back to Desktop mode...")
        driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
        driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {"enabled": False})
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": CONFIG["USER_AGENTS"]["DESKTOP"]})
        random_sleep(1, 2)
    except Exception as e:
        print(f"Warning: Failed to disable mobile emulation: {e}")

def main():
    chrome_options = Options()
    effective_user_data = USER_DATA_DIR or os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_data")
    
    try:
        os.makedirs(effective_user_data, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={effective_user_data}")
        chrome_options.add_argument("--profile-directory=Default")
        print(f"Using persistent profile at: {effective_user_data}")
    except Exception as e:
        print(f"Warning: Could not set up persistent profile directory: {e}")

    if "HOME" not in os.environ:
        os.environ["HOME"] = "/tmp"

    if HEADLESS:
        print("Running in headless mode")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    try:
        if sys.platform.startswith("linux"):
            potential_binaries = ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]
            binary_path = next((p for p in potential_binaries if os.path.exists(p)), None)
            if binary_path: chrome_options.binary_location = binary_path
            
            potential_drivers = ["/usr/bin/chromedriver", "/usr/local/bin/chromedriver"]
            driver_path = next((p for p in potential_drivers if os.path.exists(p)), None)
            service = Service(executable_path=driver_path) if driver_path else Service(ChromeDriverManager().install())
        else:
            service = Service(ChromeDriverManager().install())
            
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("WebDriver initialized successfully")
    except Exception as e:
        print(f"Failed to initialize WebDriver: {e}")
        return
    
    try:
        driver.get(CONFIG["URLS"]["COIN_MOBILE"])
        random_sleep(2, 4)
        
        if not login(driver):
            print("Login process failed, attempting to continue anyway...")
        else:
            print("Successfully logged in")

        max_total_attempts = 3
        total_attempts = 0
        
        while total_attempts < max_total_attempts:
            # Health check: is browser still open?
            try:
                _ = driver.window_handles
            except Exception:
                print("CRITICAL: Browser was closed unexpectedly. Exiting.")
                return

            total_attempts += 1
            print(f"\n{'='*20} COLLECTION ATTEMPT {total_attempts}/{max_total_attempts} {'='*20}")
            
            disable_mobile_emulation(driver)
            is_already_korea = verify_korea_selected(driver)
            
            should_proceed = False
            if is_already_korea:
                should_proceed = True
            elif change_country_to_korea(driver):
                should_proceed = True
                random_sleep(5, 7)
            
            if should_proceed:
                # PHASE 1: MOBILE COLLECTION
                print(f"\n{'-'*15} PHASE 1: MOBILE COLLECTION {'-'*15}")
                enable_mobile_emulation(driver)
                # driver.get is now inside enable_mobile_emulation for better flow
                random_sleep(5, 8)
                
                mobile_success, mobile_already = find_and_click_collect_button(driver)
                if mobile_success:
                    if mobile_already: print("MOBILE: Already collected.")
                    else: print("MOBILE: New collection successful.")
                
                # PHASE 2: DESKTOP COLLECTION
                print(f"\n{'-'*15} PHASE 2: DESKTOP COLLECTION {'-'*15}")
                disable_mobile_emulation(driver)
                driver.get(CONFIG["URLS"]["COIN_DESKTOP"])
                random_sleep(8, 12)
                
                desktop_success, desktop_already = find_and_click_collect_button(driver)
                if desktop_success:
                    if desktop_already: print("DESKTOP: Already collected.")
                    else: print("DESKTOP: New collection successful.")
                
                if mobile_success and desktop_success:
                    print("\nCOMPLETED: Both phases reached a final state.")
                    break
            else:
                if total_attempts >= max_total_attempts:
                    enable_mobile_emulation(driver)
                    random_sleep(7, 10)
                    find_and_click_collect_button(driver)
                    disable_mobile_emulation(driver)
        
        print("Coin collection process completed.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
