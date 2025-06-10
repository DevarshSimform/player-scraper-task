from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from multiprocessing import Process, Pool, cpu_count
from selenium.common.exceptions import NoSuchElementException
import json
import time
import logging
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils import _create_log_file_path


logging.basicConfig(level=logging.INFO)


class USBasketScraper:
    def __init__(self, url='https://www.usbasket.com/NBA-G-League/basketball-players.aspx'):
        self.url = url
        self.driver = webdriver.Chrome()
        self.headers = ['Player Name', 'Team Name', 'League', 'Nationality', 'Age', 'Height', 'Pos']
        self.data = []
        self.player_data_log_file_path =  _create_log_file_path("logs_eurobasket", "player_data.json")

    def start(self):
        self.driver.get(self.url)
        self.extract_header_values()
        self.extract_all_pages()

        self.save_to_file(self.player_data_log_file_path)
        self.driver.quit()

    def extract_header_values(self):
        html = self.driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        players_table = soup.find("table", attrs={"id": "players"})
        header_row = players_table.find("tr", attrs={"class": "TD_result_header"})
        header_cols = header_row.find_all("a", attrs={"class": "dataTablelink"})
        header_values = [h.text for h in header_cols]

        print("Extracted Headers:", header_values)

    def extract_all_pages(self):
        # Select 100 rows per page if option exists
        try:
            page_select = self.driver.find_element(By.ID, "Paging")
            page_select.send_keys("100")
            time.sleep(3)  # wait for DOM to update
        except:
            pass

        result_div = self.driver.find_element(By.ID, "results")

        while True:
            page_data = self.extract_current_page_data()
            self.data.extend(page_data)

            try:
                next_btn = result_div.find_element(By.XPATH, "./table[2]/tbody/tr/td[2]/span[2]/a")
                next_btn.click()
                time.sleep(3)
            except NoSuchElementException:
                break

        # Fetch player bios
        for player in self.data:
            if player['Player Profile Link']:
                player['Bio'] = self.get_player_bio(player['Player Profile Link'])

    def extract_current_page_data(self):
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        players_table = soup.find("table", attrs={"id": "players"})
        table_body = players_table.find("tbody")
        player_rows = table_body.find_all("tr")

        page_data = []

        for row in player_rows:
            data_cells = row.find_all("td")
            player_info = {key: '' for key in self.headers}
            player_info['Player Profile Link'] = ''
            player_info['Bio'] = ''

            for i, cell in enumerate(data_cells):
                if i == 0:
                    profile_link = cell.find("a")
                    if profile_link:
                        player_info[self.headers[i]] = profile_link.text.strip()
                        player_info['Player Profile Link'] = profile_link.get('href')
                else:
                    player_info[self.headers[i]] = cell.text.strip()

            page_data.append(player_info)

        return page_data

    def get_player_bio(self, profile_url):
        try:
            self.driver.get(profile_url)
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            bio_div = soup.find('div', class_='newseotxt')
            return bio_div.get_text(strip=True) if bio_div else ''
        except Exception as e:
            print(f"Error fetching bio for {profile_url}: {e}")
            return ''

    def save_to_file(self, filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)
        print(f"Saved {len(self.data)} player records to {filepath}")


