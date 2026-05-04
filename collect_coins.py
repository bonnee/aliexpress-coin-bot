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
        # Simply move directly to the element - safest approach
        actions = ActionChains(driver)
        actions.move_to_element(element)
        actions.perform()
        random_sleep(0.3, 0.7)
    except Exception as e:
        print(f"Warning: Simple mouse movement failed: {e}. Trying direct click.")

def type_like_human(element, text):
    """Type text with human-like timing and occasional mistakes that get corrected"""
    for char in text:
        # Randomly decide if we make a typo (1% chance)
        if random.random() < 0.01:
            # Make a typo
            typo_char = random.choice('qwertyuiopasdfghjklzxcvbnm')
            element.send_keys(typo_char)
            random_sleep(0.1, 0.3)
            # Delete the typo
            element.send_keys(Keys.BACKSPACE)
            random_sleep(0.2, 0.5)
        
        # Type the correct character
        element.send_keys(char)
        
        # Random pause between keystrokes
        random_sleep(0.05, 0.15)
        
        # Occasionally pause longer as if thinking
        if random.random() < 0.05:
            random_sleep(0.5, 1.2)

def save_cookies(driver, path=COOKIE_FILE):
    """Save cookies from the current session to a JSON file"""
    try:
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
            return False
            
        with open(path, 'r') as f:
            cookies = json.load(f)
            
        # We must be on the domain to add cookies for it
        driver.get("https://www.aliexpress.com/")
        random_sleep(2, 3)
        
        for cookie in cookies:
            try:
                # Selenium doesn't like 'expiry' in some cases if it's not an int
                if 'expiry' in cookie:
                    cookie['expiry'] = int(cookie['expiry'])
                driver.add_cookie(cookie)
            except Exception as e:
                # Skip problematic cookies
                continue
                
        print(f"Loaded {len(cookies)} cookies from {path}")
        driver.refresh()
        random_sleep(3, 5)
        return True
    except Exception as e:
        print(f"Failed to load cookies: {e}")
        return False

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
        
        # Get the latest update ID to ignore old messages
        last_update_id = -1
        updates = await bot.get_updates(offset=-1, timeout=10)
        if updates:
            last_update_id = updates[0].update_id
            
        print("Waiting for Telegram response...")
        # Poll for new messages
        start_time = time.time()
        timeout = 300  # 5 minutes timeout
        
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

