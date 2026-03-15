# football_logos.py: Backward-compatibility shim.
# Logo download has moved to Data/Access/football_logos.py
from Data.Access.football_logos import download_all_logos, download_all_countries
__all__ = ["download_all_logos", "download_all_countries"]
