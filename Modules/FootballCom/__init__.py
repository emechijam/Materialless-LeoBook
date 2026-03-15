"""
Football.com Booking Package
Main entry point for Football.com betting operations.
"""

from .navigator import load_or_create_session, perform_login, extract_balance, navigate_to_schedule, select_target_date
from .extractor import extract_league_matches, validate_match_data
from .booker import harvest_booking_codes, place_stairway_accumulator, force_clear_slip, check_and_perform_withdrawal

from .fb_manager import run_football_com_booking

__all__ = [
    'run_football_com_booking',
    'load_or_create_session',
    'perform_login',
    'extract_balance',
    'navigate_to_schedule',
    'select_target_date',
    'extract_league_matches',
    'validate_match_data',
    'harvest_booking_codes',
    'place_stairway_accumulator',
    'force_clear_slip',
    'check_and_perform_withdrawal'
]
