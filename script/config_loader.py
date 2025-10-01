import configparser
from pathlib import Path
import os

CONFIG_PATH = Path(__file__).resolve().parent.parent / 'config.ini'

class ConfigLoader:
    def __init__(self, path=CONFIG_PATH):
        self.config = configparser.ConfigParser()
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found at: {path}")
        self.config.read(path)

    def _get_list(self, section, option, type_converter):
        """Helper to get a comma-separated list from config."""
        value_str = self.config.get(section, option)
        if not value_str:
            return []
        return [type_converter(x.strip()) for x in value_str.split(',')]

    

    def get_target_settings(self):
        """Get settings for the classification target."""
        horizon = self.config.getint('classification_target', 'prediction_horizon', fallback=10)
        threshold = self.config.getfloat('classification_target', 'return_threshold', fallback=0.03)
        return horizon, threshold

    def get_feature_settings(self):
        """Get settings for feature engineering."""
        lags = self._get_list('feature_engineering', 'feature_lag_days', int)
        mas = self._get_list('feature_engineering', 'ma_periods', int)
        return lags, mas

    def get_hp_search_settings(self, test_mode=False):
        """Get settings for hyperparameter search."""
        settings = {
            'optuna_n_trials': self.config.getint('hyperparameter_search', 'optuna_n_trials_test' if test_mode else 'optuna_n_trials'),
            'random_n_iter': self.config.getint('hyperparameter_search', 'random_n_iter_test' if test_mode else 'random_n_iter'),
            'grid_params': {
                'n_estimators': self._get_list('hyperparameter_search', 'grid_n_estimators_test' if test_mode else 'grid_n_estimators', int),
                'learning_rate': self._get_list('hyperparameter_search', 'grid_learning_rate_test' if test_mode else 'grid_learning_rate', float),
                'num_leaves': self._get_list('hyperparameter_search', 'grid_num_leaves_test' if test_mode else 'grid_num_leaves', int),
            }
        }
        return settings

# Create a single, global instance to be imported by other modules
config_loader = ConfigLoader()