class Proballer:
    def __init__(
        self, url="https://www.proballers.com/basketball/league/3/nba/players"
    ):
        self.url = "https://www.proballers.com/basketball/league/3/nba/players"
        self.scrapped_data = []
        self.profile_obj = {
            "Basketball Player": "",
            "Basketball Team": "",
            "Age": "",
            "Height": "",
            "Home Country": "",
            "Profile URL": "",
            "Team URL": "",
            "Bio": "",
            "Date-of-birth": "",
            "game_stats": {
                "points": "",
                "rebounds": "",
                "assists": "",
                "steals": "",
                "blocks": "",
            },
        }
        self.init_driver()
        self.player_data_log_file_path =  _create_log_file_path("logs_proballers", "player_data.json")
    
    def init_driver(self):
        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")

        # Set page load strategy to "eager"
        self.chrome_options.set_capability("pageLoadStrategy", "eager")
        self.driver = webdriver.Chrome(options=self.chrome_options)
        self.driver.maximize_window()

    def start(self):
        self.driver.get(self.url)

        html_page = self.driver.page_source

        print('Scrapping player profile urls ...')
        self.scrapped_data = self.dom_traverse(html_page)
        print('Start to scrap player profiles ...')
        # print(self.scrapped_data)

        for obj in self.scrapped_data:
            print(f'Scrapping data for player {obj["Basketball Player"]}')
            time.sleep(1.5)
            prof_data = self.scrap_player_profile(obj["Profile URL"])
            obj.update(prof_data)

        self.save_to_json(self.player_data_log_file_path)

        self.driver.close()

    def save_to_json(self, filepath="temp/proballers.json"):
        with open(filepath, "w") as f:
            json.dump(self.scrapped_data, f)

    def dom_traverse(self, html_page):
        soup = BeautifulSoup(html_page, "lxml")
        scrapped_data = []

        body = soup.find("body")

        parent = body.find(
            "div", attrs={"class": "home-league__player-list__content__tables__content"}
        )

        all_tables = parent.find_all("div", attrs={"class": "mb-3"})
        for table in all_tables:
            table_data = self.scrap_table(table)
            scrapped_data.extend(table_data)

        return scrapped_data
    
    def load_json_data(self, filepath='scrapped_data/proballers.json'):
        with open(filepath, 'r') as f:
            data = f.read()
            serialized_data = json.loads(data)
        
        return serialized_data
    
    def scrap_profile_data_from_file(self, retries=3):
        scrapped_data = self.load_json_data('scrapped_data/proballers.json')
        # print(scrapped_data)
        reqs = 0
        for obj in scrapped_data:
            time.sleep(1.5)
            prof_data = {}
            try:
                prof_data = self.scrap_player_profile(obj["Profile URL"])
                reqs += 1
            except Exception as e:
                logging.warning(f"Getting error: {e}")
                break
                
            obj.update(prof_data)
        
        self.scrapped_data = scrapped_data
        self.save_to_json("temp/proballers.json")
        # return scrapped_data

    def scrap_table(self, table):
        table_data = []
        tb = table.find("table", attrs={"class": "table"})
        tbody = tb.find("tbody")
        records = tbody.find_all("tr")
        heads = [
            "Basketball Player",
            "Basketball Team",
            "Age",
            "Height",
            "Home Country",
        ]
        base_url = "https://www.proballers.com"
        for tr in records:
            data = list(tr.find_all("td"))
            player_obj = {
                "Basketball Player": "",
                "Basketball Team": "",
                "Age": "",
                "Height": "",
                "Home Country": "",
                "Profile URL": "",
                "Team URL": "",
                "Bio": "",
                "Date-of-birth": "",
                "game_stats": {
                    "points": "",
                    "rebounds": "",
                    "assists": "",
                    "steals": "",
                    "blocks": "",
                },
            }
            for i, td in enumerate(data):
                try:
                    if i == 0:
                        player_obj[heads[i]] = str(td.get_text()).strip()
                        try:
                            profile_link = td.find(
                                "a", attrs={"class", "list-player-entry"}
                            )
                            player_obj["Profile URL"] = base_url + str(
                                profile_link.get("href")
                            )
                        except:
                            print("Profile URL not available!")
                    elif i == 1:
                        team_link = (
                            td.find("ul")
                            .find("li")
                            .find("a", attrs={"class": "list-team-entry"})
                        )
                        player_obj["Basketball Team"] = str(
                            team_link.get_text()
                        ).strip()
                        player_obj["Team URL"] = team_link.get("href")
                    else:
                        player_obj[heads[i]] = str(td.get_text())
                except:
                    print(f"{heads[i]} is missing!")

            table_data.append(player_obj)

        return table_data

    def scrap_player_profile(self, url):

        try:

            # Open profile in new tab
            self.driver.set_page_load_timeout(60)
            self.driver.execute_script("window.open(arguments[0]);", url)
            self.driver.switch_to.window(self.driver.window_handles[1])

            # Wait for bio content
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.banner__biography__content p"))
            )

            html_page = self.driver.page_source

            player_stats = self.extract_profile_data(html_page)
        # Close profile tab
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])

            return player_stats
        
        except Exception as e:
            print(f"Error for row: {e}")
            # If a tab is left open, close it and return to main tab
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])

    def extract_profile_data(self, html_page):
        data_obj = {
            "Bio": "",
            "Height": "",
            "Date-of-birth": "",
            "game_stats": {
                "points": "",
                "rebounds": "",
                "assists": "",
                "steals": "",
                "blocks": "",
            },
        }
        soup = BeautifulSoup(html_page, "lxml")

        body = soup.find("body")

        main_div = body.find("div", attrs={"class": "identity__stats"})

        profile_info = main_div.find("div", attrs={"class": "identity__stats__profil"})
        stats_ul = main_div.find("ul", attrs={"class": "identity__stats__stats"})

        stat_info_divs = list(profile_info.find_all("div"))

        data_obj["Date-of-birth"] = (
            str(stat_info_divs[0].find("span", attrs={"class": "info"}).get_text()).strip()
        )
        data_obj["Height"] = (
            str(stat_info_divs[1].find("span", attrs={"class": "info"}).get_text()).strip()
        )

        game_stat_heads = ["points", "rebounds", "assists", "steals", "blocks"]

        stats_li = list(stats_ul.find_all("li"))
        for i, li in enumerate(stats_li):
            data_obj["game_stats"][game_stat_heads[i]] = str(li.find(
                "span", attrs={"class": "stat"}
            ).get_text()).strip()

        bio_parent = body.find("div", attrs={"class": "banner__biography__content"})
        data_obj['Bio'] = str(bio_parent.find("p").get_text()).strip()

        return data_obj




