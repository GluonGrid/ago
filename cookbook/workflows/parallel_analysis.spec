apiVersion: v1
kind: Workflow
metadata:
  name: parallel-analysis
  description: Parallel agent analysis with dotted notation field mapping

spec:
  # Define nodes
  nodes:
    - name: collect_input
      type: interactive
      prompt: "Enter text to analyze"
      fields:
        - name: text
          label: "Text to analyze"
          default: "AI and machine learning are transforming technology."

    # Three agents analyze in parallel
    - name: sentiment
      type: agent
      template: simple-assistant
      prompt: "Analyze the sentiment of this text: {{collect_input.text}}"

    - name: summary
      type: agent
      template: simple-assistant
      prompt: "Provide a brief summary of: {{collect_input.text}}"

    - name: keywords
      type: agent
      template: simple-assistant
      prompt: "Extract key topics from: {{collect_input.text}}"

    # Merge results
    - name: combine
      type: script
      script: python3 cookbook/workflows/scripts/merge_analysis.py
      inputs:
        sentiment_result: sentiment.content
        summary_result: summary.content
        keywords_result: keywords.content
        original_text: collect_input.text

  # Define flow: linear >> parallel >> merge
  flow: |
    collect_input >> [sentiment, summary, keywords]
    [sentiment, summary, keywords] >> combine
