# enrich_leagues.py: Backward-compatibility shim.
# League enrichment has moved to Modules/Flashscore/fs_league_enricher.py
from Modules.Flashscore.fs_league_enricher import main
__all__ = ["main"]