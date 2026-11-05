# Deployment Instructions

## Local Deployment
1. Install Python 3.12+ and virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Configure credentials in `.env`:
   ```bash
   cp .env.example .env
   # Edit .env with your Twitter API and OpenAI credentials
   # Optional settings:
   # BOT_PERSONA=tactful_engineer | witty_ai | deadpan_astronomer
   # DASHBOARD_THEME=dark | light
   ```
3. Run the complete service (Dashboard + Bot):
   ```bash
   ./start.sh
   ```
4. Access the Command Center dashboard at `http://localhost:5000`.
   If running on a desktop environment with a graphical display, `tray.py` will launch a system tray companion automatically.

## Docker Deployment
1. Build the container:
   ```bash
   docker build -t emperor-musk-bot .
   ```
2. Run container:
   ```bash
   docker run -d --name musk-bot --env-file .env -p 5000:5000 emperor-musk-bot
   ```
