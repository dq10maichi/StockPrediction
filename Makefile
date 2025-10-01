# Makefile for stockv2 project

# --- .env ファイルから環境変数を読み込む ---
ifneq (,$(wildcard .env))
    include .env
    export
endif

# --- Variables ---
IMAGE_NAME = stock-app
TICKER ?= 
FEATURES ?= 
TEST ?= false
DIRECTION ?= up
VERSION ?= 
YEARS ?= 5
SEARCH_METHOD ?= optuna

# If TEST is true, add the --test-mode flag
ifeq ($(TEST), true)
    TEST_FLAG = --test-mode
else
    TEST_FLAG = 
endif

# If VERSION is set, add the --version flag
ifeq ($(VERSION),)
    VERSION_FLAG =
else
    VERSION_FLAG = --version $(VERSION)
endif

# If TICKER is set, add the --ticker flag
ifeq ($(TICKER),)
    TICKER_FLAG =
else
    TICKER_FLAG = --ticker $(TICKER)
endif

# Add the --training-years flag
YEARS_FLAG = --training-years $(YEARS)

# Add the --search-method flag
SEARCH_METHOD_FLAG = --search-method $(SEARCH_METHOD)

# Docker run command base with volume mounts
DOCKER_RUN_BASE = docker run --rm \
    -v $(CURDIR):/app \
    --env-file .env

# Docker run command for running tests
DOCKER_RUN_TEST = docker run --rm \
    -v $(CURDIR):/app \
    --network host \
    --env-file .env



# --- Targets ---

.PHONY: build init-db update-data train-up train-down train predict-up predict-down predict predict-all list-models evaluate-model all bash help list-tickers add-ticker remove-ticker send-notifications test test-unit test-integration


# Send pending notifications
send-notifications:
	@echo "Sending pending model and prediction notifications..."
	$(DOCKER_RUN_BASE) \
	-e GSPREAD_SHEET_NAME \
	-e GDRIVE_SHARED_DRIVE_ID \
	-e SMTP_HOST \
	-e SMTP_PORT \
	-e SMTP_USER \
	-e SMTP_PASSWORD \
	-e SMTP_SENDER \
	-e SMTP_RECIPIENT \
	$(IMAGE_NAME) python /app/script/send_notifications.py


# Build the Docker image
build:
	@echo "Building Docker image..."
	docker build -t $(IMAGE_NAME) .

# Initialize the database (destructive)
init-db:
	@echo "Initializing the database. This will delete all existing data."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) /app/script/build_script.sh --mode update

# Update stock and economic data (non-destructive)
update-data:
	@echo "Updating all data in the database (non-destructive)..."
	@echo "Step 1: Ensuring database schema exists..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/ensure_schema.py
	@echo "Step 2: Updating stock data..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/update_stock_data.py
	@echo "Step 3: Updating economic data..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/update_economic_data.py


# Train the UP model for a specific ticker
train-up:
	@echo "Training UP model for ticker: $(TICKER) using last $(YEARS) years..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/train_model.py --ticker $(TICKER) --direction up $(TEST_FLAG) $(YEARS_FLAG) $(SEARCH_METHOD_FLAG)

# Train the DOWN model for a specific ticker
train-down:
	@echo "Training DOWN model for ticker: $(TICKER) using last $(YEARS) years..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/train_model.py --ticker $(TICKER) --direction down $(TEST_FLAG) $(YEARS_FLAG) $(SEARCH_METHOD_FLAG)

# Train both UP and DOWN models
train:
	@echo "Training both UP and DOWN models for ticker: $(TICKER) using last $(YEARS) years..."
	make train-up TICKER=$(TICKER) TEST=$(TEST) YEARS=$(YEARS) SEARCH_METHOD=$(SEARCH_METHOD)
	make train-down TICKER=$(TICKER) TEST=$(TEST) YEARS=$(YEARS) SEARCH_METHOD=$(SEARCH_METHOD)

# Predict UP trend using the latest trained model
predict-up:
	@echo "Predicting UP trend for ticker: $(TICKER)..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/predict.py --ticker $(TICKER) --direction up

