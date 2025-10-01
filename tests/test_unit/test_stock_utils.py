# This file will contain unit tests for stock_utils.py
# We will start by testing the create_features function.

import pandas as pd
import pytest

# Since we cannot import from the script directory directly, we need to add it to the path
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / 'script'))

from stock_utils import create_features


@pytest.fixture
def sample_stock_data():
    """Creates a sample DataFrame for testing feature creation."""
    periods = 100
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=periods, freq='D'))
    prices = [100 + i for i in range(periods)]
    data = {
        'adj_close_price': prices,
        'open_price': prices,
        'high_price': prices,
        'low_price': prices,
        'volume': [1000] * periods
    }
    df = pd.DataFrame(data, index=dates)
    return df

def test_create_features_calculates_sma(sample_stock_data):
    """Tests if SMA is calculated correctly by create_features."""
    # Arrange
    main_df = sample_stock_data
    
    # Act
    features_df = create_features(main_df, {}, pd.DataFrame())
    
    # Assert
    # Check if the SMA column for the period 5 exists
    assert 'SMA_5' in features_df.columns
    
    # Check the last valid SMA value.
    # The input prices for the last 5 days are [195, 196, 197, 198, 199]
    expected_last_sma = (195 + 196 + 197 + 198 + 199) / 5
    assert features_df['SMA_5'].iloc[-1] == expected_last_sma

def test_create_features_calculates_rsi(sample_stock_data):
    """Tests if RSI is calculated correctly by create_features."""
    # Arrange
    main_df = sample_stock_data
    
    # Act
    features_df = create_features(main_df, {}, pd.DataFrame())
    
    # Assert
    # Check if the RSI column exists
    assert 'RSI_14' in features_df.columns
    
    # For a constantly increasing price, RSI should be 100.
    assert features_df['RSI_14'].iloc[-1] == 100.0
