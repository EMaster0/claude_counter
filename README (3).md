# Claude Usage Counter

A lightweight webhook that sits between Make and Claude API to track token usage and estimated cost.

```
Make → this webhook → Claude API
              ↓
         usage counter
```

## Deploy to Railway

1. Fork this repo
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add environment variable: `ANTHROPIC_API_KEY = your_key_here`
4. Generate a public domain under Settings → Networking

## Use in Make

Replace your Claude HTTP module with:

- **POST** `https://your-app.railway.app/webhook`
- Body:
  ```json
  {
    "prompt": "your prompt",
    "feature_tag": "chat",
    "model": "claude-sonnet-4-5",
    "max_tokens": 1024
  }
  ```
- Claude's reply is in the `content` field of the response

## Check Usage

Open `https://your-app.railway.app/summary` in your browser.

> Records reset on Railway restart. Good enough for short-term monitoring.