# Predict DOWN trend using the latest trained model
predict-down:
	@echo "Predicting DOWN trend for ticker: $(TICKER)..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/predict.py --ticker $(TICKER) --direction down

# Predict both UP and DOWN trends
predict:
	@echo "Predicting both UP and DOWN trends for ticker: $(TICKER)..."
	make predict-up TICKER=$(TICKER)
	make predict-down TICKER=$(TICKER)

# Predict for all target tickers in the database
predict-all:
	@echo "Predicting for all target tickers in the database..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/predict_all.py

# --- Model Diagnosis ---

# List all trained models for a specific ticker
list-models:
	@echo "Listing models..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/diagnose_model.py $(TICKER_FLAG)

# Evaluate a specific model version
evaluate-model:
	@echo "Evaluating model for ticker: $(TICKER), direction: $(DIRECTION), version: $(VERSION)..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/diagnose_model.py --ticker $(TICKER) --direction $(DIRECTION) $(VERSION_FLAG)

# --- Ticker Management ---

# Update stock info for a specific ticker
update-info:
	@echo "Updating stock info for ticker: $(TICKER)..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/update_stock_info.py --ticker $(TICKER)

# List all target tickers in the database
list-tickers:
	@echo "Listing all target tickers..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/manage_tickers.py list

# Add or update a target ticker in the database
add-ticker:
	@echo "Adding/updating ticker: $(TICKER) with features: $(FEATURES)..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/manage_tickers.py add --ticker "$(TICKER)" --features "$(FEATURES)"

# Remove a target ticker from the database
remove-ticker:
	@echo "Removing ticker: $(TICKER)..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/manage_tickers.py remove --ticker "$(TICKER)"

# --- Bulk Evaluation ---

.PHONY: evaluate-all evaluate-all-fresh test-evaluation

# Run the bulk evaluation pipeline (resumes from last run)
evaluate-all:
	@echo "Starting bulk evaluation... (resuming if possible)"
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/bulk_evaluate.py

# Run the bulk evaluation pipeline from scratch
evaluate-all-fresh:
	@echo "Starting bulk evaluation from scratch..."
	docker run --rm \
    -v $(CURDIR)/predictions:/app/predictions \
    -v $(CURDIR)/logs:/app/logs \
    -v $(CURDIR)/models:/app/models \
    -v $(CURDIR)/script:/app/script \
    -v $(CURDIR)/plots:/app/plots \
    -v $(CURDIR)/SQL:/app/SQL \
    -v $(CURDIR)/tickers.json:/app/tickers.json:ro \
    -v $(CURDIR)/secrets:/app/secrets:ro \
    -v $(CURDIR)/list.csv:/app/list.csv:ro \
    $(IMAGE_NAME) python /app/script/bulk_evaluate.py --fresh

# Run a test evaluation with a small dataset
test-evaluation:
	@echo "Starting test evaluation with list_test.csv..."
	docker run --rm \
    -v /home/sako/.ssh:/root/.ssh:ro \
    -v $(CURDIR)/predictions:/app/predictions \
    -v $(CURDIR)/logs:/app/logs \
    -v $(CURDIR)/models:/app/models \
    -v $(CURDIR)/script:/app/script \
    -v $(CURDIR)/plots:/app/plots \
    -v $(CURDIR)/SQL:/app/SQL \
    -v $(CURDIR)/tickers.json:/app/tickers.json:ro \
    -v $(CURDIR)/secrets:/app/secrets:ro \
    -v $(CURDIR)/list_test.csv:/app/list_test.csv:ro \
    $(IMAGE_NAME) python /app/script/bulk_evaluate.py --fresh --test-mode --source-file list_test.csv

# --- Testing ---

.PHONY: test test-unit test-integration

# Run all tests
test: init-db
	@echo "Running all tests..."
	$(DOCKER_RUN_TEST) $(IMAGE_NAME) python -m pytest

