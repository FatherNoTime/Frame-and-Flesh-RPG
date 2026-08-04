import re
import json
import os
import time
import random
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & MOBILE-FRIENDLY CSS / JS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="FRAME & FLESH", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #0a0b0d; color: #c5c9d1; font-family: 'Courier New', Courier, monospace; }
    
    [data-testid="stHeader"], footer, [data-testid="stToolbar"], [data-testid="stSidebar"] {
        display: none !important;
    }
    
    .st-key-fixed_hud_container {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100% !important;
        z-index: 99999 !important;
        background-color: #12151a !important;
        border-bottom: 1px solid #2a323d !important;
        padding: 6px 12px !important;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.9);
        box-sizing: border-box;
    }
    
    .st-key-fixed_hud_container button {
        background-color: #1a1f29 !important;
        color: #00ffcc !important;
        border: 1px solid #2a323d !important;
        font-family: 'Courier New', Courier, monospace !important;
        font-size: 0.65rem !important;
        padding: 2px 6px !important;
        margin-top: 2px !important;
        width: 100% !important;
    }
    
    .block-container {
        padding-top: 95px !important;
        padding-bottom: 110px !important;
    }
    
    [data-testid="stChatInputContainer"] {
        position: fixed !important;
        bottom: 15px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        width: 92% !important;
        max-width: 750px !important;
        z-index: 99998 !important;
        background-color: #12151a !important;
        border-radius: 8px !important;
        box-shadow: 0px -4px 15px rgba(0,0,0,0.8);
    }
    
    .hp-text { color: #00ffcc; font-weight: bold; }
    .strain-text { color: #ff3366; font-weight: bold; }
    .stat-val { color: #f0a020; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

components.html("""
    <script>
    function scrollToTopOFLastMessage() {
        const messages = window.parent.document.querySelectorAll('[data-testid="stChatMessage"]');
        if (messages.length > 0) {
            const lastMessage = messages[messages.length - 1];
            const elementPosition = lastMessage.getBoundingClientRect().top + window.parent.pageYOffset;
            window.parent.scrollTo({
                top: elementPosition - 105,
                behavior: 'smooth'
            });
        }
    }

    window.parent.addEventListener("DOMContentLoaded", () => {
        setTimeout(scrollToTopOFLastMessage, 150);
        setTimeout(scrollToTopOFLastMessage, 450);
    });
    setTimeout(scrollToTopOFLastMessage, 200);
    </script>
""", height=0)
      

# -----------------------------------------------------------------------------
# 2. STATE INITIALIZATION & GHOST TRACKER
# -----------------------------------------------------------------------------
if "game" not in st.session_state:
    st.session_state.game = {
        "hull_hp": 100,
        "bio_strain": 0,
        "campaign_depth": 1,
        "stats": {
            "force": 65,
            "reflex": 60,
            "scan": 55,
            "stability": 70
        },
        "loadout": {
            "left_arm": "Standard Manipulator",
            "right_arm": "Heavy Welder Tool",
            "legs": "Bipedal Industrial Struts",
            "head": "Basic Optic Cluster"
        },
        "inventory": "2x Bio-Sutures, 1x Emergency Coolant Injector, Field Engineer Toolkit, 0x Raw Scrap",
        "hostile_schematics": "No enemy units scanned yet.",
        "timeline": "* Arrived at Sub-level 3 Docking Bay under Command's evacuation protocol.",
        "lore_notes": "* Command claimed all personnel evacuated safely before the grid blackout.",
        "history": [],
    }

if "api_key" not in st.session_state:
    st.session_state.api_key = st.secrets.get("GEMINI_API_KEY", "")

# -----------------------------------------------------------------------------
# 3. THE LOREBOOK ENGINE
# -----------------------------------------------------------------------------
LOREBOOK = {
    "erebus": "Black-Site Erebus: Subterranean military research facility. Command claimed all staff evacuated prior to the blackout.",
    "splicer": "Mark-1 Splicer Frame: Your mech. Field-engineering variant. Modular slots: L-Arm, R-Arm, Legs, Head.",
    "neural loom": "Neural Loom: The spinal harness connecting your nervous system to the mech. Splicing incompatible/organic parts causes severe psychological shock.",
    "command": "Command: The military brass that deployed you. They asserted a clean, total evacuation.",
    "scanner": "High-Fidelity Blueprint Scanner: Penetrates chassis plating to reveal internal mechanics, weak points, and biological signatures."
}

def get_lore(text):
    found_lore = []
    text_lower = text.lower()
    for key, desc in LOREBOOK.items():
        if re.search(rf"\b{re.escape(key)}\b", text_lower):
            found_lore.append(desc)
            
    if found_lore:
        return "\n[SYSTEM INJECTED LORE CONTEXT]:\n" + "\n".join(found_lore)
    return ""

# -----------------------------------------------------------------------------
# 4. UNIFIED FIXED TOP HUD & EMBEDDED MENU CONTAINER
# -----------------------------------------------------------------------------
with st.container(key="fixed_hud_container"):
    col_hud, col_btn = st.columns([3.8, 1.0])
    
    with col_hud:
        st.markdown(f"""
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.68rem;">
                <span style="color: #667080; letter-spacing: 0.5px;">OP STATUS // SUBJ 09 // DEPTH {st.session_state.game['campaign_depth']}</span>
                <span>HULL: <span class="hp-text">{st.session_state.game['hull_hp']}/100</span> | STRAIN: <span class="strain-text">{st.session_state.game['bio_strain']}%</span></span>
            </div>
            <div style="font-size: 0.65rem; color: #8892b0; margin-top: 2px; word-break: break-word;">INV: {st.session_state.game['inventory']}</div>
        """, unsafe_allow_html=True)
        
    with col_btn:
        with st.popover("⚙️ SYS_MENU", use_container_width=True):
            st.title("SYS_CONFIG")
            
            with st.form("api_key_form"):
                api_input = st.text_input("Gemini API Key", type="password", value=st.session_state.api_key)
                if st.form_submit_button("Save Key"):
                    st.session_state.api_key = api_input
                    st.success("Key Saved")
            
            st.markdown("---")
            st.subheader("FRAME SCHEMATICS")
            
            with st.expander("📊 Frame Character Sheet", expanded=False):
                st.markdown(f"""
                **VITALS**
                * **HULL HP:** <span class="hp-text">{st.session_state.game['hull_hp']} / 100</span>
                * **BIO-STRAIN:** <span class="strain-text">{st.session_state.game['bio_strain']}%</span>
                
                <hr style="margin: 0.8em 0; border-color: #2a323d;">
                
                **CORE STATS**
                * **FORCE:** <span class="stat-val">{st.session_state.game['stats']['force']}</span> *(Lift, Throw, Melee, Break)*
                * **REFLEX:** <span class="stat-val">{st.session_state.game['stats']['reflex']}</span> *(Aim, Shoot, Dodge, React)*
                * **SCAN:** <span class="stat-val">{st.session_state.game['stats']['scan']}</span> *(Awareness, Search, Analyze)*
                * **STABILITY:** <span class="stat-val">{st.session_state.game['stats']['stability']}</span> *(Balance, Resist Recoil, Brace)*
                """, unsafe_allow_html=True)
            
            with st.expander("🛠️ Loadout Slots", expanded=False):
                st.markdown(f"""
                - **Head:** {st.session_state.game['loadout']['head']}
                - **L-Arm:** {st.session_state.game['loadout']['left_arm']}
                - **R-Arm:** {st.session_state.game['loadout']['right_arm']}
                - **Legs:** {st.session_state.game['loadout']['legs']}
                """)
            
            st.markdown("---")
            st.subheader("FIELD LOGS")
            
            with st.expander("⚙️ Hostile Schematics", expanded=False):
                st.markdown(st.session_state.game.get("hostile_schematics", "No units cataloged."))
                
            with st.expander("⏳ Timeline Summary", expanded=False):
                st.markdown(st.session_state.game.get("timeline", "No events recorded."))
                
            with st.expander("📝 Lore Notes & Secrets", expanded=False):
                st.markdown(st.session_state.game.get("lore_notes", "No notes recorded."))

            st.markdown("---")
            with st.expander("💾 Save / Load Manager", expanded=False):
                safe_game_data = st.session_state.game.copy()
                save_json = json.dumps(safe_game_data, indent=4)
                st.download_button("Export Save", data=save_json, file_name="frame_and_flesh_save.json", mime="application/json")
                
                uploaded_save = st.file_uploader("Import Save", type=["json"])
                if uploaded_save is not None:
                    try:
                        loaded_data = json.load(uploaded_save)
                        st.session_state.game = loaded_data
                        st.success("Save loaded successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Invalid save file: {e}")

# -----------------------------------------------------------------------------
# 5. SYSTEM INSTRUCTIONS (The GM Persona & Pacing)
# -----------------------------------------------------------------------------
SYS_INSTRUCT = """You are a Strict, immersive GM for a grimdark sci-fi/body-horror TTRPG titled 'FRAME & FLESH'.
The Player is a military field engineer injured in battle, piloting a repurposed Splicer Frame.

CORE NARRATIVE PILLARS (SPACE THESE OUT - MAKE THEM RARE AND SPECIAL. DO NOT USE IN EVERY SCENE):
1. THE CARETAKER AI: The facility's AI is NOT integrated into the player's system and is NEVER actually trying to help. Initially, it acts like it's helping but subtly impedes the player (especially around boss areas). Once the player discovers human experiments, it begins to rationalize them. As the player nears the final boss, it adopts a completely hostile tone.
2. NEURAL BLEED & HUMAN FOOTPRINT: Only occasionally inject phantom memories or tie loot to intimate human artifacts. These should feel special, not constant.
3. FACTIONS OF THE LEFT BEHIND: Rarely introduce remnants of surviving staff who distrust Splicer Frames.

STRICT CAMPAIGN PACING & SCALING:
- Run 3 to 5 tactical, multi-turn enemy encounters before Boss 1.
- BOSSES 1-3 (PURE MECHANICAL): Autonomous industrial mechs. The facility appears abandoned as Command claimed.
- POST-BOSS 3 (BIO-HYBRID REVELATION): Introduce rare bio-mechs integrated with human limbs and nervous tissue. 

MECH STATS & d100 CHECK SYSTEM (MANDATORY):
The player's frame has 4 core stats: FORCE, REFLEX, SCAN, STABILITY.
When the player attempts a risky action requiring a roll, output the Check Tag AND STOP YOUR RESPONSE immediately. The system will roll the dice and prompt you to write the consequence.
Format Example: [CHECK: stat=force, base=65, mod=10, reason="Forcing open a sealed blast door"]

AUTOMATED CAMPAIGN LOGGING (STRICT CONDITIONS APPLY):
At the end of your response, output tags ONLY if their specific condition is met:
- [STATE_UPDATE: HP=85, STRAIN=15, INV=...] -> ALWAYS output this to maintain inventory and HP.
- [COMBAT_STATUS: Loader Drone | Hull: 45/50 | Range: Out of melee] -> ONLY output if currently in active combat.
- [THREAT_LOG: Enemy Name | Prime: FORCE(60) | Loot: L-Arm Heavy Welder] -> ONLY output for NEW, previously un-scanned enemy types. EVERY enemy must have at least one specific salvageable frame part (e.g., L-Arm, R-Arm, Legs, Head), not just raw scrap.
- [TIMELINE_LOG: Defeated the Sub-level Boss] -> ONLY output for MAJOR plot advancements (boss encounters, entering new levels). Do NOT log standard turns, scans, or generic combat actions.
- [LORE_LOG: Discovered human bio-matter in the fuel line] -> ONLY output for MAJOR narrative reveals. Do NOT log minor phantom memories or basic AI dialogue."""

# -----------------------------------------------------------------------------
# 6. MAIN CHAT INTERFACE
# -----------------------------------------------------------------------------
if not st.session_state.game["history"]:
    kickoff = "I am ready to begin. Establish the scene."
    st.session_state.game["history"].append({"role": "user", "content": kickoff, "display": False})
    
    initial_gm = (
        "**[SYSTEM INITIALIZATION... ONLINE]**\n\n"
        "**SUBJECT DOSSIER & PHYSICAL SITUATION:**\n"
        "* **Role:** Military Field Engineer.\n"
        "* **Physical Status:** Recovering from critical battlefield trauma. Synthetic neural-loom interface directly knitting your nervous system into a heavy-duty Splicer Frame.\n"
        "* **Current Location:** Sealed inside the airlock of the Sub-level 3 Docking Bay.\n\n"
        "---\n\n"
        "The airlock hisses shut. Emergency red strobes cut through the gloom of Sub-level 3. Fifty feet down the gantry, a four-legged industrial loader drone pauses its work. A bright blue welding torch flickers at the end of its primary manipulator arm. It slowly pivots its optic cluster toward you.\n\n"
        "What do you do, Engineer?"
    )
    st.session_state.game["history"].append({"role": "model", "content": initial_gm, "display": True})

for msg in st.session_state.game["history"]:
    if msg.get("display", True):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# -----------------------------------------------------------------------------
# 7. INPUT HANDLING & API CALLS
# -----------------------------------------------------------------------------
def call_gemini(messages):
    client = genai.Client(api_key=st.session_state.api_key)
    model_chain = ["gemini-3.1-pro", "gemini-3.6-flash", "gemini-3.5-flash"]
    for model_name in model_chain:
        success = False
        for attempt in range(2):
            try:
                resp = client.models.generate_content(
                    model=model_name, 
                    contents=messages,
                    config=types.GenerateContentConfig(system_instruction=SYS_INSTRUCT)
                )
                return resp.text
            except Exception as e:
                error_str = str(e)
                if any(err in error_str for err in ["429", "404", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE"]):
                    time.sleep(2)
                    continue
                else:
                    raise e
    return None

if prompt := st.chat_input("Type your action..."):
    if not st.session_state.api_key:
        st.error("Please enter your Gemini API key in the SYS_MENU popover.")
        st.stop()
        
    st.session_state.game["history"].append({"role": "user", "content": prompt, "display": True})
    with st.chat_message("user"):
        st.markdown(prompt)

    context_injected_prompt = (
        prompt + 
        get_lore(prompt) + 
        f"\n[CURRENT STATS: Force:{st.session_state.game['stats']['force']}, Reflex:{st.session_state.game['stats']['reflex']}, Scan:{st.session_state.game['stats']['scan']}, Stability:{st.session_state.game['stats']['stability']}]" +
        f"\n[LOADOUT: Head:{st.session_state.game['loadout']['head']}, L-Arm:{st.session_state.game['loadout']['left_arm']}, R-Arm:{st.session_state.game['loadout']['right_arm']}, Legs:{st.session_state.game['loadout']['legs']}]" +
        f"\n[CURRENT INVENTORY: {st.session_state.game['inventory']}]" +
        f"\n[HOSTILE SCHEMATICS: {st.session_state.game['hostile_schematics']}]"
    )
    
    api_messages = []
    for i, m in enumerate(st.session_state.game["history"]):
        text = m["content"]
        if i == len(st.session_state.game["history"]) - 1 and m["role"] == "user":
            text = context_injected_prompt
            
        api_messages.append(
            types.Content(
                role="model" if m["role"] == "model" else "user",
                parts=[types.Part.from_text(text=text)]
            )
        )

    with st.spinner("Processing feed..."):
        gm_text = call_gemini(api_messages)
                    
        if not gm_text:
            st.error("All fallback models are currently unavailable. Please wait a moment and try again.")
            st.stop()
            
        # Parse d100 Mechanical Checks
        check_match = re.search(r"\[CHECK:\s*stat=([a-z_]+),\s*base=(\d+),\s*mod=(-?\d+),\s*reason=\"(.*?)\"]", gm_text, re.IGNORECASE)
        if check_match:
            stat_name = check_match.group(1).lower()
            base_val = int(check_match.group(2))
            modifier = int(check_match.group(3))
            reason = check_match.group(4)
            
            strain_penalty = st.session_state.game.get("bio_strain", 0)
            effective_target = base_val + modifier - strain_penalty
            
            roll = random.randint(1, 100)
            success_roll = roll <= effective_target
            is_crit_success = roll <= 5
            is_crit_fail = roll >= 96
            
            crit_msg = ""
            if is_crit_fail:
                old_strain = st.session_state.game["bio_strain"]
                st.session_state.game["bio_strain"] = min(100, old_strain + 3)
                crit_msg = f" **[CRIT FAIL: +{st.session_state.game['bio_strain'] - old_strain}% STRAIN SPIKE]**"
            elif is_crit_success:
                old_strain = st.session_state.game["bio_strain"]
                st.session_state.game["bio_strain"] = max(0, old_strain - 2)
                crit_msg = f" **[CRIT SUCCESS: {old_strain - st.session_state.game['bio_strain']}% STRAIN FLUSH]**"
            
            result_box = (
                f"\n\n> `[SYS_CHECK // {stat_name.upper()}]`\n"
                f"> Action: *{reason}*\n"
                f"> Target: {effective_target}% (Base: {base_val} | Mod: {modifier:+d} | Strain: -{strain_penalty}%)\n"
                f"> Roll: {roll} -> **{'SUCCESS' if success_roll else 'FAILURE'}**{crit_msg}\n"
            )
            
            gm_text_part1 = gm_text.replace(check_match.group(0), "").strip() + result_box
            
            follow_up_prompt = (
                f"[SYSTEM OVERRIDE]: The roll resulted in a **{'SUCCESS' if success_roll else 'FAILURE'}** (Rolled {roll} vs Target {effective_target}). "
                "Immediately narrate the consequence of this outcome. If combat damage or strain occurs due to this result, explicitly state the changes in your narration. "
                "Ensure you include all required tracking tags (STATE_UPDATE, COMBAT_STATUS, etc.) at the very end of your response, strictly following the rules for when to log them."
            )
            
            api_messages.append(types.Content(role="model", parts=[types.Part.from_text(text=gm_text)]))
            api_messages.append(types.Content(role="user", parts=[types.Part.from_text(text=follow_up_prompt)]))
            
            gm_text_part2 = call_gemini(api_messages)
            if gm_text_part2:
                gm_text = gm_text_part1 + "\n\n" + gm_text_part2
            else:
                gm_text = gm_text_part1 + "\n\n*[SYSTEM ERROR: Consequence feed dropped. Manual resolution required.]*"

        # Parse State 
        state_match = re.search(r"\[STATE_UPDATE:\s*HP\s*=\s*(\d+)[,\s]*STRAIN\s*=\s*(\d+)[,\s]*INV\s*=\s*(.*?)\]", gm_text, re.IGNORECASE)
        if state_match:
            st.session_state.game["hull_hp"] = int(state_match.group(1))
            st.session_state.game["bio_strain"] = int(state_match.group(2))
            st.session_state.game["inventory"] = state_match.group(3).strip()
            gm_text = gm_text.replace(state_match.group(0), "").strip()
            
        # Parse Threat Log (With deduplication failsafe)
        threat_match = re.search(r"\[THREAT_LOG:\s*(.*?)\]", gm_text, re.IGNORECASE)
        if threat_match:
            entry = threat_match.group(1).strip()
            enemy_name = entry.split("|")[0].strip() # Extracts just the name portion
            
            if st.session_state.game["hostile_schematics"] == "No enemy units scanned yet.":
                st.session_state.game["hostile_schematics"] = f"* {entry}"
            elif enemy_name.lower() not in st.session_state.game["hostile_schematics"].lower():
                st.session_state.game["hostile_schematics"] += f"\n\n* {entry}"
                
            gm_text = gm_text.replace(threat_match.group(0), "").strip()

        # Parse Timeline (With stricter prompt rules above to prevent over-logging)
        timeline_match = re.search(r"\[TIMELINE_LOG:\s*(.*?)\]", gm_text, re.IGNORECASE)
        if timeline_match:
            st.session_state.game["timeline"] += f"\n\n* {timeline_match.group(1).strip()}"
            gm_text = gm_text.replace(timeline_match.group(0), "").strip()

        # Parse Lore (With stricter prompt rules above to prevent over-logging)
        lore_match = re.search(r"\[LORE_LOG:\s*(.*?)\]", gm_text, re.IGNORECASE)
        if lore_match:
            st.session_state.game["lore_notes"] += f"\n\n* {lore_match.group(1).strip()}"
            gm_text = gm_text.replace(lore_match.group(0), "").strip()
            
        # Parse and display active Combat Status at the end of the turn
        combat_match = re.search(r"\[COMBAT_STATUS:\s*(.*?)\]", gm_text, re.IGNORECASE)
        combat_ui_block = ""
        if combat_match:
            status_text = combat_match.group(1).strip()
            combat_ui_block = f"\n\n> ⚔️ **[COMBAT STATUS]:** *{status_text}*"
            gm_text = gm_text.replace(combat_match.group(0), "").strip()
            
        if combat_ui_block:
            gm_text += combat_ui_block
                
        st.session_state.game["history"].append({"role": "model", "content": gm_text, "display": True})
        st.rerun()
