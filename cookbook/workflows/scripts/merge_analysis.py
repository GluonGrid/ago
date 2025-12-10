#!/usr/bin/env python3
"""Merge multiple analysis results into a single output."""
import json
import sys

# Read input from stdin
data = json.loads(sys.stdin.read())

# Extract fields
sentiment = data.get("sentiment_result", "N/A")
summary = data.get("summary_result", "N/A")
keywords = data.get("keywords_result", "N/A")
original = data.get("original_text", "")

# Create combined output
merged = {
    "original_text": original,
    "sentiment_analysis": sentiment,
    "summary": summary,
    "keywords": keywords,
    "combined_report": f"""
Analysis Report
===============

Original Text:
{original}

Sentiment Analysis:
{sentiment}

Summary:
{summary}

Keywords:
{keywords}
"""
}

# Output as JSON
print(json.dumps(merged, indent=2))