def login(driver):
    """Perform the login process with human-like behavior, checking for existing session first"""
    try:
        print("Checking if already logged in...")
        
        # Try to load cookies if they exist
        if os.path.exists(COOKIE_FILE):
            print("Found cookies.json, attempting to load session...")
            load_cookies(driver)
        else:
            driver.get("https://www.aliexpress.com/")
            random_sleep(5, 7)
        
        # Look for indicators of being logged in
        page_source = driver.page_source.lower()
        
        # Multiple check points for login status
        login_indicators = [
            "sign out", "logout", "my orders", "message center", "my coupons",
            "로그아웃", "내 주문", "메시지 센터", "내 쿠폰", "계정", "배송지"
        ]
        is_logged_in = any(indicator in page_source for indicator in login_indicators)
        
        if is_logged_in:
            print("Detected existing session (Logged in).")
            # Refresh cookies if we just logged in
            save_cookies(driver)
            return True

        print("Not logged in (Indicators not found). Starting login process...")
        # Navigate to a direct login-triggering URL
        driver.get("https://s.click.aliexpress.com/e/_DB2kEjh")
        random_sleep(3, 5)

        # ... (rest of the login logic remains the same until 2FA) ...

        random_sleep(3, 5)

        # Wait for the email input field
        wait = WebDriverWait(driver, 15)
        
        # Check if we are actually on a login page or if we bypassed it
        try:
            # More generic selector for the email field
            email_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Email'], input[label*='Email'], #fm-login-id"))
            )
            print("Found email input field")
        except:
            # Re-check if we are logged in - maybe the redirect just took a moment
            if "sign out" in driver.page_source.lower():
                print("Bypassed login, 'Sign Out' detected.")
                return True
            print("Error: Could not find login fields nor 'Sign Out' indicator.")
            return False
        
        # Ensure email field is visible in the viewport
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", email_input)
        random_sleep(1, 2)
        
        # Try to click directly without sophisticated mouse movement
        try:
            email_input.click()
        except Exception as e:
            print(f"Direct click failed: {e}, trying JavaScript click")
            driver.execute_script("arguments[0].click();", email_input)
        
        random_sleep(0.5, 1.5)
        
        # Type email with human-like behavior
        print("Entering email address...")
        type_like_human(email_input, ALIEXPRESS_EMAIL)  # Use environment variable
        random_sleep(1, 2)
        
        # Find and click the Continue button
        continue_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, 
                "//button[contains(@class, 'cosmos-btn-primary') and .//span[text()='Continue']]"))
        )
        print("Found continue button")
        
        # Ensure button is in view and click it
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", continue_button)
        random_sleep(0.5, 1)
        
        try:
            continue_button.click()
        except Exception as e:
            print(f"Direct click failed: {e}, trying JavaScript click")
            driver.execute_script("arguments[0].click();", continue_button)
            
        print("Clicked continue button")
        random_sleep(2, 3)
        
        # Wait for password field to appear
        password_input = wait.until(
            EC.presence_of_element_located((By.ID, "fm-login-password"))
        )
        print("Found password field")
        
        # Ensure password field is in view
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", password_input)
        random_sleep(0.5, 1)
        
        # Click on password field
        try:
            password_input.click()
        except Exception as e:
            print(f"Direct click failed: {e}, trying JavaScript click")
            driver.execute_script("arguments[0].click();", password_input)
            
        random_sleep(0.5, 1)
        
        # Type password with human-like behavior
        print("Entering password...")
        type_like_human(password_input, ALIEXPRESS_PASSWORD)  # Use environment variable
        random_sleep(1, 2)
        
        # Find and click the Sign in button
        sign_in_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, 
                "//button[contains(@class, 'cosmos-btn-primary') and .//span[text()='Sign in']]"))
        )
        print("Found sign in button")
        
        # Ensure sign in button is in view and click it
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", sign_in_button)
        random_sleep(0.5, 1)
        
        try:
            sign_in_button.click()
        except Exception as e:
            print(f"Direct click failed: {e}, trying JavaScript click")
            driver.execute_script("arguments[0].click();", sign_in_button)
            
        print("Clicked sign in button")
        
        # --- Check for Email Verification / 2FA ---
        random_sleep(3, 5)
        
        # Helper to check for 2FA keywords in page and iframes
        def check_for_2fa(driver):
            source = driver.page_source.lower()
            keywords = ["verification code", "verify your identity", "enter code", "sent to your email", "인증 번호", "security verification"]
            if any(k in source for k in keywords):
                return True
            
            # Check iframes
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                try:
                    driver.switch_to.frame(iframe)
                    inner_source = driver.page_source.lower()
                    driver.switch_to.default_content()
                    if any(k in inner_source for k in keywords):
                        return True
                except:
                    driver.switch_to.default_content()
            return False

        if check_for_2fa(driver):
            print("\n" + "!" * 50)
            print("ACTION REQUIRED: Email Verification Detected!")
            if USE_TELEGRAM:
                asyncio.run(send_telegram_screenshot(driver, "🚨 AliExpress 2FA Detected!"))
            print("Please check your email and enter the verification code below.")
            print("!" * 50 + "\n")
            
            # Try to find the input field for the code
            try:
                # Helper to find code input, including in iframes
                def find_code_input(driver):
                    selectors = [
                        "input[placeholder*='code']", "input[id*='checkcode']", 
                        ".next-input.next-large input", "input[name='checkCode']",
                        "input[class*='checkcode']", "input[aria-label*='code']"
                    ]
                    for s in selectors:
                        try:
                            el = driver.find_element(By.CSS_SELECTOR, s)
                            if el.is_displayed(): return el
                        except: continue
                    
                    # Try iframes
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    for iframe in iframes:
                        try:
                            driver.switch_to.frame(iframe)
                            for s in selectors:
                                try:
                                    el = driver.find_element(By.CSS_SELECTOR, s)
                                    if el.is_displayed(): return el # Note: staying in iframe if found
                                except: continue
                            driver.switch_to.default_content()
                        except: driver.switch_to.default_content()
                    return None

                code_input = find_code_input(driver)
                
                if code_input:
                    if USE_TELEGRAM:
                        verification_code = asyncio.run(get_2fa_from_telegram())
                    else:
                        if HEADLESS:
                            print("CRITICAL: 2FA required in headless mode but Telegram is not configured. Cannot proceed.")
                            return False
                        verification_code = input("Enter verification code: ").strip()
                    
                    if verification_code:
                        type_like_human(code_input, verification_code)
                        random_sleep(1, 2)
                        
                        # Try to find and click submit/verify button
                        try:
                            verify_btn = driver.find_element(By.XPATH, "//button[contains(., 'Verify') or contains(., 'Submit') or contains(., '확인') or contains(., 'OK')]")
                            verify_btn.click()
                        except:
                            code_input.send_keys(Keys.ENTER)
                        
                        print("Verification code submitted.")
                        driver.switch_to.default_content() # Ensure we're back
                    else:
                        print("No verification code provided.")
                else:
                    print("Could not find verification code input field automatically.")
                    if USE_TELEGRAM:
                        asyncio.run(send_telegram_screenshot(driver, "🚨 2FA detected but I couldn't find the input field automatically."))
                    
                    if not HEADLESS:
                        input("Press Enter here once you have finished the verification in the browser...")
            except Exception as ve:
                print(f"Error handling verification: {ve}")
                driver.switch_to.default_content()

        # Wait for login to complete
        random_sleep(5, 7)
        
        # Final check if login was actually successful
        if any(indicator in driver.page_source.lower() for indicator in ["sign out", "logout", "로그아웃"]):
            print("Login successful")
            save_cookies(driver)
            return True
        else:
            print("Login check failed. Please check the browser/screenshot.")
            if USE_TELEGRAM:
                asyncio.run(send_telegram_screenshot(driver, "❌ Login failed. Check the state of the page."))
            return False
    
    except Exception as e:
        print(f"Login failed: {e}")
        if USE_TELEGRAM:
            asyncio.run(send_telegram_screenshot(driver, f"❌ Login exception: {e}"))
        return False

