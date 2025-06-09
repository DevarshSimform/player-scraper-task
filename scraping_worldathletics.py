import ssl
# import certifi
import requests
import json
import time
import os
import asyncio
from typing import Dict, List


import aiohttp
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from decouple import config

# to solve SSL Certificate verification error.
# ssl_context = ssl.create_default_context(cafile=certifi.where())
# ssl_context.load_verify_locations(certifi.where())

# Disable (Do not use this in production it bypasses all SSL checks)
ssl_context = ssl._create_unverified_context()


class WorldAthleticsScrapper:

    PLAYER_BASE_URL = config("WORLDATHLETICS_BASE_URL")
    RETRY_LIMIT = config("RETRY_LIMIT", cast=int)


    def __init__(self, country: str = None, url_log_path: str = None, data_log_path: str = None):
        self.base_url = config("WORLDATHLETICS_BASE_URL")
        self.country = country or "United States"
        self.driver = self._init_driver()

        self.url_log_file_path = url_log_path or self._create_log_file_path("logs_worldathletics", "player_profile_urls.json")
        self.player_data_log_file_path = data_log_path or self._create_log_file_path("logs_worldathletics", "player_data.json")


    def _init_driver(self):
        chrome_options = Options()
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # chrome_options.add_argument("--start-fullscreen")
        chrome_options.add_argument('--headless')  # Run Chrome in headless mode
        chrome_options.add_argument('--disable-gpu')  # (optional) Disable GPU acceleration, recommended in headless mode
        chrome_options.add_argument('--no-sandbox')  # (optional) Required in some Linux environments
        chrome_options.add_argument('--window-size=1920,1080')  # Optional: set window size to avoid resolution issues
        service = ChromeService()
        return webdriver.Chrome(service=service, options=chrome_options)
    

    def _create_log_file_path(self, log_dir: str, log_filename: str) -> str:
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, log_filename)
    

    def scrape_players(self):
        try: 
            self.driver.get(f"{self.base_url}")
            select_federation_element = self.driver.find_element(By.ID, "countryCode")
            select = Select(select_federation_element)

            select.select_by_visible_text(self.country)
            time.sleep(2)

            html = self.driver.page_source
            
            soup = BeautifulSoup(html, "html.parser")

            player_data = {}

            table = soup.find("table", class_="AthleteSearch_results__3W7HB")
            table_body = table.contents[0]

            for row in table_body.contents[1:]:
                try:
                    table_div = row.find("td", class_="AthleteSearch_name__2z8I1")
                    name = table_div.a.text
                    gender = row.contents[2].text
                    href = table_div.a["href"] if table_div.a and "href" in table_div.a.attrs else ""
                    last_segment = "/" + href.rstrip("/").split("/")[-1] if href else ""

                    player_data[name] = {
                        "gender": gender,
                        "profile_url": last_segment
                    }
                except Exception as inner_e:
                        print("Error parsing in table div:", inner_e)
            return player_data

        except Exception as e:
            print("Exception occured", e)
            self.driver.save_screenshot("snapshots/debug.png")

        finally:
            self.driver.quit()

            print("Total Players =", len(player_data))
            self._write_log_file(self.url_log_file_path, player_data)


    async def _fetch_profile(
        self, session: aiohttp.ClientSession, name: str, relative_url: str, gender: str) -> Dict:
        url = f"{self.PLAYER_BASE_URL}/united-states{relative_url}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        }
        for attempt in range(1, self.RETRY_LIMIT + 1):
            try:
                async with session.get(url, headers=headers, timeout=60, ssl=ssl_context) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status} for {url}")
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")

                    data_div = soup.find("div", class_="athletesBio_athletesBioDetailsContainer__3_nDn")

                    birthdate_div = data_div.contents[1]
                    date_span = birthdate_div.find("span", class_="athletesBio_athletesBioTagValue__oKZC4")
                    birthdate_text = date_span.text.strip().split(" (")[0]  # Extract only the date part
                    age = self._calculate_age(birthdate_text)

                    code_div = data_div.contents[2]
                    code_span = code_div.find("span", class_="athletesBio_athletesBioTagValue__oKZC4")
                    player_code = code_span.text.strip()

                return {
                    "name": name,
                    "gender": gender,
                    "birthdate": birthdate_text,
                    "age": age,
                    "player_code": player_code,
                    "country": self.country,
                    "profile_url": url
                }

            except Exception as e:  
                if attempt < self.RETRY_LIMIT:
                    await asyncio.sleep(1)
                    continue
                print(f"Attempt {attempt} failed for {name} ({url}): {e}")
                return {
                    "name": name,
                    "gender": gender,
                    "birthdate": "error",
                    "player_code": "error",
                    "profile_url": url
                }
    

    async def fetch_all_profiles(self, player_data: Dict[str, str]) -> List[Dict]:
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._fetch_profile(session, name, player_data["profile_url"], player_data["gender"])
                for name, player_data in player_data.items()
            ]
            return await asyncio.gather(*tasks)


    def _write_log_file(self, path, data: List[Dict]):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data written to: {path}")



    def _calculate_age(self, birthdate_str: str) -> int:
        """
        Calculate age from a birthdate string in format: 'DD MMM YYYY' (e.g. '12 Jun 1996')
        """
        try:
            birthdate = datetime.strptime(birthdate_str, "%d %b %Y")
            today = datetime.today()
            age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
            return age
        except Exception as e:
            print(f"Error parsing birthdate '{birthdate_str}':", e)
            return -1  # or return None if preferred



    def run(self):
        player_profile_urls = self.scrape_players()
        if player_profile_urls:
            print(f"\nStarting async scraping for {len(player_profile_urls)} players...\n")
            start = time.time()
            profiles = asyncio.run(self.fetch_all_profiles(player_profile_urls))
            # profiles = self.fetch_all_profiles_sync(player_profile_urls)
            print(f"Fetched all profiles in {time.time() - start:.2f} seconds.")
            self._write_log_file(self.player_data_log_file_path, profiles)


    async def run_in_app(self):
        loop = asyncio.get_running_loop()
        # Run synchronous function in a thread
        player_profile_urls = await loop.run_in_executor(None, self.scrape_players)
        if player_profile_urls:
            print(f"\nStarting async scraping for {len(player_profile_urls)} players...\n")
            start = time.time()
            profiles = await self.fetch_all_profiles(player_profile_urls)
            print(f"Fetched all profiles in {time.time() - start:.2f} seconds.")
            self._write_log_file(self.player_data_log_file_path, profiles)


if __name__ == "__main__":
    scraper = WorldAthleticsScrapper()
    scraper.run()
    # asyncio.run(scraper.run_in_app())
