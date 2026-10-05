import os
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()
client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])

r = client.chat.completions(
    model="sarvam-105b",
    messages=[{"role": "user", "content": "Ek line mein batao: IndiaMART kya hai?"}],
)
print(r.choices[0].message.content)
