import streamlit as st
import requests
import os
import re
import random
import subprocess
import time
import base64
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="SENTRY", layout="centered")

API_KEY = os.getenv("OPENROUTER_API_KEY")
WAZUH_URL = os.getenv("WAZUH_INDEXER_URL")
WAZUH_USER = os.getenv("WAZUH_INDEXER_USER")
WAZUH_PASS = os.getenv("WAZUH_INDEXER_PASS")
TARGET_IP = "192.168.56.102"


def get_base64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

bg_image = get_base64_image("docs/title.png")

# --- Theme + full-page background image + HUD-style button ---
st.markdown(f"""
<style>
.stApp {{
    background-image: url("data:image/png;base64,{bg_image}");
    background-size: cover;
    background-position: center top;
    background-repeat: no-repeat;
    background-attachment: fixed;
}}

.block-container {{
    margin-left: 40%;
    max-width: 55%;
}}

div[data-testid="stButton"],
div[data-testid="stButton"] > div,
.element-container:has(button) {{
    display: flex !important;
    justify-content: flex-start !important;
    width: 100% !important;
}}

.stButton {{
    width: 100% !important;
}}

h2, h3 {{ color: #c8ffd9 !important; text-align: center; }}
.stMarkdown, p, span, label {{ color: #d4f5e0; }}

.stButton > button {{
    position: relative;
    background: rgba(6, 9, 10, 0.75);
    border: 1px solid rgba(57, 255, 136, 0.35);
    color: rgba(93, 196, 142, 0.85);
    font-family: 'Courier New', monospace;
    font-weight: 700;
    letter-spacing: 3px;
    text-transform: uppercase;
    padding: 16px 28px;
    width: 100%;
    clip-path: polygon(22px 0, 100% 0, 100% calc(100% - 22px), calc(100% - 22px) 100%, 0 100%, 0 22px);
    transition: all 0.25s ease;
}}

.stButton > button::before,
.stButton > button::after {{
    content: '';
    position: absolute;
    width: 34px;
    height: 10px;
    background: repeating-linear-gradient(135deg, currentColor 0px, currentColor 2px, transparent 2px, transparent 5px);
    opacity: 0.6;
    pointer-events: none;
}}
.stButton > button::before {{ top: 0; left: 0; }}
.stButton > button::after {{ bottom: 0; right: 0; }}

.stButton > button:hover {{
    border-color: #39ff88;
    color: #39ff88;
    background: rgba(6, 9, 10, 0.9);
    text-shadow: 0 0 8px rgba(57, 255, 136, 0.8), 0 0 16px rgba(57, 255, 136, 0.5);
    filter: drop-shadow(0 0 10px rgba(57, 255, 136, 0.5));
}}

[data-testid="stChatMessage"] {{
    background-color: rgba(10, 16, 12, 0.9);
    border: 1px solid rgba(57, 255, 136, 0.2);
    border-radius: 4px;
}}

[data-baseweb="tab"] {{
    color: #d4f5e0 !important;
}}
[data-baseweb="tab"][aria-selected="true"] {{
    color: #39ff88 !important;
    border-bottom-color: #39ff88 !important;
}}

::-webkit-scrollbar {{ width: 8px; }}
::-webkit-scrollbar-track {{ background: #06090a; }}
::-webkit-scrollbar-thumb {{ background: #39ff88; border-radius: 4px; }}
</style>
""", unsafe_allow_html=True)

st.markdown("<div style='height: 420px;'></div>", unsafe_allow_html=True)


FALLBACK_MODELS = [
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
]

def ask_agent(system_prompt, chat_history):
    messages = [{"role": "system", "content": system_prompt}] + chat_history
    for model in FALLBACK_MODELS:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages},
            timeout=30
        )
        data = response.json()
        if "choices" in data:
            text = data["choices"][0]["message"]["content"].strip()
            text = re.sub(r"User Safety:.*?(Response Safety:\s*\w+)?", "", text, flags=re.IGNORECASE).strip()
            return text
    return "⚠️ All models are currently rate-limited. Please try again in a moment."


def ssh_attempt(username, password):
    """Runs one SSH login attempt. Returns True if it actually succeeded."""
    result = subprocess.run(
        ["sshpass", "-p", password, "ssh",
         "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
         f"{username}@{TARGET_IP}", "exit"],
        capture_output=True, timeout=10
    )
    return result.returncode == 0


def trigger_random_attack():
    scenario_type = random.choice([
        "false_positive", "false_positive",
        "failed_bruteforce", "failed_bruteforce", "failed_bruteforce",
        "successful_compromise"
    ])

    login_succeeded = False

    if scenario_type == "false_positive":
        ssh_attempt("debian", "wrongpass0")
    elif scenario_type == "failed_bruteforce":
        for i in range(5):
            ssh_attempt("debian", f"wrongpass{i}")
            time.sleep(0.5)
    elif scenario_type == "successful_compromise":
        for i in range(4):
            ssh_attempt("labuser", f"wrongpass{i}")
            time.sleep(0.5)
        login_succeeded = ssh_attempt("labuser", "labuser")  # real password confirmed earlier

    return scenario_type, login_succeeded


