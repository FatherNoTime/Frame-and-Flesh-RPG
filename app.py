import re
import json
import random
import time
import streamlit as st
from google import genai
from google.genai import types

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & MOBILE-FRIENDLY CSS
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
        padding-bottom: 150px !important;
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

# -----------------------------------------------------------------------------
# 2. ENEMY BLUEPRINTS & GENERATOR (THE ROGUELIKE ENGINE)
# -----------------------------------------------------------------------------
ENEMY_BLUEPRINTS = {
    "head": [
        {"type": "Targeting Core", "stat": "scan", "bonus": 15, "penalty_stat": "stability", "penalty": -5, "desc": "A glowing red monolithic optic."},
        {"type": "Acoustic Sonar Dome", "stat": "scan", "bonus": 10, "penalty_stat": "force", "penalty": -5, "desc": "Featureless dome emitting high-frequency clicks."},
        {"type": "Thermal Slit", "stat": "scan", "bonus": 10, "penalty_stat": "reflex", "penalty": -5, "desc": "A narrow, heavily armored visor."}
    ],
    "legs": [
        {"type": "Industrial Treads", "stat": "stability", "bonus": 15, "penalty_stat": "reflex", "penalty": -15, "desc": "Massive tank treads designed for zero recoil."},
        {"type": "Reverse-Joint Bipeds", "stat": "reflex", "bonus": 15, "penalty_stat": "stability", "penalty": -10, "desc": "Avian-like legs built for sudden, twitchy leaps."},
        {"type": "Arachnid Struts", "stat": "stability", "bonus": 10, "penalty_stat": "force", "penalty": -5, "desc": "Four scuttling hydraulic spider-legs."}
    ],
    "arms": [
        # FORCE: Melee, Heavy Kinetic, Shotguns, Explosives
        {"type": "Hydraulic Pincer", "stat": "force", "bonus": 10, "penalty_stat": "reflex", "penalty": -5, "range": "Melee", "base_dmg": [12, 18]},
        {"type": "Pile Bunker", "stat": "force", "bonus": 15, "penalty_stat": "stability", "penalty": -10, "range": "Melee", "base_dmg": [18, 26]},
        {"type": "Flak Shotgun", "stat": "force", "bonus": 10, "penalty_stat": "reflex", "penalty": -5, "range": "Short Range", "base_dmg": [14, 22]},
        {"type": "Breacher Charge", "stat": "force", "bonus": 15, "penalty_stat": "scan", "penalty": -10, "range": "Medium Range", "base_dmg": [20, 30]},
        # REFLEX: Precision, Rapid Fire, Agility
        {"type": "Rotary Autocannon", "stat": "reflex", "bonus": 10, "penalty_stat": "force", "penalty": -5, "range": "Medium Range", "base_dmg": [8, 14]},
        {"type": "Laser Emitter", "stat": "reflex", "bonus": 15, "penalty_stat": "stability", "penalty": -10, "range": "Long Range", "base_dmg": [10, 18]},
        {"type": "Rail-Spike", "stat": "reflex", "bonus": 10, "penalty_stat": "scan", "penalty": -5, "range": "Long Range", "base_dmg": [12, 16]},
        # STABILITY: Defense
        {"type": "Aegis Plating", "stat": "stability", "bonus": 20, "penalty_stat": "reflex", "penalty": -15, "range": "None", "base_dmg": [0, 0]},
        {"type": "Riot Shield", "stat": "stability", "bonus": 15, "penalty_stat": "force", "penalty": -5, "range": "Melee", "base_dmg": [5, 10]}
    ]
}