class sports247:
    def __init__(self):
        self.scrapped_data = []
        self.init_driver()
        self.player_data_log_file_path =  _create_log_file_path("logs_247sports", "player_data.json")

    def init_driver(self):
        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")

        # Set page load strategy to "eager"
        self.chrome_options.set_capability("pageLoadStrategy", "eager")
        self.driver = webdriver.Chrome(options=self.chrome_options)
        self.driver.maximize_window()

    def save_to_json(self, filepath="temp/sport72.json"):
        with open(filepath, "w") as f:
            json.dump(self.scrapped_data, f)

    def start(self, url = "https://247sports.com/season/2024-basketball/transferportal/"):
        self.driver.get(url)
        time.sleep(3)
        html_page = self.driver.page_source
        self.extract_data(html_page)
        self.save_to_json(self.player_data_log_file_path)
        self.driver.quit()


    def extract_data(self, html_page):
        soup = BeautifulSoup(html_page, "lxml")
        body = soup.find("body")

        players_section = body.find("section", attrs={"class": "transfer-results"})
        players_el_lst = list(players_section.find_all("section", attrs={"class": "transfer-group"}))

        for p in players_el_lst:
            player_profile_link = p.find("h3").find("a").get("href")
            player = self.scrap_player_profile(player_profile_link)
            self.scrapped_data.append(player)

    def scrap_player_profile(self, url):
        # Open profile in new tab
        self.driver.set_page_load_timeout(60)
        self.driver.execute_script("window.open(arguments[0]);", url)
        self.driver.switch_to.window(self.driver.window_handles[1])

        # # Wait for bio content
        # WebDriverWait(self.driver, 10).until(
        #     EC.presence_of_element_located((By.CSS_SELECTOR, "div.banner__biography__content p"))
        # )

        html_page = self.driver.page_source

        player = self.extract_player_profile(html_page)
        player['Profile URL'] = url
    # Close profile tab
        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[0])
        return player

    def extract_player_profile(self, html):
        player = {"Player Name": '', "Profile URL": '', "POS": '', "Height": '', "Weight": '', "High School": '', "City": '', "Exp": ''}
        soup = BeautifulSoup(html, "lxml")

        body = soup.find("body")

        player["Player Name"] = body.find("h1", attrs={"class": "name"}).text
        
        metric_list = list(body.find("ul", attrs={"class": "metrics-list"}).find_all("li"))

        heads = ["POS", "Height", "Weight"]
        for i, e in enumerate(metric_list):
            metric = list(e.find_all("span"))
            player[heads[i]] = metric[1].text
        
        details = list(body.find("ul", attrs={"class": "details"}).find_all("li"))

        details_heads = ["High School", "City", "Exp"]
        for i, e in enumerate(details):
            try:
                detail = list(e.find_all("span"))
                player[details_heads[i]] = detail[1].text
            except:
                pass

        print(player)
        return player