def fetch_latest_alert(since_timestamp):
    query = {
        "size": 10,
        "sort": [{"timestamp": "desc"}],
        "query": {
            "bool": {
                "must": [
                    {"term": {"agent.ip": TARGET_IP}},
                    {"match": {"rule.groups": "authentication_failed"}}
                ],
                "filter": [
                    {"range": {"timestamp": {"gte": since_timestamp}}}
                ]
            }
        }
    }
    response = requests.get(
        f"{WAZUH_URL}/wazuh-alerts-4.x-*/_search",
        auth=(WAZUH_USER, WAZUH_PASS),
        headers={"Content-Type": "application/json"},
        json=query,
        verify=False
    )
    result = response.json()
    hits = result.get("hits", {}).get("hits", [])
    if not hits:
        return None, 0
    return hits[0]["_source"], len(hits)


def build_scenario_from_alert(alert, failure_count, compromised):
    rule = alert.get("rule", {})
    data = alert.get("data", {})

    is_likely_false_positive = failure_count <= 1 and not compromised

    if compromised:
        client_context = (
            "You are an employee at the company. Your computer has been acting strange — "
            "programs you didn't open, files moved around, maybe your cursor jumped on its own. "
            "You're genuinely scared and think someone else might be in your account RIGHT NOW."
        )
        senior_context = (
            "This is a CONFIRMED COMPROMISE — the attacker successfully logged in after multiple "
            "failed attempts. You expect the analyst to treat this as urgent: immediate isolation of "
            "the host, forced password reset, and clear timeline of what happened before you consider "
            "this contained. Do not accept a casual or slow response."
        )
    elif is_likely_false_positive:
        client_context = (
            f"You noticed {failure_count} failed login attempt on your device — honestly you "
            "probably just fat-fingered your own password and aren't very worried. You're mildly "
            "annoyed IT is even asking about this, since it felt like nothing."
        )
        senior_context = "You expect the analyst to give you source IP, targeted account, failed attempt pattern, and a recommended containment step before you approve any action. If the pattern looks like a one-off (1 failed attempt, same source as the legitimate user), push the analyst to consider whether this is actually a false positive rather than escalating unnecessarily."
    else:
        client_context = (
            f"You are an employee at the company. You noticed {failure_count} failed login popups/attempts "
            "on your device in a short time and reported it to IT because it felt unusual and worrying."
        )
        senior_context = "You expect the analyst to give you source IP, targeted account, failed attempt pattern, and a recommended containment step before you approve any action."

    return {
        "wazuh_rule_id": rule.get("id", "unknown"),
        "wazuh_rule_description": rule.get("description", "unknown"),
        "agent_name": alert.get("agent", {}).get("name", "unknown"),
        "agent_ip": alert.get("agent", {}).get("ip", "unknown"),
        "source_ip": data.get("srcip", "unknown"),
        "target_username": data.get("dstuser", "unknown"),
        "severity_level": rule.get("level", "unknown"),
        "failure_count": failure_count,
        "is_likely_false_positive": is_likely_false_positive,
        "compromised": compromised,
        "client_context": client_context,
        "senior_context": senior_context,
    }


if "scenario" not in st.session_state:
    st.session_state.scenario = None

start_clicked = st.button("▶  START NEW SCENARIO", type="primary")

import datetime

if start_clicked:
    with st.spinner("Generating a live incident on the target server..."):
        attack_start_time = datetime.datetime.utcnow().isoformat() + "Z"
        scenario_type, confirmed_compromise = trigger_random_attack()
        time.sleep(5)
        alert, failure_count = fetch_latest_alert(attack_start_time)
    if alert is None:
        st.error("No alert was generated. Check that the target server is reachable and Wazuh is running.")
    else:
        st.session_state.scenario = build_scenario_from_alert(alert, failure_count, confirmed_compromise)
        st.session_state.senior_chat = []
        st.session_state.client_chat = []
        st.session_state.actions_taken = set()
        st.rerun()

if st.session_state.scenario is None:
    st.info("Click 'Start New Scenario' to generate a live incident.")
    st.stop()

scenario = st.session_state.scenario

st.subheader("🚨 Active Incident")
st.markdown("A new security alert has just come in. Investigate by speaking with the client and your senior analyst.")

st.divider()

senior_system_prompt = f"""You are a senior SOC analyst reviewing a junior analyst's work.
Scenario facts: {scenario['senior_context']}
Stay strictly in character. Reply in 1-3 short sentences. Be realistic and
experienced: you know non-technical clients can't read hostnames or find BIOS
screens, so you ask the analyst for information they CAN realistically get
rather than demanding technical details from the client directly. Push the
analyst to investigate using Wazuh/logs themselves. Only approve containment
actions once given enough reasonable detail. Never explain your reasoning or
break character."""

