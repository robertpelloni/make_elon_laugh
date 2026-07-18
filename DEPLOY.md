# Deployment Instructions

1.  **Prerequisites:** Python 3.8+ installed on the host machine.
2.  **Install Dependencies:** Run `pip install tweepy` (or `pip install -r requirements.txt` once added).
3.  **API Keys:** Edit `bot.py` (or set environment variables in the future) to include your actual X API Bearer Token, API Key, API Secret, Access Token, and Access Token Secret. Ensure the app has "Read and Write" permissions.
4.  **Dry Run Test:** Execute `python3 bot.py --dry-run` to verify the logic without posting.
5.  **Run as Service:** To keep the bot running permanently, use a tool like `tmux`, `screen`, or set it up as a `systemd` service:
    ```bash
    nohup python3 bot.py > bot_output.log 2>&1 &
    ```
