
import sys
from unittest.mock import MagicMock, patch
import unittest
import os
import json
from datetime import datetime
import pytz

# Mock Firebase before importing scraper to avoid initialization side effects
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

from scraper import get_volume_spikes, save_daily_close, MARKET_OPEN_H, PKT

class TestVolumeSpikeScreener(unittest.TestCase):

    def setUp(self):
        # Mock rolling averages directly to avoid complex Firestore mocking
        self.patcher_avg = patch('scraper.get_rolling_avg')
        self.mock_avg = self.patcher_avg.start()
        
        def side_effect(symbol):
            averages = {
                'LUCK': 1000000,
                'HUBC': 2000000,
                'TRG': 400000
            }
            return averages.get(symbol, 0)
        self.mock_avg.side_effect = side_effect

    def tearDown(self):
        self.patcher_avg.stop()

    @patch('scraper.os.path.exists', return_value=True)
    @patch('scraper.get_all_stocks')
    @patch('scraper.datetime')
    def test_spike_ratio_calculation(self, mock_datetime, mock_get_all, mock_exists):
        # 11:30 AM = 11.5 H. Market opened at 9.5. Elapsed = 2.0 hours.
        fixed_now = datetime(2026, 3, 12, 11, 30, tzinfo=PKT)
        mock_datetime.now.return_value = fixed_now
        
        mock_get_all.return_value = [
            {"symbol": "LUCK", "price": 800.0, "change": 2.5, "volume": "1,000,000"} # Today vol 1M
        ]
        
        spikes = get_volume_spikes()
        self.assertEqual(len(spikes), 1)
        self.assertEqual(spikes[0]['symbol'], "LUCK")
        self.assertEqual(spikes[0]['spike_ratio'], 3.0)

    @patch('scraper.os.path.exists', return_value=True)
    @patch('scraper.get_all_stocks')
    @patch('scraper.datetime')
    def test_volume_projection_caps(self, mock_datetime, mock_get_all, mock_exists):
        # Market closed (after 15:30 PM PKT)
        mock_get_all.return_value = [
            {"symbol": "LUCK", "price": 800.0, "change": 2.5, "volume": "2,000,000"}
        ]
        
        fixed_now = datetime(2026, 3, 12, 16, 30, tzinfo=PKT)
        mock_datetime.now.return_value = fixed_now
        
        spikes = get_volume_spikes()
        self.assertEqual(len(spikes), 1)
        self.assertEqual(spikes[0]['spike_ratio'], 2.0)

    @patch('scraper.os.path.exists', return_value=True)
    @patch('scraper.get_all_stocks')
    @patch('scraper.datetime')
    def test_illiquid_filter(self, mock_datetime, mock_get_all, mock_exists):
        # TRG avg_vol (400K) < 500K
        mock_get_all.return_value = [
            {"symbol": "TRG", "price": 70.0, "change": 5.0, "volume": "2,000,000"} 
        ]
        
        fixed_now = datetime(2026, 3, 12, 12, 0, tzinfo=PKT)
        mock_datetime.now.return_value = fixed_now
        
        spikes = get_volume_spikes()
        self.assertEqual(len(spikes), 0)

    @patch('scraper.os.path.exists', return_value=True)
    @patch('scraper.datetime')
    def test_market_hours_guard(self, mock_datetime, mock_exists):
        # Before market open
        fixed_now = datetime(2026, 3, 12, 8, 0, tzinfo=PKT)
        mock_datetime.now.return_value = fixed_now
        
        spikes = get_volume_spikes()
        self.assertEqual(len(spikes), 0)

    @patch('scraper.os.path.exists', return_value=True)
    @patch('scraper.get_all_stocks')
    @patch('scraper.datetime')
    def test_sorting_order(self, mock_datetime, mock_get_all, mock_exists):
        fixed_now = datetime(2026, 3, 12, 15, 30, tzinfo=PKT)
        mock_datetime.now.return_value = fixed_now
        
        mock_get_all.return_value = [
            {"symbol": "LUCK", "price": 800.0, "change": 1.0, "volume": "2,000,000"}, # 2.0x (Baseline 1M)
            {"symbol": "HUBC", "price": 120.0, "change": 1.0, "volume": "8,000,000"}, # 4.0x (Baseline 2M)
        ]
        
        spikes = get_volume_spikes()
        self.assertEqual(len(spikes), 2)
        self.assertEqual(spikes[0]['symbol'], "HUBC")
        self.assertEqual(spikes[1]['symbol'], "LUCK")

    pass # Removed baseline test as logic moved to Cloud/Firestore (Mocking verified in previous tests)

if __name__ == '__main__':
    unittest.main()
