import os
import sys
import json
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Load environment variables
load_dotenv()

def export_session():
    """Run a visible browser to log in and save cookies for the prod server"""
    print("Starting browser for session export...")
    
    chrome_options = Options()
    # Explicitly NOT headless
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Initialize WebDriver with same logic as main script
    try:
        if sys.platform.startswith("linux"):
            # Try to find system-installed Chromium binary
            potential_binaries = ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]
            binary_path = next((p for p in potential_binaries if os.path.exists(p)), None)
            
            if binary_path:
                print(f"Found system Chromium binary at: {binary_path}")
                chrome_options.binary_location = binary_path

            # Try to find system-installed chromedriver
            potential_drivers = ["/usr/bin/chromedriver", "/usr/local/bin/chromedriver"]
            driver_path = next((p for p in potential_drivers if os.path.exists(p)), None)
            
            if driver_path:
                print(f"Using system ChromeDriver at: {driver_path}")
                service = Service(driver_path)
            else:
                service = Service(ChromeDriverManager().install())
        else:
            service = Service(ChromeDriverManager().install())
            
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("WebDriver initialized successfully")
    except Exception as e:
        print(f"Failed to initialize WebDriver: {e}")
        return
    
    try:
        driver.get("https://www.aliexpress.com/")
        print("\n" + "="*60)
        print("ACTION REQUIRED: PLEASE LOG IN MANUALLY IN THE BROWSER WINDOW")
        print("Once you are logged in and see your account, return here.")
        print("="*60 + "\n")
        
        while True:
            user_input = input("Are you logged in? (y/n/q to quit): ").lower()
            if user_input == 'y':
                # Double check login indicators with a broader list
                page_source = driver.page_source.lower()
                # Include account-specific keywords and regional variations
                indicators = [
                    "sign out", "logout", "my orders", "message center", "my coupons",
                    "로그아웃", "내 주문", "메시지 센터", "내 쿠폰", "계정", "배송지",
                    "account", "orders", "wish list", "쿠폰", "센터"
                ]
                
                # Check for indicators in the main page source
                is_logged_in = any(ind in page_source for ind in indicators)
                
                # Also check if session cookies are present as a fallback
                cookies = driver.get_cookies()
                has_session_cookies = any(c.get('name') in ['alf', 'ali_apache_id', 'xman_t'] for c in cookies)
                
                if is_logged_in or has_session_cookies:
                    print(f"Login detected! (Indicator: {is_logged_in}, Cookies: {has_session_cookies})")
                    with open("cookies.json", "w") as f:
                        json.dump(cookies, f)
                    print("\nSUCCESS: cookies.json has been created.")
                    print("You can now upload cookies.json to your production server.")
                    break
                else:
                    print("Hmm, I don't see the login indicators yet. Please make sure you are fully logged in.")
                    print("Try navigating to the 'Account' or 'My Orders' page in the browser first.")
            elif user_input == 'q':
                print("Exiting without saving.")
                break
                
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    export_session()
