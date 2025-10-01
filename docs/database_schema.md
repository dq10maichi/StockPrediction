# Database Schema and Views

This document provides an overview of the key tables and views in the PostgreSQL database used by the stock prediction application.

## `prediction_summary` View

To provide a quick and comprehensive overview of the latest prediction status for all monitored tickers, the `prediction_summary` view is available. This view consolidates information from `target_tickers`, `stock_info`, `prediction_results`, and `trained_models` into a single, easy-to-query source.

### View Columns

| Column Name              | Type      | Description                                                                                             |
| ------------------------ | --------- | ------------------------------------------------------------------------------------------------------- |
| `ticker`                 | `varchar` | The ticker symbol of the stock.                                                                         |
| `company_name`           | `text`    | The name of the company. (From `stock_info` table)                                                      |
| `up_probability`         | `float`   | The probability from the latest 'up' trend prediction.                                                  |
| `up_model_version`       | `integer` | The version of the model used for the latest 'up' prediction.                                           |
| `up_model_creation_date` | `timestamptz` | The timestamp when the model for the 'up' prediction was trained.                                       |
| `up_model_recall`        | `float`   | The recall score of the 'up' model on its test set.                                                     |
| `up_model_roc_auc`       | `REAL`   | The ROC AUC score of the 'up' model on its test set.                                                    |
| `up_model_accuracy`      | `float`   | The accuracy score of the 'up' model on its test set.                                                   |
| `up_model_f1_score`      | `float`   | The F1 score of the 'up' model on its test set.                                                         |
| `down_probability`       | `float`   | The probability from the latest 'down' trend prediction.                                                |
| `down_model_version`     | `integer` | The version of the model used for the latest 'down' prediction.                                         |
| `down_model_creation_date`| `timestamptz` | The timestamp when the model for the 'down' prediction was trained.                                     |
| `down_model_recall`      | `float`   | The recall score of the 'down' model on its test set.                                                   |
| `down_model_roc_auc`     | `float`   | The ROC AUC score of the 'down' model on its test set.                                                  |
| `down_model_accuracy`    | `float`   | The accuracy score of the 'down' model on its test set.                                                 |
| `down_model_f1_score`    | `float`   | The F1 score of the 'down' model on its test set.                                                       |
| `stock_data_updated_at`  | `date`    | The most recent date for which stock price data is available in the `daily_stock_prices` table.         |

### Creation and Update

The view is defined in `SQL/create_summary_view.sql`. To create or update the view in the database, run the following `make` command:

```bash
make create-summary-view
```
This command executes the SQL script and applies the latest view definition to the database..