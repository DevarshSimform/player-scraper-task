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
sports247_path = Path("logs_247sports/player_data.json")
eurobasket_path = Path("logs_eurobasket/player_data.json")
proballers_path = Path("logs_proballers/player_data.json")


allrugby_players = []
rugbypass_players = []
worldathletics_players = []
sports247_players = []
eurobasket_players = []
proballers_players = []


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


sports247_players = load_players(sports247_path)
eurobasket_players = load_players(eurobasket_path)
proballers_players = load_players(proballers_path)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/allrugby", response_class=HTMLResponse)
async def read_players(request: Request):
    return templates.TemplateResponse("allrugby_player_list.html", {"request": request, "players": allrugby_players})


@app.get("/rugbypass", response_class=HTMLResponse)
async def read_players(request: Request):
    return templates.TemplateResponse("rugbypass_player_list.html", {"request": request, "players": rugbypass_players})


@app.get("/worldathletics", response_class=HTMLResponse)
async def read_players(request: Request):
    return templates.TemplateResponse("worldathletics_player_list.html", {"request": request, "players": worldathletics_players})


@app.get("/247sports", response_class=HTMLResponse)
async def read_players(request: Request):
    return templates.TemplateResponse("247sports_player_list.html", {"request": request, "players": sports247_players})


@app.get("/eurobasket", response_class=HTMLResponse)
async def read_players(request: Request):
    return templates.TemplateResponse("eurobasket_player_list.html", {"request": request, "players": eurobasket_players})


@app.get("/proballers", response_class=HTMLResponse)
async def read_players(request: Request):
    return templates.TemplateResponse("proballers_player_list.html", {"request": request, "players": proballers_players})