def change_country_to_korea(driver):
    """Change the country to Korea using the ship-to dropdown with manual confirmation at each step"""
    try:
        wait = WebDriverWait(driver, 15)
        
        # Look for the ship-to dropdown with the exact class structure from the HTML
        print("Looking for the ship-to dropdown...")
        try:
            # Try to find the main ship-to menu item
            ship_to_dropdown = wait.until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//div[contains(@class, 'ship-to--menuItem--')]"))
            )
            print("Found ship-to dropdown using menuItem class")
        except Exception as e:
            print(f"menuItem selector failed: {e}, trying alternative selector")
            # Try looking for the div containing USD with dropdown icon
            try:
                ship_to_dropdown = wait.until(
                    EC.element_to_be_clickable((By.XPATH, 
                        "//div[contains(@class, 'ship-to--text--')]/b[contains(text(), 'USD')]"))
                )
                print("Found ship-to dropdown using USD text")
            except Exception as e2:
                print(f"USD text selector failed too: {e2}, trying broader selector")
                # Try the most specific element that should be unique to this dropdown
                ship_to_dropdown = wait.until(
                    EC.element_to_be_clickable((By.XPATH, 
                        "//div[contains(@class, 'es--wrap--')]/div/div[contains(@class, 'ship-to--menuItem--')]"))
                )
                print("Found ship-to dropdown using es--wrap container")
        
        # Scroll to make the dropdown visible
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", ship_to_dropdown)
        random_sleep(1, 2)
        
        # Highlight the element to make it visible in logs
        driver.execute_script("arguments[0].style.border='3px solid red'", ship_to_dropdown)
        print("STEP 1: Ship-to dropdown found. Clicking automatically...")
        random_sleep(1, 1)
        
        # Click on the ship-to dropdown
        try:
            ship_to_dropdown.click()
            print("Clicked ship-to dropdown using normal click")
        except Exception as e:
            print(f"Normal click failed: {e}, trying JavaScript click")
            driver.execute_script("arguments[0].click();", ship_to_dropdown)
            print("Clicked ship-to dropdown using JavaScript")
        
        random_sleep(2, 3)
        
        # Now look for the Korea option in the country dropdown section
        # First, find the country selector text element
        try:
            print("Looking for country selector...")
            country_selector = wait.until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//div[contains(@class, 'select--text')]"))
            )
            print("Found country selector")
            
            # Highlight the element
            driver.execute_script("arguments[0].style.border='3px solid red'", country_selector)
            print("STEP 2: Country selector found. Clicking automatically...")
            random_sleep(1, 1)
            
            # Click on the country selector to open the dropdown
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", country_selector)
            random_sleep(0.5, 1)
            
            try:
                country_selector.click()
                print("Clicked country selector using normal click")
            except Exception as e:
                print(f"Normal click failed: {e}, trying JavaScript click")
                driver.execute_script("arguments[0].click();", country_selector)
                print("Clicked country selector using JavaScript")
                
            random_sleep(1.5, 2.5)
            
            # Now that the country dropdown is open, search for Korea
            search_input = wait.until(
                EC.presence_of_element_located((By.XPATH, 
                    "//div[contains(@class, 'select--search')]/input"))
            )
            print("Found country search input")
            
            # Highlight the element
            driver.execute_script("arguments[0].style.border='3px solid red'", search_input)
            print("STEP 3: Search input found. Typing 'Korea'...")
            random_sleep(1, 1)
            
            # Click on search input and type 'Korea'
            search_input.click()
            random_sleep(0.5, 1)
            
            # Try with English first, then Korean if needed
            search_term = "Korea"
            type_like_human(search_input, search_term)
            random_sleep(1, 2)
            
            # Press ENTER
            search_input.send_keys(Keys.ENTER)
            random_sleep(1, 2)
            
            # Check if search result is visible and needs clicking
            try:
                korea_option = wait.until(
                    EC.element_to_be_clickable((By.XPATH, 
                        "//div[contains(@class, 'select--item') and (contains(., 'Korea') or contains(., '대한민국') or contains(., '한국'))]"))
                )
                print("Found Korea option in list. Clicking...")
                driver.execute_script("arguments[0].click();", korea_option)
            except:
                # If not found with "Korea", try with "대한민국"
                print("Korea not found with English term, trying Korean term...")
                # Clear input first
                search_input.send_keys(Keys.CONTROL + "a")
                search_input.send_keys(Keys.BACKSPACE)
                random_sleep(0.5, 1)
                type_like_human(search_input, "대한민국")
                random_sleep(1, 2)
                search_input.send_keys(Keys.ENTER)
                random_sleep(1, 2)
                
                try:
                    korea_option = wait.until(
                        EC.element_to_be_clickable((By.XPATH, 
                            "//div[contains(@class, 'select--item') and (contains(., 'Korea') or contains(., '대한민국') or contains(., '한국'))]"))
                    )
                    driver.execute_script("arguments[0].click();", korea_option)
                except:
                    print("Korea option still not found in list (might have been selected via Enter).")
            
            random_sleep(1.5, 2.5)
            
        except Exception as e:
            print(f"Country selection process failed: {e}")
            return False
        
        # Look for Save button
        try:
            print("Looking for Save/Apply button...")
            save_button_selectors = [
                "//div[contains(@class, 'es--saveBtn')]",
                "//button[contains(., 'Save')]",
                "//button[contains(., 'Apply')]",
                "//div[contains(@class, 'button') and contains(., 'Save')]",
                "//div[contains(@class, 'button') and contains(., 'Apply')]"
            ]
            
            save_button = None
            for selector in save_button_selectors:
                try:
                    save_button = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    print(f"Found save button with selector: {selector}")
                    break
                except:
                    continue
            
            if not save_button:
                raise Exception("Could not find Save or Apply button")
            
            # Highlight and click
            driver.execute_script("arguments[0].style.border='3px solid red'", save_button)
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", save_button)
            random_sleep(1, 1)
            
            try:
                save_button.click()
            except:
                driver.execute_script("arguments[0].click();", save_button)
            
            print("Clicked Save button.")
            random_sleep(3, 5)
            print("Country has been saved")
            return True
            
        except Exception as e:
            print(f"Save button interaction failed: {e}")
            return False
            
    except Exception as e:
        print(f"Country change failed: {e}")
        return False

