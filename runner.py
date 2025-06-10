from scrapper import USBasketScraper, sports247, Proballer

from scraping_allrugby import AllRugbyScraper
from scraping_rugbypass import RugbyPassScrapper
from scraping_worldathletics import WorldAthleticsScrapper

# eurobasked_obj = USBasketScraper()
# eurobasked_obj.start()

# sport_obj = sports247()
# sport_obj.start()

# allrugby_obj = AllRugbyScraper("united-states")
# allrugby_obj.run()

# rugbypass_obj = RugbyPassScrapper("usa")
# rugbypass_obj.run()

# worldathletics_obj = WorldAthleticsScrapper()
# worldathletics_obj.run()

proballer_obj = Proballer()
proballer_obj.start()