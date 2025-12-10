apiVersion: v1
kind: Workflow
metadata:
  name: simple-example
  description: Simple 3-step linear workflow

spec:
  nodes:
    - name: get_input
      type: script
      script: python3 cookbook/workflows/scripts/step1_input.py
      outputs:
        user_input: result

    - name: process
      type: agent
      template: simple-assistant
      prompt: "Analyze this input and provide a detailed response: {{get_input.result}}"
      outputs:
        analysis_result: content

    - name: validate
      type: script
      script: python3 cookbook/workflows/scripts/step3_validate.py
      inputs:
        content: process.content
