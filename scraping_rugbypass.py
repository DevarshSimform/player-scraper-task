import asyncio
# import re
import json
import os
import time
from typing import Dict, List

import aiohttp
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService

from decouple import config


class RugbyPassScrapper:

    PLAYER_BASE_URL = f"{config('RUGBYPASS_BASE_URL')}/players"
    RETRY_LIMIT = config("RETRY_LIMIT", cast=int)


    def __init__(self, country_name: str, url_log_path: str = None, data_log_path: str = None):
        self.base_url = config("RUGBYPASS_BASE_URL")
        self.country = f"/teams/{country_name}"
        self.driver = self._init_driver()
        
        self.url_log_file_path = url_log_path or self._create_log_file_path("logs_rugbypass", "player_profile_urls.json")
        self.player_data_log_file_path = data_log_path or self._create_log_file_path("logs_rugbypass", "player_data.json")


    def _init_driver(self):
        chrome_options = Options()
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # chrome_options.add_argument("--start-fullscreen")
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


    def scrape_player_urls(self) -> Dict[str, Dict[str, str]]:
        try:
            self.driver.get(f"{self.base_url}{self.country}")  

            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

            html = self.driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            player_data = {}

            viewports = soup.find_all("div", class_="flickity-viewport")
            for viewport in viewports:
                slider = viewport.find("div", class_="flickity-slider")
                if not slider:
                    continue

                player_cards = slider.select("div.player-item.carousel-cell")
                print("Total players found in slider =", len(player_cards))

                for player in player_cards:
                    try:
                        name_tag = player.find("div", class_="base").find("div", class_="name").find("div", class_="title")
                        name = name_tag.get_text(strip=True) if name_tag else "Unknown"

                        link_tag = player.find("a")
                        href = link_tag["href"] if link_tag and "href" in link_tag.attrs else ""
                        # currently of href = "{base_url}/players/william-waguespack/"
                        last_segment = "/" + href.rstrip("/").split("/")[-1] if href else ""
                        # last_segment = "/william-waguespack"
                        player_data[name] = {
                            "url": last_segment
                        }
                    except Exception as inner_e:
                        print("Error parsing player card:", inner_e)

            return player_data

        except Exception as e:
            print("Exception occurred:", e)
            self.driver.save_screenshot("snapshots/debug.png")
            return {}

        finally:
            self.driver.quit()

            print("Total Players =", len(player_data))
            self.write_log_file(self.url_log_file_path, player_data)



    async def _fetch_profile(
        self, session: aiohttp.ClientSession, name: str, relative_url: str) -> Dict:
        url = f"{self.PLAYER_BASE_URL}{relative_url}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        }
        
        for attempt in range(1, self.RETRY_LIMIT + 1):
            try:
                async with session.get(url, headers=headers, timeout=15) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")

                    # Get only the first player-details div
                    player_details = soup.find("div", class_="player-details")
                    data = {}

                    if player_details:
                        details = player_details.find_all("div", class_="detail")
                        for detail in details:
                            key = detail.find("h3").text.strip().lower()
                            value_div = detail.find_all("div")[-1]

                            if key in ["age", "position", "height", "weight"]:
                                data[key] = value_div.text.strip()

                    result = {
                        "name": name,
                        **data,  # unpack age, position, height, weight here
                        "profile_url": url,
                    }

                    return result


            except Exception as e:
                if attempt < self.RETRY_LIMIT:
                    await asyncio.sleep(1)
                    continue
                print(f"Failed to fetch {name}")
                return {
                    "name": name,
                    "age": "Error",
                    "position": "Error",
                    "height": "Error",
                    "weight": "Error",
                    "profile_url": url,
                    }


    async def fetch_all_profiles(self, player_data: Dict[str, str]) -> List[Dict]:
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._fetch_profile(session, name, player_data["url"])
                for name, player_data in player_data.items()
            ]
            return await asyncio.gather(*tasks)
        
    
    def write_log_file(self, path, data: List[Dict]):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data written to: {path}")
        
    
    def run(self):
        player_profile_urls = self.scrape_player_urls()
        if player_profile_urls:
            print(f"\nStarting async scraping for {len(player_profile_urls)} players...\n")
            start = time.time()
            profiles = asyncio.run(self.fetch_all_profiles(player_profile_urls))
            print(f"Fetched all profiles in {time.time() - start:.2f} seconds.")
            self.write_log_file(self.player_data_log_file_path, profiles)


    async def run_in_app(self):
        loop = asyncio.get_running_loop()
        # Run synchronous scraping in a thread
        player_profile_urls = await loop.run_in_executor(None, self.scrape_player_urls)
        if player_profile_urls:
            print(f"\nStarting async scraping for {len(player_profile_urls)} players...\n")
            start = time.time()
            profiles = await self.fetch_all_profiles(player_profile_urls)
            print(f"Fetched all profiles in {time.time() - start:.2f} seconds.")
            self.write_log_file(self.player_data_log_file_path, profiles)


if __name__ == "__main__":
    scraper = RugbyPassScrapper("usa")
    scraper.run()
    # asyncio.run(scraper.run_in_app())

