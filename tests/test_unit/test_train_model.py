import pandas as pd
import pytest

# Since we cannot import from the script directory directly, we need to add it to the path
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / 'script'))

from train_model import create_classification_target

@pytest.fixture
def price_data_for_targeting():
    """Creates a sample DataFrame for testing target creation."""
    # Data is designed to have clear up, down, and neutral movements
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=30, freq='D'))
    prices = (
        [100] * 10 + # Flat period
        [110] * 10 + # 10% jump
        [95] * 10    # 13.6% drop from 110
    )
    data = {'adj_close_price': prices}
    df = pd.DataFrame(data, index=dates)
    return df

def test_create_classification_target_up(price_data_for_targeting):
    """Tests the creation of the 'up' classification target."""
    # Arrange
    df = price_data_for_targeting
    horizon = 10 # days
    threshold = 0.05 # 5%

    # Act
    result_df, target_col_name = create_classification_target(df, horizon, threshold, direction='up')

    # Assert
    assert target_col_name == f'target_{horizon}d_up_{int(threshold*100)}pct'
    assert target_col_name in result_df.columns

    # The price at day 0 is 100. 10 days later (day 10) it's 110. Return is (110-100)/100 = 0.10 (10%)
    # This is >= 5% threshold, so target should be 1.
    assert result_df[target_col_name].iloc[0] == 1

    # The price at day 10 is 110. 10 days later (day 20) it's 95. Return is (95-110)/110 = -0.136
    # This is not >= 5% threshold, so target should be 0.
    assert result_df[target_col_name].iloc[10] == 0

def test_create_classification_target_down(price_data_for_targeting):
    """Tests the creation of the 'down' classification target."""
    # Arrange
    df = price_data_for_targeting
    horizon = 10 # days
    threshold = 0.05 # 5%

    # Act
    result_df, target_col_name = create_classification_target(df, horizon, threshold, direction='down')

    # Assert
    assert target_col_name == f'target_{horizon}d_down_{int(threshold*100)}pct'
    assert target_col_name in result_df.columns

    # The price at day 0 is 100. 10 days later (day 10) it's 110. Return is 0.10 (10%)
    # This is not <= -5% threshold, so target should be 0.
    assert result_df[target_col_name].iloc[0] == 0

    # The price at day 10 is 110. 10 days later (day 20) it's 95. Return is (95-110)/110 = -0.136 (-13.6%)
    # This is <= -5% threshold, so target should be 1.
    assert result_df[target_col_name].iloc[10] == 1
