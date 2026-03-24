# Community Feedback Insights Hub

This is a separate survey-insights mini-project built from the workbook at:

`/home/gondamol/sentiment-analysis-projects/Survey_04_04_2023, 23_09_23.xlsx`

It turns the raw survey export into:

- a normalized analysis dataset
- a Vercel-friendly static web app
- a donor-ready PDF brief

## Project Structure

- `scripts/build_survey_insights.py`: parses the XLSX workbook without `openpyxl`, normalizes fields, scores sentiment, tags themes, and writes processed assets
- `scripts/generate_usaid_report.py`: builds the PDF brief from the processed analysis
- `data/processed/`: archival JSON and CSV outputs
- `app/`: static site for Vercel deployment
- `reports/`: generated PDF brief

## Rebuild Data

From the repo root:

```bash
python3 survey_insights/scripts/build_survey_insights.py
python3 survey_insights/scripts/generate_usaid_report.py
```

If the workbook moves, pass a custom input path:

```bash
python3 survey_insights/scripts/build_survey_insights.py --input "/path/to/workbook.xlsx"
```

## Preview Locally

```bash
cd survey_insights/app
python3 -m http.server 4173
```

Then open `http://localhost:4173`.

## Deploy To Vercel

The app is fully static, so you can deploy it from the `survey_insights/app` directory:

```bash
cd survey_insights/app
vercel --prod
```

If you prefer the Vercel web dashboard, set the project root to `survey_insights/app`.

## Outputs

- App entry point: `survey_insights/app/index.html`
- Processed CSV: `survey_insights/app/assets/records.csv`
- PDF brief: `survey_insights/reports/usaid-community-feedback-report.pdf`