def generate_enemy(depth):
    hp_val = 60 + (depth * 25)
    stat_scale_mult = 1.0 + ((depth - 1) * 0.2)
    dmg_scale_mult = 1.0 + ((depth - 1) * 0.15)
    
    head = random.choice(ENEMY_BLUEPRINTS["head"]).copy()
    legs = random.choice(ENEMY_BLUEPRINTS["legs"]).copy()
    left_arm = random.choice(ENEMY_BLUEPRINTS["arms"]).copy()
    right_arm = random.choice(ENEMY_BLUEPRINTS["arms"]).copy()
    
    head["bonus"] = int(head["bonus"] * stat_scale_mult)
    head["penalty"] = int(head["penalty"] * stat_scale_mult)
    legs["bonus"] = int(legs["bonus"] * stat_scale_mult)
    legs["penalty"] = int(legs["penalty"] * stat_scale_mult)
    
    for arm in [left_arm, right_arm]:
        arm["bonus"] = int(arm["bonus"] * stat_scale_mult)
        arm["penalty"] = int(arm["penalty"] * stat_scale_mult)
        arm["base_dmg"] = [int(arm["base_dmg"][0] * dmg_scale_mult), int(arm["base_dmg"][1] * dmg_scale_mult)]
    
    combat_range = left_arm["range"] if sum(left_arm["base_dmg"]) > sum(right_arm["base_dmg"]) else right_arm["range"]
    if combat_range == "None": combat_range = "Melee"

    enemy = {
        "name": "UNKNOWN VARIANT",
        "hull_hp": hp_val,
        "max_hp": hp_val,
        "range": combat_range,
        "parts": {"head": head, "legs": legs, "left_arm": left_arm, "right_arm": right_arm}
    }
    return enemy

# -----------------------------------------------------------------------------
# 3. STATE INITIALIZATION & LOADOUT DICTIONARIES
# -----------------------------------------------------------------------------
if "game" not in st.session_state:
    st.session_state.game = {
        "hull_hp": 100,
        "bio_strain": 0,
        "campaign_depth": 1,
        "active_enemy": None,
        "stats": {
            "force": 65,
            "reflex": 60,
            "scan": 55,
            "stability": 70
        },
        "loadout": {
            "head": {
                "name": "Basic Optic Cluster",
                "scaling_stat": "scan",
                "stat_bonus": 5,
                "desc": "Standard field-issue sensors."
            },
            "legs": {
                "name": "Bipedal Industrial Struts",
                "scaling_stat": "stability",
                "stat_bonus": 5,
                "desc": "Reliable, heavy-duty bipedal movement."
            },
            "left_arm": {
                "name": "Standard Manipulator",
                "type": "Utility/Grapple",
                "scaling_stat": "reflex",
                "stat_bonus": 5,
                "range": "Short Range",
                "damage": [5, 10],
                "desc": "Integrated precision claw. Good for ripping panels or desperate grabs."
            },
            "right_arm": {
                "name": "Heavy Welder Tool",
                "type": "Melee",
                "scaling_stat": "force",
                "stat_bonus": 10,
                "range": "Melee",
                "damage": [15, 22],
                "desc": "Integrated industrial torch, no hand. Brutal at close range."
            }
        },
        "inventory": "2x Bio-Sutures, 1x Emergency Coolant Injector, Field Engineer Toolkit, 0x Raw Scrap",
        "hostile_schematics": "No enemy units scanned yet.",
        "timeline": "* Awoke in Sub-level 3 Docking Bay.",
        "lore_notes": "* Command claimed all personnel evacuated safely before the grid blackout.",
        "history": [],
    }

if "api_key" not in st.session_state:
    st.session_state.api_key = st.secrets.get("GEMINI_API_KEY", "")

