import asyncio
import re
import json
import os
import time
from typing import Dict, List, Tuple

import aiohttp
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService

from decouple import config


class AllRugbyScraper:

    PLAYER_BASE_URL = config("ALLRUGBY_BASE_URL")
    RETRY_LIMIT = config("RETRY_LIMIT", cast=int)

    def __init__(self, country_path: str, url_log_path: str = None, data_log_path: str = None):
        self.base_url = f"{self.PLAYER_BASE_URL}/players"
        self.country = f"/{country_path}"
        self.driver = self._init_driver()

        self.url_log_file_path = url_log_path or self._create_log_file_path("logs_allrugby", "player_profile_urls.json")
        self.player_data_log_file_path = data_log_path or self._create_log_file_path("logs_allrugby", "player_data.json")


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


    def scrape_players(self) -> Dict[str, str]:
        try:
            self.driver.get(f"{self.base_url}{self.country}")

            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

            html = self.driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            player_data = {}

            for div in soup.find_all("div", class_="bloc jou"):
                a = div.find("a")
                if a and a.b and a.get("href"):
                    first_name = a.contents[2].strip()
                    last_name = a.b.get_text(strip=True)
                    full_name = f"{first_name} {last_name}"

                    href = a["href"]
                    # Extract text after <a> tag — which contains age
                    text_after_a = div.get_text(separator=" ", strip=True).replace(a.get_text(strip=True), "")
                    age_match = re.search(r"(\d{1,2})\s*years", text_after_a)
                    age = int(age_match.group(1)) if age_match else None

                    player_data[full_name] = {
                        "href": href,
                        "age": age
                    }

            return player_data

        except Exception as e:
            print("Exception:", e)
            self.driver.save_screenshot("snapshots/debug.png")
            return {}

        finally:
            self.driver.quit()

            print("Total Players =", len(player_data))
            self.write_log_file(self.url_log_file_path, player_data)



    def _extract_height_weight_from_bio(self, bio_text: str) -> Tuple[float, float]:

        bio_text = bio_text.lower()

        # Match height in meters (e.g., "2 m", "1.85 meters")
        height_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(m|meter|meters)\b", bio_text)

        # Match any float/int weight like "105.5 kg", "72 kilograms", etc.
        weight_match = re.search(r"(\d+(?:\.\d{1,2})?)\s*(kg|kgs|kilogram|kilograms)\b", bio_text)

        height = float(height_match.group(1)) if height_match else None
        weight = float(weight_match.group(1)) if weight_match else None

        return height, weight

    

    async def _fetch_profile(
        self, session: aiohttp.ClientSession, name: str, relative_url: str, age: str = None
    ) -> Dict:
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

                    bio_section = soup.find("div", class_="bio")
                    bio = bio_section.get_text() if bio_section else "N/A"
                    bio = " ".join(bio.split())
                    if bio != "N/A":
                        height, weight = self._extract_height_weight_from_bio(bio)

                    career_section = soup.find("div", class_="parcours")
                    career_list = [
                        li.get_text(strip=True)
                        for li in career_section.find_all("li")
                        if li.get_text(strip=True)
                    ] if career_section else []

                    return {
                        "name": name,
                        "age": age,
                        "profile_url": url,
                        "height_m": height,
                        "weight_kg": weight,
                        "bio": bio,
                        "career": career_list,
                    }

            except Exception as e:
                if attempt < self.RETRY_LIMIT:
                    await asyncio.sleep(1)
                    continue
                print(f"Failed to fetch {name} after {self.RETRY_LIMIT} attempts: {e}")
                return {
                    "name": name,
                    "profile_url": url,
                    "bio": "Error",
                }


    async def fetch_all_profiles(self, player_data: Dict[str, str]) -> List[Dict]:
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._fetch_profile(session, name, player_data["href"], player_data["age"])
                for name, player_data in player_data.items()
            ]
            return await asyncio.gather(*tasks)


    def write_log_file(self, path, data: List[Dict]):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Data written to: {path}")


    def run(self):
        player_data = self.scrape_players()
        if player_data:
            print(f"\nStarting async scraping for {len(player_data)} players...\n")
            start = time.time()
            player_profiles = asyncio.run(self.fetch_all_profiles(player_data))
            print(f"Fetched all profiles in {time.time() - start:.2f} seconds.")
            self.write_log_file(self.player_data_log_file_path, player_profiles)


    async def run_in_app(self):
        loop = asyncio.get_running_loop()
        # Run synchronous scraping in a thread
        player_data = await loop.run_in_executor(None, self.scrape_players)
        if player_data:
            print(f"\nStarting async scraping for {len(player_data)} players...\n")
            start = time.time()
            player_profiles = await self.fetch_all_profiles(player_data)
            print(f"Fetched all profiles in {time.time() - start:.2f} seconds.")
            self.write_log_file(self.player_data_log_file_path, player_profiles)


if __name__ == "__main__":
    scraper = AllRugbyScraper("united-states")
    scraper.run()
    # asyncio.run(scraper.run_in_app())
