# PDF OCR with Claude

A Streamlit web application for bulk PDF OCR processing using Claude Sonnet API.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install system dependencies for PDF processing:
- macOS: `brew install poppler`
- Ubuntu/Debian: `sudo apt-get install poppler-utils`

3. Create `.env` file:
```bash
cp .env.example .env
```

4. Update `.env` with your credentials:
- `AUTH_EMAIL`: Login email
- `AUTH_PASSWORD`: Login password
- `ANTHROPIC_API_KEY`: Your Claude API key

## Running Locally

```bash
streamlit run app.py
```

## Deployment Options

### Streamlit Cloud (Recommended)
1. Push to GitHub
2. Go to share.streamlit.io
3. Deploy from your repository
4. Add secrets in Streamlit Cloud settings

### Other Options
- Heroku
- Google Cloud Run
- AWS App Runner
- Render.com

## Features
- Simple email/password authentication
- Bulk PDF upload (up to 5 files)
- OCR using Claude Sonnet API
- Table view of extracted data
- CSV export functionality
- Full text preview