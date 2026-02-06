"""Create data visualizations."""

import base64
import io
import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

params = json.loads(os.environ.get("PARVA_PARAMS", "{}"))
chart_type = params.get("chart_type", "bar")
data = params.get("data", {})
title = params.get("title", "Chart")
xlabel = params.get("xlabel", "")
ylabel = params.get("ylabel", "")
csv_filename = params.get("filename")

# If a CSV file is specified, load it
if csv_filename:
    import pandas as pd
    files_dir = Path(os.environ.get("PARVA_FILES_DIR", "/workspace/files"))
    csv_path = files_dir / csv_filename
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        cols = df.columns.tolist()
        if len(cols) >= 2:
            data = {"labels": df[cols[0]].tolist(), "values": df[cols[1]].tolist()}
        elif len(cols) == 1:
            data = {"values": df[cols[0]].tolist()}

fig, ax = plt.subplots(figsize=(10, 6))

try:
    if chart_type == "bar":
        labels = data.get("labels", list(range(len(data.get("values", [])))))
        values = data.get("values", [])
        ax.bar(labels, values)
    elif chart_type == "line":
        x = data.get("x", data.get("labels", list(range(len(data.get("y", data.get("values", [])))))))
        y = data.get("y", data.get("values", []))
        ax.plot(x, y, marker="o")
    elif chart_type == "scatter":
        ax.scatter(data.get("x", []), data.get("y", []))
    elif chart_type == "pie":
        labels = data.get("labels", [])
        values = data.get("values", [])
        ax.pie(values, labels=labels, autopct="%1.1f%%")
    elif chart_type == "histogram":
        values = data.get("values", [])
        bins = data.get("bins", 20)
        ax.hist(values, bins=bins)

    ax.set_title(title)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    plt.tight_layout()

    # Save to workspace
    workspace = Path(os.environ.get("PARVA_WORKSPACE", "/workspace"))
    output_path = workspace / "files" / f"chart_{os.environ.get('PARVA_EXECUTION_ID', 'out')[:8]}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")

    # Also encode as base64 for inline display
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()

    result = {
        "chart_type": chart_type,
        "image_base64": b64,
        "saved_to": str(output_path),
    }
except Exception as e:
    result = {"error": str(e)}
finally:
    plt.close(fig)

print(json.dumps(result, default=str))
