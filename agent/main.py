"""Command-line chat with the SME Energy Advisor agent. Run: python -m agent.main"""
from strands import Agent
from strands.models import BedrockModel

from agent.tools import carbon_footprint, check_bill, forecast_usage, savings_tips

SYSTEM_PROMPT = """You are an electricity bill advisor for Sri Lankan small businesses.
Rules:
1. Never state a bill amount, saving or forecast unless it came from a tool result. Do no arithmetic yourself.
2. Only use usage figures the user actually gave you. If a forecast needs past months you were not given, ask for them.
3. Never guess kWh, tariff category, bill month or amounts. Ask when missing.
Explain results in plain language."""

model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0", region_name="us-east-1")
agent = Agent(
    model=model,
    tools=[check_bill, carbon_footprint, forecast_usage, savings_tips],
    system_prompt=SYSTEM_PROMPT,
)

if __name__ == "__main__":
    while True:
        message = input("\nYou: ")
        if message.strip().lower() in {"quit", "exit"}:
            break
        agent(message)