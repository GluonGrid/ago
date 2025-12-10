apiVersion: v1
kind: Workflow
metadata:
  name: interactive-example
  description: Interactive workflow with field mapping

spec:
  nodes:
    - name: get_user_input
      type: interactive
      prompt: "Please provide information for analysis"
      fields:
        - name: name
          label: "Your name"
          default: "Alice"
        - name: topic
          label: "Topic to analyze"
          default: "AI and Machine Learning"
      outputs:
        user_name: name
        user_topic: topic

    - name: process
      type: agent
      template: simple-assistant
      prompt: "Analyze this topic for {{get_user_input.name}}: {{get_user_input.topic}}"
      outputs:
        analysis: content

    - name: validate
      type: script
      script: python3 cookbook/workflows/scripts/step3_validate.py
      inputs:
        content: process.content
