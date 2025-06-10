from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
import time

# Optional: Configure Chrome options
chrome_options = Options()
chrome_options.add_argument("--start-fullscreen")  # Open Chrome maximized

# Path to your ChromeDriver, or use it from PATH
service = ChromeService()

# Start Chrome browser
driver = webdriver.Chrome(service=service, options=chrome_options)

# Open the website
driver.get("https://all.rugby/")

# Keep the browser open for a while (optional)
time.sleep(10)

# Optionally, close the browser
driver.quit()
