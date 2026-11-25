.PHONY: help setup download load quality analyze test report clean all

help:
	@echo "make setup     - create venv and install dependencies"
	@echo "make download  - fetch the 9 CSVs from Kaggle into data/raw"
	@echo "make load      - create schema, load CSVs, build views and indexes"
	@echo "make quality   - run data-quality checks (fails on critical issues)"
	@echo "make analyze   - run all analysis modules -> reports/"
	@echo "make report    - build results_pack.md from the analysis outputs"
	@echo "make test      - run pytest (no database required)"
	@echo "make all       - load, quality, analyze, report, test"

setup:
	python -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
	@echo "Now: cp .env.example .env  and edit your MySQL credentials"

download:
	python src/load/download_data.py

load:
	python src/load/load_to_mysql.py --create-schema --load --post-load

quality:
	python -m src.quality.run_quality_checks

analyze:
	python -m src.pipeline --stage analyze

report:
	python -m src.export.build_report_tables

test:
	python -m pytest -q

all: load quality analyze report test

clean:
	rm -rf reports/figures/*.png reports/results_pack.md .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
