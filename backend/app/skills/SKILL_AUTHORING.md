# Skill Authoring Guide

## Structure

Each skill is a directory containing:

```
my_skill/
├── manifest.json    # Required: skill metadata
├── main.py          # Required: entrypoint script
└── ...              # Optional: any other files
```

## manifest.json

```json
{
  "name": "my_skill",
  "description": "What this skill does — shown to the AI agent",
  "version": "1.0.0",
  "author": "your-name",
  "entrypoint": "main.py",
  "language": "python",
  "dependencies": ["requests", "pandas"],
  "params": [
    {
      "name": "input_text",
      "type": "string",
      "description": "The text to process",
      "required": true
    },
    {
      "name": "max_results",
      "type": "integer",
      "description": "Maximum results to return",
      "required": false,
      "default": 10
    }
  ],
  "tags": ["text", "analysis"],
  "timeout_seconds": 120
}
```

## Environment Variables

Your script receives these environment variables:

| Variable | Description |
|----------|-------------|
| `PARVA_PARAMS` | JSON string of parameters passed by the agent |
| `PARVA_WORKSPACE` | Path to the persistent user workspace (`/workspace`) |
| `PARVA_EXECUTION_ID` | Unique ID for this execution |
| `PARVA_FILES_DIR` | Path to uploaded files (`/workspace/files`) |
| `MINIO_ENDPOINT` | MinIO endpoint for direct file access |
| `MINIO_ACCESS_KEY` | MinIO access key |
| `MINIO_SECRET_KEY` | MinIO secret key |
| `MINIO_BUCKET` | MinIO bucket name |
| `REDIS_URL` | Redis URL for publishing progress updates |
| `USER_ID` | The user ID |

## Output Protocol

Your script should print a **JSON object as the last line of stdout**. This is what the agent receives as the result.

```python
import json, os

params = json.loads(os.environ.get("PARVA_PARAMS", "{}"))
# ... do work ...
print(json.dumps({"result": "your output here"}))
```

## Progress Updates (Optional)

For long-running skills, publish progress to Redis:

```python
import json, os, redis

r = redis.from_url(os.environ["REDIS_URL"])
user_id = os.environ["USER_ID"]
exec_id = os.environ["PARVA_EXECUTION_ID"]

r.publish(f"parva:exec:{exec_id}:progress", json.dumps({
    "type": "execution_progress",
    "data": {
        "execution_id": exec_id,
        "status": "running",
        "progress_pct": 50,
        "current_step": "Processing data..."
    }
}))
```

## Persistent State

- The `/workspace` directory persists across executions for the same user.
- Installed pip dependencies persist in the container.
- Store any state files in `/workspace/` for later use.

## Importing Skills

Skills can be imported from:
- Git repositories (must contain `manifest.json`)
- Tarball URLs (`.tar.gz`)

Via the UI or API:
```bash
curl -X POST http://localhost:8000/api/skills/import \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/user/my-skill.git"}'
```