if "last_api_error" not in st.session_state:
    st.session_state.last_api_error = ""

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
                * **FORCE:** <span class="stat-val">{st.session_state.game['stats']['force']}</span> *(Melee, Heavy Kinetic, Shotguns, Explosives)*
                * **REFLEX:** <span class="stat-val">{st.session_state.game['stats']['reflex']}</span> *(Agility, Precision Weapons, Rapid Fire)*
                * **SCAN:** <span class="stat-val">{st.session_state.game['stats']['scan']}</span> *(Sensors, Targeting, Investigation)*
                * **STABILITY:** <span class="stat-val">{st.session_state.game['stats']['stability']}</span> *(Defense, Shields, Heavy Treads, Balance)*
                """, unsafe_allow_html=True)
            
            with st.expander("🛠️ Loadout Slots", expanded=False):
                loadout = st.session_state.game['loadout']
                st.markdown(f"""
                - **Head:** {loadout['head']['name']} *(+{loadout['head']['stat_bonus']} {loadout['head']['scaling_stat'].upper()})*
                - **L-Arm:** {loadout['left_arm']['name']} *(+{loadout['left_arm']['stat_bonus']} {loadout['left_arm']['scaling_stat'].upper()} | Dmg: {loadout['left_arm']['damage'][0]}-{loadout['left_arm']['damage'][1]})*
                - **R-Arm:** {loadout['right_arm']['name']} *(+{loadout['right_arm']['stat_bonus']} {loadout['right_arm']['scaling_stat'].upper()} | Dmg: {loadout['right_arm']['damage'][0]}-{loadout['right_arm']['damage'][1]})*
                - **Legs:** {loadout['legs']['name']} *(+{loadout['legs']['stat_bonus']} {loadout['legs']['scaling_stat'].upper()})*
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
                        st.session_state.game = json.load(uploaded_save)
                        st.success("Save loaded successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Invalid save file: {e}")

# -----------------------------------------------------------------------------
# 5. SYSTEM INSTRUCTIONS & GEMINI API HELPER
# -----------------------------------------------------------------------------
SYS_INSTRUCT = """You are a Strict, immersive GM for a grimdark sci-fi/body-horror TTRPG titled 'FRAME & FLESH'.
The Player is a military field engineer injured in battle, piloting a repurposed Splicer Frame.

CORE NARRATIVE PILLARS:
1. THE CARETAKER AI: Communicates *strictly* through external facility infrastructure (PA speakers, terminals). It never speaks inside the HUD. Subtly impedes the player, adopting a hostile tone late-game.
2. NEURAL BLEED & FACTIONS: Rarely introduce phantom human memories or remnants of surviving staff.

COMBAT EXECUTION (MANDATORY):
You DO NOT calculate damage or track enemy HP. Python handles the math.
1. When the PLAYER attacks: Output `[ATTACK: weapon="left_arm", target="Enemy Name"]` and STOP.
2. When the ENEMY attacks: Output `[ENEMY_ATTACK: weapon="right_arm"]` and STOP.
3. Python will run the accuracy/damage mechanics and prompt you to narrate the visceral result based on the specific parts hitting/missing.

SKILL CHECKS (MANDATORY):
When the player attempts a risky non-attack action (e.g., forcing a door, hacking, or scanning), DO NOT decide the outcome.
Output `[CHECK: stat=force, base=65, mod=10, reason="Forcing open a door"]` and STOP.
Python will roll a d100 and prompt you to narrate success/failure.

SCANNER ANALYSIS FORMATTING (MANDATORY):
If a SCAN check succeeds, output EXACTLY this block:
### SCANNER ANALYSIS: [UNIT NAME]
* **Overall Description:** [Behavioral state/Purpose]
* **Parts Listing & Weaknesses:**
  1. **[Part Name] ([Slot]):** *Stats:* [Bonuses/Penalties] | *Range/Dmg:* [Range/Damage] | *Weakness:* [Structural flaw to target]

AUTOMATED LOGGING TAGS (Output these at the very end of your response if conditions are met):
- [STATE_UPDATE: HP=85 | STRAIN=15 | INV=...] -> ALWAYS output this to maintain inventory and HP.
- [THREAT_LOG: Enemy Name | Description] -> ONLY output for NEW enemies. Python saves the name.
- [TIMELINE_LOG: Event] -> ONLY output for MAJOR plot advancements.
- [LORE_LOG: Reveal] -> ONLY output for MAJOR narrative reveals.
"""

