"""Agent skill substrate — FSM recipe runner for in-session skill execution.

The runner enforces step boundaries via schema validation. It never calls an
LLM; the agent LLM in-session is the executor. Enforcement comes from the
emit/submit/validate handshake.

Dependency direction: agent_skills -> vocab (leaf import only).
"""