def verify_korea_selected(driver):
    """Verify that Korea is currently selected as the country"""
    try:
        wait = WebDriverWait(driver, 10)
        
        # Multiple selectors for the ship-to element
        selectors = [
            "//div[contains(@class, 'ship-to--text--')]",
            "//div[contains(@class, 'ship-to--menuItem--')]",
            "//div[contains(@class, 'es--wrap--')]//div[contains(@class, 'ship-to--menuItem--')]",
            "//div[contains(@class, 'header--right--')]//div[contains(@class, 'ship-to')]"
        ]
        
        ship_to_element = None
        for selector in selectors:
            try:
                ship_to_element = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                if ship_to_element:
                    print(f"Found ship-to element with selector: {selector}")
                    break
            except:
                continue
                
        if not ship_to_element:
            print("Warning: Could not find ship-to element to verify country.")
            return False
            
        # Get the text content and include child elements
        ship_to_text = driver.execute_script("return arguments[0].innerText;", ship_to_element)
        print(f"Current ship-to text detected: {ship_to_text}")
        
        # Standard check for indicators
        ship_to_text_lower = ship_to_text.lower()
        # 'kr' is common in 'KR/USD', '한국' is Korea in Korean
        korea_indicators = ['korea', '한국', '대한민국', ' south korea', 'republic of korea', 'ko/', 'kr/']
        
        if any(indicator in ship_to_text_lower for indicator in korea_indicators):
            print("Confirmation: Korea is already selected as the country.")
            return True
        else:
            print(f"Detected location text '{ship_to_text}', which does not match Korea indicators.")
            return False
            
    except Exception as e:
        print(f"Error verifying Korea selection: {e}")
        return False