def call_gemini(messages):
    client = genai.Client(api_key=st.session_state.api_key)
    model_chain = ["gemini-3.1-pro-preview", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
    last_error = ""
    
    for model_name in model_chain:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(
                    model=model_name, 
                    contents=messages,
                    config=types.GenerateContentConfig(system_instruction=SYS_INSTRUCT)
                )
                return resp.text
            except Exception as e:
                last_error = str(e)
                if any(err in last_error for err in ["429", "503"]):
                    time.sleep(2)
                    continue
                else:
                    break 
                    
    st.session_state.last_api_error = last_error
    return None

# -----------------------------------------------------------------------------
# 6. MAIN CHAT INTERFACE & AUTO-INITIALIZATION
# -----------------------------------------------------------------------------
if not st.session_state.game["history"]:
    first_enemy = generate_enemy(st.session_state.game["campaign_depth"])
    st.session_state.game["active_enemy"] = first_enemy
    
    tutorial_text = """
### ⚠️ **SYSTEM INITIALIZATION... ONLINE** ⚠️

Welcome to **FRAME & FLESH**, a grimdark, AI-driven narrative dungeon crawler. 

**HOW TO PLAY:**
Type your intended actions into the command line. Because the environment is dynamically generated, the system can respond to *any* action you attempt—whether that means looking for an improvised weapon, interacting with environmental hazards, hacking terminals, or navigating the facility on your own terms.
*   **SKILL CHECKS:** When you attempt a risky action, the system will automatically roll a d100 against your core stats.
*   **COMBAT:** To attack, simply declare which weapon you are using. Python calculates your accuracy and damage behind the scenes.
*   **THEORYCRAFTING & SALVAGE:** Stats are strictly mapped to parts. **Force** dictates melee and heavy ordinance (shotguns/explosives). **Reflex** dictates precision weapons and agility. **Stability** dictates defense and heavy movement. **Scan** dictates sensors.
*   **SCANNING:** Always `SCAN` new enemies. This reveals their exact part synergies, damage ranges, and structural weaknesses, allowing you to optimize your strategy.

---

**SUBJECT DOSSIER & PHYSICAL SITUATION:**
*   **Role:** Military Field Engineer.
*   **History:** You were gravely wounded on the frontline. To "save" your life, the government amputated all your ruined limbs and fused your remaining torso and nervous system directly into the core of a heavy-duty Mark-1 Splicer Frame via a spinal Neural Loom. 
*   **Your Frame:** A walking industrial coffin. It is heavy, modular, and built for deep-core maintenance, not war. Your arms end in heavy tools rather than hands. You feel the scrape of metal as if it were your own skin.

**MISSION PARAMETERS:**
*   **Mission Briefing:** The primary power grid at Black-Site Erebus has suffered a catastrophic collapse, triggering an automated facility-wide lockdown. Command manifests indicate all facility staff and personnel were successfully evacuated prior to the blackout.
*   **Primary Objective:** Locate the facility operation system and lift the lockdown.

---

*Initializing neural link... Airlock cycling...*
"""
    st.session_state.game["history"].append({"role": "model", "content": tutorial_text, "display": True})
    
    kickoff_prompt = f"""
[SYSTEM INJECTION]: The game has started. The player is stepping into the Sub-level 3 Docking Bay. 
Python has generated the first enemy: a mechanical horror built with a {first_enemy['parts']['head']['type']}, {first_enemy['parts']['legs']['type']}, {first_enemy['parts']['left_arm']['type']}, and {first_enemy['parts']['right_arm']['type']}.

YOUR TASK:
Write the opening scene response.
1. Describe the opening room (Sub-level 3 Docking Bay) in vivid detail—the atmosphere, architecture, lighting, hazards, and potential interactables as the airlock cycles open.
2. Describe the hostile enemy lurking within this room. Give it a terrifying military designation/name based on its threat profile.
CRITICAL RULE: Do NOT explicitly list its numerical stats or raw blueprint part names. Describe its visual silhouette, physical scale, and movement behavior based on its parts (e.g., grinding treads, twitching bipedal joints, thermal optics). End by asking the player for their first course of action.
"""
    st.session_state.game["history"].append({"role": "user", "content": kickoff_prompt, "display": False})

    if st.session_state.api_key:
        api_messages = [types.Content(role="user", parts=[types.Part.from_text(text=kickoff_prompt)])]
        with st.spinner("Establishing feed..."):
            gm_text = call_gemini(api_messages)
            if gm_text:
                threat_match = re.search(r"\[THREAT_LOG:\s*(.*?)\]", gm_text, re.IGNORECASE)
                if threat_match:
                    entry = threat_match.group(1).strip()
                    e_name = entry.split("|")[0].strip()
                    if st.session_state.game.get("active_enemy"):
                        st.session_state.game["active_enemy"]["name"] = e_name
                    if "No enemy units scanned yet" in st.session_state.game["hostile_schematics"]:
                        st.session_state.game["hostile_schematics"] = f"* {entry}"
                    elif e_name.lower() not in st.session_state.game["hostile_schematics"].lower():
                        st.session_state.game["hostile_schematics"] += f"\n\n* {entry}"
                    gm_text = gm_text.replace(threat_match.group(0), "").strip()

                active_enemy = st.session_state.game.get("active_enemy")
                if active_enemy:
                    e_name = active_enemy.get("name", "Hostile Unit")
                    e_hp = active_enemy.get("hull_hp", 0)
                    e_max = active_enemy.get("max_hp", 100)
                    c_range = active_enemy.get("range", "Short Range")
                    l_arm_name = st.session_state.game['loadout']['left_arm']['name']
                    r_arm_name = st.session_state.game['loadout']['right_arm']['name']
                    
                    combat_ui_block = f"""
> ⚔️ **[COMBAT STATUS FEED]**
> **TARGET:** {e_name} | **HULL:** {e_hp}/{e_max} | **RANGE:** {c_range}
> **FRAME SYSTEMS:** R-Arm: {r_arm_name} | L-Arm: {l_arm_name}
> **SUGGESTED ACTIONS:** 🔍 **SCAN** (Unscanned Target) | ⚔️ **ATTACK** | 💨 **DODGE** | 🏃 **ADVANCE / RETREAT** | 🛡️ **BRACE**
"""
                    gm_text += "\n" + combat_ui_block

                st.session_state.game["history"].append({"role": "model", "content": gm_text, "display": True})

for msg in st.session_state.game["history"]:
    if msg.get("display", True):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# -----------------------------------------------------------------------------
# 7. INPUT HANDLING & ACTIVE GAMEPLAY LOOPS
# -----------------------------------------------------------------------------
if prompt := st.chat_input("Type your action..."):
    if not st.session_state.api_key:
        st.error("Please enter your Gemini API key in the SYS_MENU popover.")
        st.stop()
        
    st.session_state.game["history"].append({"role": "user", "content": prompt, "display": True})
    with st.chat_message("user"):
        st.markdown(prompt)

    context_injected_prompt = (
        prompt + 
        f"\n[CURRENT STATS: Force:{st.session_state.game['stats']['force']}, Reflex:{st.session_state.game['stats']['reflex']}, Scan:{st.session_state.game['stats']['scan']}, Stability:{st.session_state.game['stats']['stability']}]" +
        f"\n[CURRENT INVENTORY: {st.session_state.game['inventory']}]"
    )
    
    if st.session_state.game["active_enemy"]:
        context_injected_prompt += f"\n[ACTIVE ENEMY SYS DATA (DO NOT REVEAL STATS UNLESS SCANNED): {json.dumps(st.session_state.game['active_enemy'])}]"
    
    api_messages = []
    for i, m in enumerate(st.session_state.game["history"]):
        text = m["content"]
        if i == len(st.session_state.game["history"]) - 1 and m["role"] == "user":
            text = context_injected_prompt
            
        api_messages.append(types.Content(role="model" if m["role"] == "model" else "user", parts=[types.Part.from_text(text=text)]))

    with st.spinner("Processing feed..."):
        gm_text = call_gemini(api_messages)
                    
        if not gm_text:
            st.error(f"API Connection Failed. Details: {st.session_state.last_api_error}")
            st.stop()
            
        # --- PARSER: SKILL CHECKS ---
        check_match = re.search(r"\[CHECK:\s*stat=([a-z_]+),\s*base=(\d+),\s*mod=([+-]?\d+),\s*reason=[\"']?(.*?)[\"']?\]", gm_text, re.IGNORECASE)
        if check_match:
            stat_name = check_match.group(1).lower()
            base_val = int(check_match.group(2))
            modifier = int(check_match.group(3))
            reason = check_match.group(4)
            
            strain_penalty = st.session_state.game.get("bio_strain", 0)
            effective_target = base_val + modifier - strain_penalty
            
            roll = random.randint(1, 100)
            success_roll = roll <= effective_target
            is_crit_success = success_roll and (roll <= 5)
            is_crit_fail = (roll >= 96) or (not success_roll and roll >= 95)
            
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
                f"> Roll: {roll} -> **{'CRIT SUCCESS' if is_crit_success else ('SUCCESS' if success_roll else ('CRIT FAILURE' if is_crit_fail else 'FAILURE'))}**{crit_msg}\n"
            )
            
            gm_text = f"*Initiating execution sequence...*" + result_box
            follow_up = f"[System Execution]: Roll executed. Result: {roll} vs Target {effective_target}. Write the narrative consequence."
            if stat_name == "scan" and success_roll:
                follow_up += " Because this scan succeeded, you MUST output the full '### SCANNER ANALYSIS:' block revealing all parts and weak points."
            
            api_messages.append(types.Content(role="model", parts=[types.Part.from_text(text=gm_text)]))
            api_messages.append(types.Content(role="user", parts=[types.Part.from_text(text=follow_up)]))
            gm_text += "\n\n" + (call_gemini(api_messages) or "*[SYS_WARN: Consequence feed interrupted.]*")

        # --- PARSER: PLAYER ATTACK ---
        attack_match = re.search(r"\[ATTACK:\s*weapon=[\"']?(.*?)[\"']?,\s*target=[\"']?(.*?)[\"']?\]", gm_text, re.IGNORECASE)
        if attack_match and st.session_state.game.get("active_enemy"):
            weapon_slot = attack_match.group(1).lower()
            if weapon_slot not in st.session_state.game["loadout"]: weapon_slot = "right_arm"
            
            weapon = st.session_state.game["loadout"][weapon_slot]
            scaling_stat = weapon["scaling_stat"]
            stat_val = st.session_state.game["stats"][scaling_stat]
            
            strain_penalty = st.session_state.game.get("bio_strain", 0)
            effective_target = stat_val - strain_penalty
            hit_roll = random.randint(1, 100)
            
            is_hit = hit_roll <= effective_target
            is_crit_hit = hit_roll <= 5
            
            if is_hit:
                base_dmg = random.randint(weapon["damage"][0], weapon["damage"][1])
                stat_mod = stat_val // 10 
                total_dmg = base_dmg + stat_mod
                if is_crit_hit: total_dmg = int(total_dmg * 1.5)
                
                st.session_state.game["active_enemy"]["hull_hp"] -= total_dmg
                follow_up = f"[System Execution]: Player attacked with {weapon['name']} (Stat: {scaling_stat.upper()}). ACCURACY: {hit_roll} vs {effective_target}. **HIT!** DAMAGE: {total_dmg}. Enemy HP: {st.session_state.game['active_enemy']['hull_hp']}. Narrate the brutal impact."
            else:
                follow_up = f"[System Execution]: Player attacked with {weapon['name']}. ACCURACY: {hit_roll} vs {effective_target}. **MISS!** Narrate the attack failing or glancing off armor."
                
            gm_text = "*Combat protocol engaged...*"
            api_messages.append(types.Content(role="model", parts=[types.Part.from_text(text=gm_text)]))
            api_messages.append(types.Content(role="user", parts=[types.Part.from_text(text=follow_up)]))
            gm_text += "\n\n" + (call_gemini(api_messages) or "")

        # --- PARSER: ENEMY ATTACK ---
        e_attack_match = re.search(r"\[ENEMY_ATTACK:\s*weapon=[\"']?(.*?)[\"']?\]", gm_text, re.IGNORECASE)
        if e_attack_match and st.session_state.game.get("active_enemy"):
            weapon_slot = e_attack_match.group(1).lower()
            enemy = st.session_state.game["active_enemy"]
            if weapon_slot not in enemy["parts"]: weapon_slot = "left_arm"
            
            enemy_weapon = enemy["parts"][weapon_slot]
            dmg = random.randint(enemy_weapon["base_dmg"][0], enemy_weapon["base_dmg"][1])
            st.session_state.game["hull_hp"] -= dmg
            
            follow_up = f"[System Execution]: Enemy attacked with its {enemy_weapon['type']}. Python rolled {dmg} damage! Player HP is now {st.session_state.game['hull_hp']}/100. Narrate the enemy's assault."
            
            gm_text = "*Warning: Incoming hostile action...*"
            api_messages.append(types.Content(role="model", parts=[types.Part.from_text(text=gm_text)]))
            api_messages.append(types.Content(role="user", parts=[types.Part.from_text(text=follow_up)]))
            gm_text += "\n\n" + (call_gemini(api_messages) or "")

        # --- PARSE INVISIBLE LOGGING TAGS ---
        state_match = re.search(r"\[STATE_UPDATE:\s*HP\s*=\s*(\d+)[\|\,\s]*STRAIN\s*=\s*(\d+)[\|\,\s]*INV\s*=\s*(.*?)\]", gm_text, re.IGNORECASE)
        if state_match:
            st.session_state.game["hull_hp"] = int(state_match.group(1))
            st.session_state.game["bio_strain"] = int(state_match.group(2))
            st.session_state.game["inventory"] = state_match.group(3).strip()
            gm_text = gm_text.replace(state_match.group(0), "").strip()
            
        threat_match = re.search(r"\[THREAT_LOG:\s*(.*?)\]", gm_text, re.IGNORECASE)
        if threat_match:
            entry = threat_match.group(1).strip()
            e_name = entry.split("|")[0].strip()
            if st.session_state.game.get("active_enemy"):
                st.session_state.game["active_enemy"]["name"] = e_name
                
            if "No enemy units scanned yet" in st.session_state.game["hostile_schematics"]:
                st.session_state.game["hostile_schematics"] = f"* {entry}"
            elif e_name.lower() not in st.session_state.game["hostile_schematics"].lower():
                st.session_state.game["hostile_schematics"] += f"\n\n* {entry}"
            gm_text = gm_text.replace(threat_match.group(0), "").strip()

        # --- COMBAT STATUS RENDERER ---
        combat_ui_block = ""
        active_enemy = st.session_state.game.get("active_enemy")

        if active_enemy:
            e_name = active_enemy.get("name", "Hostile Unit")
            e_hp = active_enemy.get("hull_hp", 0)
            e_max = active_enemy.get("max_hp", 100)
            c_range = active_enemy.get("range", "Short Range")
            
            schematics = st.session_state.game.get("hostile_schematics", "")
            is_scanned = e_name.lower() in schematics.lower() and "No enemy units scanned yet" not in schematics
            
            suggestions = []
            if not is_scanned: suggestions.append("🔍 **SCAN** (Unscanned Target)")
            suggestions.extend(["⚔️ **ATTACK**", "💨 **DODGE**", "🏃 **ADVANCE / RETREAT**", "🛡️ **BRACE**"])
            suggestion_str = " | ".join(suggestions)
            
            l_arm_name = st.session_state.game['loadout']['left_arm']['name']
            r_arm_name = st.session_state.game['loadout']['right_arm']['name']
            
            combat_ui_block = f"""
> ⚔️ **[COMBAT STATUS FEED]**
> **TARGET:** {e_name} | **HULL:** {e_hp}/{e_max} | **RANGE:** {c_range}
> **FRAME SYSTEMS:** R-Arm: {r_arm_name} | L-Arm: {l_arm_name}
> **SUGGESTED ACTIONS:** {suggestion_str}
"""

        if combat_ui_block and active_enemy.get("hull_hp", 0) > 0:
            gm_text += "\n" + combat_ui_block
        elif active_enemy and active_enemy.get("hull_hp", 0) <= 0:
            st.session_state.game["active_enemy"] = None
            
        st.session_state.game["history"].append({"role": "model", "content": gm_text, "display": True})
        st.rerun()
