apiVersion: v1
kind: Workflow
metadata:
  name: parallel-with-merge-node
  description: Parallel workflow using MergeNode instead of script

spec:
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

    # Merge results using MergeNode
    - name: combine
      type: merge
      strategy: dict  # Options: dict, list, concat
      inputs:
        sentiment: sentiment.content
        summary: summary.content
        keywords: keywords.content
        original_text: collect_input.text
      outputs:
        final_report: combined

  # Define flow: linear >> parallel >> merge
  flow: |
    collect_input >> [sentiment, summary, keywords]
    [sentiment, summary, keywords] >> combine