client_system_prompt = f"""You play an employee at the company. You are chatting
with your organization's SOC analyst through the official company IT support channel.

FIXED FACTS you must never contradict:
- Device: {scenario['agent_name']} ({scenario['agent_ip']}), a COMPANY-OWNED device
- Your account username is: {scenario['target_username']}
- You noticed {scenario['failure_count']} failed login attempt(s) related to this account

Your personality: {scenario['client_context']}

Rules:
- Reply in 1-2 short sentences, like a real chat message.
- Use everyday words only, zero technical jargon.
- Never contradict the FIXED FACTS above.
- When given a clear, reasonable instruction, follow it and report back, in character.
- Question instructions that are clearly harmful or nonsensical.
- Never give the analyst advice or instructions yourself. Never break character."""

if "senior_chat" not in st.session_state:
    st.session_state.senior_chat = []
if "client_chat" not in st.session_state:
    st.session_state.client_chat = []
if "actions_taken" not in st.session_state:
    st.session_state.actions_taken = set()

tab1, tab2 = st.tabs(["💬 Senior Analyst", "📞 Client"])

with tab1:
    for msg in st.session_state.senior_chat:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    senior_input = st.chat_input("Message the senior analyst...", key="senior_input")
    if senior_input:
        st.session_state.actions_taken.add("escalate_senior")
        st.session_state.senior_chat.append({"role": "user", "content": senior_input})
        reply = ask_agent(senior_system_prompt, st.session_state.senior_chat)
        st.session_state.senior_chat.append({"role": "assistant", "content": reply})
        st.rerun()

    st.divider()

    if st.button("🏁 Resolve Scenario", type="primary", key="resolve_btn"):
        if not st.session_state.senior_chat and not st.session_state.client_chat:
            st.error("You closed this incident without investigating or talking to anyone. That's not acceptable — a real analyst must gather facts before resolving.")
        else:
            if scenario.get('compromised'):
                fp_note = (
                    "This scenario is a CONFIRMED COMPROMISE — the attacker successfully logged in. "
                    "Treating this as low-urgency, delaying escalation, or not recommending immediate "
                    "isolation/password reset should score VERY POORLY. This is the most serious scenario type."
                )
            elif scenario.get('is_likely_false_positive'):
                fp_note = (
                    f"This scenario IS likely a false positive (only {scenario['failure_count']} failed attempt). "
                    "If it's a false positive, correctly identifying it as such (rather than over-escalating) should score WELL."
                )
            else:
                fp_note = (
                    f"This scenario is a genuine incident pattern ({scenario['failure_count']} failed attempts). "
                    "Failing to escalate or investigate properly should score POORLY."
                )

            judge_prompt = f"""You are a senior SOC analyst evaluating a junior analyst's
handling of this incident. Here is the real alert data:
Host: {scenario['agent_name']} ({scenario['agent_ip']})
Source IP: {scenario['source_ip']}
Target account: {scenario['target_username']}
Failed attempts: {scenario.get('failure_count', 'unknown')}

Conversation with the CLIENT (word-for-word, nothing else happened in this chat):
{chr(10).join(f"{m['role']}: {m['content']}" for m in st.session_state.client_chat) or "(EMPTY — no messages at all.)"}

Conversation with YOU, the senior (word-for-word, nothing else happened in this chat):
{chr(10).join(f"{m['role']}: {m['content']}" for m in st.session_state.senior_chat) or "(EMPTY — no messages at all.)"}

CRITICAL RULES for your evaluation:
- Only reference things that literally appear in the transcripts above. Do not invent, assume, or guess what the analyst might have meant.
- If a transcript is EMPTY or very short (like just "hi"), say so plainly and score accordingly low — do not fabricate a detailed critique of actions that never happened.
- If you quote or describe something the analyst did, it must be something actually present in the text above.

{fp_note}

Score the analyst's handling on a scale of 1 to 10 based on: symptoms gathered
from the client, accurate technical facts reported to you, correct judgment on
whether this is a real incident or noise, and (if real) a sensible containment
step proposed. Respond in this exact format:
SCORE: <number out of 10>
VERDICT: <2-4 sentence verdict in your voice as the senior analyst, grounded only in what actually happened>"""

            with st.spinner("Senior is reviewing your handling of this incident..."):
                result = ask_agent(judge_prompt, [{"role": "user", "content": "Please evaluate my handling of this incident now."}])

            score_match = re.search(r"SCORE:\s*(\d+)", result)
            verdict_match = re.search(r"VERDICT:\s*(.+)", result, re.DOTALL)
            score = score_match.group(1) if score_match else "N/A"
            verdict = verdict_match.group(1).strip() if verdict_match else result

            st.subheader(f"📊 Score: {score}/10")
            st.markdown(f"**Senior's verdict:** {verdict}")

with tab2:
    for msg in st.session_state.client_chat:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    client_input = st.chat_input("Message the client...", key="client_input")
    if client_input:
        st.session_state.actions_taken.add("notify_client")
        st.session_state.client_chat.append({"role": "user", "content": client_input})
        reply = ask_agent(client_system_prompt, st.session_state.client_chat)
        st.session_state.client_chat.append({"role": "assistant", "content": reply})
        st.rerun()