def find_and_click_collect_button(driver):
    """Find and click the coin collect button with multiple approaches"""
    print("STEP 7: Looking for the Collect button...")
    wait = WebDriverWait(driver, 15)
    
    # List of possible selectors for the collect button - ordered from most to least specific
    collect_button_selectors = [
        "//*[@id='signButton' or contains(@class, 'checkin-button')]", # Combined ID and Class
        "//div[contains(text(), 'Collect') and contains(@class, 'button')]",
        "//div[contains(text(), '출석체크') and contains(@class, 'button')]",  # Korean for "attendance check"
        "//div[contains(text(), '적립하기') and contains(@class, 'button')]",   # Korean for "collect"
        "//div[contains(text(), '체크인') and contains(@class, 'button')]",     # Korean for "check-in"
        "//div[contains(text(), '받기') and contains(@class, 'button')]",     # Korean for "check-in"
        "//button[contains(@class, 'check-in') or contains(@class, 'checkin')]",
        "//div[contains(@class, 'coin') and contains(@class, 'collect')]",
    ]
    
    # Try each selector until one works
    for selector in collect_button_selectors:
        try:
            print(f"Trying to find collect button with selector: {selector}")
            collect_button = wait.until(
                EC.presence_of_element_located((By.XPATH, selector))
            )
            print(f"Found the Collect button using selector: {selector}")
            
            # Highlight the button to make it more visible
            driver.execute_script("arguments[0].style.border='3px solid red'", collect_button)
            random_sleep(1, 2)
            
            # Scroll to make button visible if needed
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", collect_button)
            random_sleep(1, 2)
            
            # Try to click button with several methods
            try:
                # Move mouse naturally to the button first
                move_mouse_randomly(driver, collect_button)
                
                # Try normal click
                collect_button.click()
                print("Clicked collect button using normal click")
            except Exception as e:
                print(f"Normal click failed: {e}, trying JavaScript click")
                driver.execute_script("arguments[0].click();", collect_button)
                print("Clicked collect button using JavaScript")
            
            # Wait after clicking to see the result
            random_sleep(5, 7)
            print("Collect button clicked successfully")
            return True
            
        except Exception as e:
            print(f"Couldn't find or click collect button with selector {selector}: {e}")
            continue
    
    # If no button found, try a more aggressive approach - look for any clickable element that might be the collect button
    try:
        print("Trying fallback approach - looking for any element that might be the collect button")
        
        # Use JavaScript to find elements that might be collect buttons
        potential_buttons = driver.execute_script("""
            return Array.from(document.querySelectorAll('div, button, a'))
                  .filter(el => {
                      const text = el.textContent.toLowerCase();
                      return (text.includes('collect') || 
                              text.includes('check') || 
                              text.includes('출석') || 
                              text.includes('적립') || 
                              text.includes('체크')) && 
                             (el.className.includes('button') || 
                              el.tagName === 'BUTTON' ||
                              el.style.cursor === 'pointer');
                  });
        """)
        
        if potential_buttons and len(potential_buttons) > 0:
            print(f"Found {len(potential_buttons)} potential collect buttons using JavaScript")
            
            # Try clicking the first potential button
            button = potential_buttons[0]
            driver.execute_script("arguments[0].style.border='3px solid red'", button)
            random_sleep(1, 2)
            
            # Scroll to button
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
            random_sleep(1, 2)
            
            # Click the button using JavaScript
            driver.execute_script("arguments[0].click();", button)
            
            print("Clicked potential collect button using JavaScript")
            random_sleep(5, 7)
            return True
    except Exception as e:
        print(f"Fallback approach failed: {e}")
    
    print("Could not find any collect button despite multiple attempts")
    print("*** WILL RESTART FROM STEP 1 (COUNTRY SELECTION) ***")
    return False

