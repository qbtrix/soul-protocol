# Human Evaluation UI

A FastAPI web app for running blinded A/B evaluations of soul-enabled vs baseline AI agents.

## Setup

1. Make sure you're in the `soul-protocol` project root with dependencies installed:

```bash
cd soul-protocol
uv pip install fastapi jinja2 uvicorn
```

2. Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

3. Set an admin token for viewing results:

```bash
export EVAL_ADMIN_TOKEN="your-secret-token-here"
```

## Running

```bash
cd soul-protocol
uvicorn research.eval_ui.app:app --reload --port 8080
```

Then open http://localhost:8080 in your browser.

## How It Works

Each student session:

1. A soul is birthed with a random OCEAN personality preset (from 5 options)
2. Agent order is randomized — the student doesn't know which is soul-enabled
3. Student chats 5 turns with Agent A, then fills a 5-question Likert survey
4. Student chats 5 turns with Agent B, then fills the same survey
5. Student picks their overall preference (A or B)
6. Session data is saved to `research/results/human_eval/`

## Viewing Results

Visit the admin endpoint with your configured token:

```
http://localhost:8080/api/results?token=your-secret-token-here
```

## File Structure

```
research/eval_ui/
    __init__.py
    app.py              # FastAPI backend
    README.md           # This file
    templates/
        index.html      # Landing page
        chat.html       # Chat + survey interface
```

Results are saved to `research/results/human_eval/*.json`.
