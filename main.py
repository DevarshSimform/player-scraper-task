import json

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from scraping_allrugby import AllRugbyScraper
from scraping_rugbypass import RugbyPassScrapper
from scraping_worldathletics import WorldAthleticsScrapper


app = FastAPI()
templates = Jinja2Templates(directory="templates")


allrugby_path = Path("logs_allrugby/player_data.json")
rugbypass_path = Path("logs_rugbypass/player_data.json")
worldathletics_path = Path("logs_worldathletics/player_data.json")

allrugby_players = []
rugbypass_players = []
worldathletics_players = []


def load_players(path: str):
    file_path = Path(path)
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


@app.on_event("startup")
async def startup_event():
    global allrugby_players, rugbypass_players, worldathletics_players
    
    # AllRugby
    if not allrugby_path.exists():
        print("Starting AllRugby scraping...")
        allrugby_scraper = AllRugbyScraper("united-states")
        await allrugby_scraper.run_in_app()
    else:
        print("AllRugby JSON already exists, skipping scraping.")
    allrugby_players = load_players(allrugby_path)

    # RugbyPass
    if not rugbypass_path.exists():
        print("Starting RugbyPass scraping...")
        rugbypass_scraper = RugbyPassScrapper("usa")
        await rugbypass_scraper.run_in_app()
    else:
        print("RugbyPass JSON already exists, skipping scraping.")
    rugbypass_players = load_players(rugbypass_path)

    # WorldAthletics
    if not worldathletics_path.exists():
        print("Starting WorldAthletics scraping...")
        worldathletics_scraper = WorldAthleticsScrapper()
        await worldathletics_scraper.run_in_app()
    else:
        print("WorldAthletics JSON already exists, skipping scraping.")
    worldathletics_players = load_players(worldathletics_path)



@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/one", response_class=HTMLResponse)
async def read_players(request: Request):
    return templates.TemplateResponse("allrugby_player_list.html", {"request": request, "players": allrugby_players})


@app.get("/two", response_class=HTMLResponse)
async def read_players(request: Request):
    return templates.TemplateResponse("rugbypass_player_list.html", {"request": request, "players": rugbypass_players})


@app.get("/three", response_class=HTMLResponse)
async def read_players(request: Request):
    return templates.TemplateResponse("worldathletics_player_list.html", {"request": request, "players": worldathletics_players})