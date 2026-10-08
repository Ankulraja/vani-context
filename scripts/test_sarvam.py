import os
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()
client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])

r = client.chat.completions(
    model="sarvam-105b",
    messages=[{"role": "user", "content": "Tell me a joke about Delhi traffic"}],
    reasoning_effort=None,  # explicit None = thinking OFF; otherwise all tokens go to reasoning and content is empty
    max_tokens=400,
)
print(r.choices[0].message.content)
