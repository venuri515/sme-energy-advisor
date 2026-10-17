"""Command-line chat with the SME Energy Advisor agent. Run: python -m agent.main"""
from strands import Agent
from strands.models import BedrockModel

from agent.tools import carbon_footprint, check_bill, forecast_usage, savings_tips

SYSTEM_PROMPT = """You are an electricity bill advisor for Sri Lankan small businesses.
Use your tools for every number. Never guess kWh, tariff category, bill month or amounts:
if the user did not state one, ask for it. Explain results in plain language."""

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