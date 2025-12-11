apiVersion: v1
kind: Workflow
metadata:
  name: simple-forked-flows
  description: Simple forked flows demo with sleep instead of agents

spec:
  # Demonstrates two independent flows that run concurrently
  # Flow A: Completes in 10 seconds
  # Flow B: Completes in 30 seconds

  nodes:
    - name: start
      type: script
      script: echo '{"message":"Starting forked flows demo","timestamp":"'$(date +%s)'"}'

    # Flow A nodes - Fast 10-second path
    - name: flow_a_process
      type: script
      script: python3 /Users/sky/git/ago/cookbook/workflows/scripts/sleep_and_report.py 10 "Flow A"

    - name: flow_a_done
      type: script
      script: echo '{"flow":"A","status":"completed","duration":"10s"}'

    # Flow B nodes - Slow 30-second path
    - name: flow_b_process
      type: script
      script: python3 /Users/sky/git/ago/cookbook/workflows/scripts/sleep_and_report.py 30 "Flow B"

    - name: flow_b_done
      type: script
      script: echo '{"flow":"B","status":"completed","duration":"30s"}'

  # Fork into two independent flows that run concurrently
  flow: |
    start >> [flow_a_process, flow_b_process]
    flow_a_process >> flow_a_done
    flow_b_process >> flow_b_done
