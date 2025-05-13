def build_prompt(question, telemetry):
    return f"""
You are an expert UAV systems analyst. Analyze the following telemetry data and answer the user’s question. Be concise and accurate. If useful, point out anomalies or suggest further investigation.

Telemetry Snapshot (JSON):
{telemetry}

User Question:
{question}
"""