# Run only unit tests
test-unit:
	@echo "Running unit tests..."
	$(DOCKER_RUN_TEST) $(IMAGE_NAME) pytest tests/test_unit/

# Run only integration tests
# Run only integration tests
test-integration: init-db
	@echo "Running integration tests..."
	$(DOCKER_RUN_TEST) $(IMAGE_NAME) python -m pytest tests/test_integration/

# --- Misc ---

# Create or update the prediction_summary view
create-summary-view:
	@echo "Creating/updating the prediction_summary view..."
	$(DOCKER_RUN_BASE) $(IMAGE_NAME) python /app/script/run_sql_file.py SQL/create_summary_view.sql

# Run the full pipeline (update data and train both models)
all:
	@echo "Running the full pipeline (update and train) for ticker: $(TICKER)..."
	make update-data
	make train TICKER=$(TICKER) TEST=$(TEST) YEARS=$(YEARS)

# Enter the container for debugging
bash:
	@echo "Entering container shell..."
	$(DOCKER_RUN_BASE) -it $(IMAGE_NAME) bash

# Help message
help:
	@echo "Usage: make [target] [VARIABLE=value]"
	@echo ""
	@echo "Targets:"
	@echo "  build                Build the Docker image."
	@echo "  init-db              Initialize the database. Deletes all existing data."
	@echo "  update-data          Update stock and economic data without deleting existing data."
	@echo "  all                  Run the full pipeline (update data and train both models). Usage: make all TICKER=AAPL [YEARS=5]"
	@echo ""
	@echo "  --- Ticker Management ---"
	@echo "  add-ticker           Add/update a ticker and its features. Automatically fetches company info. Usage: make add-ticker TICKER=7203.T FEATURES='^N225,^TPX'"
	@echo "  remove-ticker        Remove a ticker. Usage: make remove-ticker TICKER=7203.T"
	@echo "  list-tickers         List all registered tickers."
	@echo "  update-info          Manually update a ticker's company info. Usage: make update-info TICKER=7203.T"
	@echo ""
	@echo "  --- Model Training & Prediction ---"
	@echo "  train                Train both UP and DOWN models. Usage: make train TICKER=AAPL [YEARS=5] [SEARCH_METHOD=optuna]"
	@echo "  predict              Predict both UP and DOWN trends. Usage: make predict TICKER=AAPL"
	@echo "  predict-all          Predict for all registered tickers."
	@echo ""
	@echo "  --- Model Diagnosis & Evaluation ---"
	@echo "  list-models          List models. If TICKER is set, lists for that ticker only. Usage: make list-models [TICKER=AAPL]"
	@echo "  evaluate-model       Evaluate a specific model. Usage: make evaluate-model TICKER=AAPL DIRECTION=up [VERSION=1]"
	@echo "  evaluate-all         Run bulk evaluation, resuming from the last run."
	@echo "  evaluate-all-fresh   Run bulk evaluation from scratch. Deletes prior results. If interrupted, it starts over."
	@echo ""
	@echo "  --- Testing ---"
	@echo "  test                 Run all tests (unit and integration)."
	@echo "  test-unit            Run only unit tests."
	@echo "  test-integration     Run only integration tests."
	@echo ""
	@echo "  --- Other Commands ---"
	@echo "  send-notifications   Send pending model and prediction notifications."
	@echo "  bash                 Enter the container shell for debugging."
	@echo "  help                 Show this help message."
	@echo ""
	@echo "Variables:"
	@echo "  TICKER               The ticker symbol to use (e.g., 7203.T)."
	@echo "  FEATURES             Comma-separated list of tickers to use as features."
	@echo "  YEARS                Number of recent years to use for training (default: 5)."
	@echo "  TEST                 Set to 'true' to run training in test mode (default: false)."
	@echo "  DIRECTION            The trend direction to use ('up' or 'down', for evaluate-model)."
	@echo "  VERSION              The model version to evaluate (optional, for evaluate-model)."
	@echo "  SEARCH_METHOD        Hyperparameter search method: 'grid', 'random', or 'optuna' (default: optuna)."