def enable_mobile_emulation(driver):
    """Enable mobile emulation to mimic an Android device with correct CDP parameters"""
    try:
        print("Switching to Android Mobile Emulation mode...")
        # Correct CDP parameters for Emulation.setDeviceMetricsOverride
        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width": 360,
            "height": 800,
            "deviceScaleFactor": 3,
            "mobile": True
        })
        # Enable touch emulation separately
        driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {
            "enabled": True,
            "configuration": "mobile"
        })
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {
            "userAgent": "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"
        })
        random_sleep(2, 3)
    except Exception as e:
        print(f"Warning: Failed to enable mobile emulation: {e}")

def disable_mobile_emulation(driver):
    """Switch back to desktop mode correctly"""
    try:
        print("Switching back to Desktop mode...")
        driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
        driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {"enabled": False})
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
        })
        random_sleep(1, 2)
    except Exception as e:
        print(f"Warning: Failed to disable mobile emulation: {e}")

def main():
    """Main function to run the coin collection process"""
    # ... (Setup code same as before)

    """Main function to run the coin collection process"""
    # Set up Chrome options
    chrome_options = Options()

    # Use persistent user data directory for session cookies
    # If not specified in ENV, we'll try to use a local 'chrome_data' folder
    effective_user_data = USER_DATA_DIR or os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_data")
    
    try:
        os.makedirs(effective_user_data, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={effective_user_data}")
        chrome_options.add_argument("--profile-directory=Default")
        print(f"Using persistent profile at: {effective_user_data}")
    except Exception as e:
        print(f"Warning: Could not set up persistent profile directory: {e}")
        print("Continuing with a temporary profile (cookies will not be saved).")

    # Ensure HOME is set for Chromium (crucial for systemd)
    if "HOME" not in os.environ:
        os.environ["HOME"] = "/tmp"
        print("Warning: HOME environment variable was not set. Defaulting to /tmp")

    if HEADLESS:
        print("Running in headless mode")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-gpu-sandbox")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-background-networking")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--remote-debugging-port=9222")

    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Initialize WebDriver
    try:
        # Check if we are in a Linux environment where we might have a system-installed driver
        if sys.platform.startswith("linux"):
            # Try to find system-installed Chromium binary
            potential_binaries = ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]
            binary_path = next((p for p in potential_binaries if os.path.exists(p)), None)
            
            if binary_path:
                print(f"Found system Chromium binary at: {binary_path}")
                chrome_options.binary_location = binary_path
                # Enhanced Internal check
                try:
                    import subprocess
                    check = subprocess.run([binary_path, "--version"], capture_output=True, text=True, timeout=5)
                    if check.returncode == 0:
                        print(f"Chromium version check OK: {check.stdout.strip()}")
                    else:
                        print(f"Chromium version check FAILED (Code {check.returncode}): {check.stderr.strip()}")
                except Exception as ce:
                    print(f"Chromium execution check failed: {ce}")

            # Try to find system-installed chromedriver
            potential_drivers = ["/usr/bin/chromedriver", "/usr/local/bin/chromedriver"]
            driver_path = next((p for p in potential_drivers if os.path.exists(p)), None)
            
            if driver_path:
                print(f"Using system ChromeDriver at: {driver_path}")
                # Enable verbose logging
                service = Service(
                    executable_path=driver_path,
                    log_output="chromedriver.log",
                    service_args=["--verbose"]
                )
            else:
                print("System ChromeDriver not found, using ChromeDriverManager")
                service = Service(ChromeDriverManager().install())
        else:
            # On Windows/Mac, use ChromeDriverManager
            print("Using ChromeDriverManager to set up ChromeDriver")
            service = Service(ChromeDriverManager().install())
            
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("WebDriver initialized successfully")
    except Exception as e:
        print(f"Failed to initialize WebDriver: {e}")
        if os.path.exists("chromedriver.log"):
            print("\n--- LAST 20 LINES OF CHROMEDRIVER LOG ---")
            with open("chromedriver.log", "r") as f:
                lines = f.readlines()
                for line in lines[-20:]:
                    print(line.strip())
        print("\nPossible fix: Try running: rm -rf /app/chrome_data/*")
        return
    
    # Set a realistic user agent
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    })
    
    try:
        # Navigate to the website
        driver.get("https://s.click.aliexpress.com/e/_DB2kEjh")
        print("Website loaded")
        
        # Add random delay to simulate page load analysis by human
        random_sleep(2, 4)
        
        # Check if we need to login and proceed with login if necessary
        login_successful = login(driver)
        if not login_successful:
            print("Login process failed, attempting to continue anyway...")
        else:
            print("Successfully logged in")

        # Main collection loop - allows restarting from Step 1 when needed
        max_total_attempts = 3  # Maximum number of complete cycles to try
        total_attempts = 0
        
        while total_attempts < max_total_attempts:
            total_attempts += 1
            print(f"Starting collection attempt {total_attempts}/{max_total_attempts}")
            
            # STEP 1-5: Change country to Korea
            print("Checking if country change to Korea is needed...")
            disable_mobile_emulation(driver) # Desktop mode for check/change
            
            is_already_korea = verify_korea_selected(driver)
            
            should_proceed = False
            if is_already_korea:
                print("Country is already Korea. Proceeding to collection.")
                should_proceed = True
            elif change_country_to_korea(driver):
                print("Country successfully changed to Korea.")
                should_proceed = True
                # Wait a bit for the page to reload/update after change
                random_sleep(5, 7)
            
            if should_proceed:
                # Switch to Mobile mode for the actual collection
                enable_mobile_emulation(driver)
                
                # Navigate to the coin page
                print("Going to coin page after country change (Mobile Emulation).")
                driver.get("https://s.click.aliexpress.com/e/_DB2kEjh")
                
                # Give it some time for initial load
                random_sleep(5, 8)
                
                # Check if page is stuck/blank and needs a refresh
                try:
                    # Look for signs of life (any content in the body)
                    body_text = driver.execute_script("return document.body ? document.body.innerText.length : 0;")
                    if body_text < 100:  # Very little content likely means it's stuck or a blank loader
                        print("Page seems stuck or blank. Triggering a refresh...")
                        driver.refresh()
                        random_sleep(8, 12)
                    else:
                        print("Page loaded content successfully.")
                        random_sleep(2, 4)
                except Exception as e:
                    print(f"Error checking page content: {e}. Refreshing just in case.")
                    driver.refresh()
                    random_sleep(8, 12)
                
                # STEP 7: Look for the collect button
                if find_and_click_collect_button(driver):
                    print("Successfully collected coins!")
                    disable_mobile_emulation(driver)
                    break  # Exit the loop if successful
                else:
                    print(f"Failed to find collect button on attempt {total_attempts}, restarting from Step 1")
                    # Continue loop to restart from Step 1
            else:
                print(f"Country change failed on attempt {total_attempts}")
                
                # If we're on the last attempt and country change failed, try the coin page anyway
                if total_attempts >= max_total_attempts:
                    print("Maximum attempts reached. Trying coin page directly as last resort...")
                    enable_mobile_emulation(driver)
                    driver.get("https://s.click.aliexpress.com/e/_DB2kEjh")
                    random_sleep(7, 10)
                    find_and_click_collect_button(driver)
                    disable_mobile_emulation(driver)
                
        if total_attempts >= max_total_attempts:
            print("Maximum attempts reached without successful coin collection.")
            
        print("Coin collection process completed.")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        # Don't close the browser immediately
        print("Script execution complete. Closing browser in 5 seconds...")
        random_sleep(3, 5)
        driver.quit()

if __name__ == "__main__":
    main()
