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
    [data-testid="stHeader"], footer, [data-testid="stToolbar"], [data-testid="stSidebar"] { display: none !important; }
    .st-key-fixed_hud_container { position: fixed !important; top: 0 !important; left: 0 !important; right: 0 !important; width: 100% !important; z-index: 99999 !important; background-color: #12151a !important; border-bottom: 1px solid #2a323d !important; padding: 6px 12px !important; box-shadow: 0px 4px 15px rgba(0,0,0,0.9); box-sizing: border-box; }
    .st-key-fixed_hud_container button { background-color: #1a1f29 !important; color: #00ffcc !important; border: 1px solid #2a323d !important; font-family: 'Courier New', Courier, monospace !important; font-size: 0.65rem !important; padding: 2px 6px !important; margin-top: 2px !important; width: 100% !important; }
    .block-container { padding-top: 95px !important; padding-bottom: 150px !important; }
    [data-testid="stChatInputContainer"] { position: fixed !important; bottom: 15px !important; left: 50% !important; transform: translateX(-50%) !important; width: 92% !important; max-width: 750px !important; z-index: 99998 !important; background-color: #12151a !important; border-radius: 8px !important; box-shadow: 0px -4px 15px rgba(0,0,0,0.8); }
    .hp-text { color: #00ffcc; font-weight: bold; }
    .strain-text { color: #ff3366; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. ENEMY BLUEPRINTS & GENERATOR (THE ROGUELIKE ENGINE)
# -----------------------------------------------------------------------------
RANGE_VALS = {"Melee": 1, "Short Range": 2, "Medium Range": 3, "Long Range": 4}

ENEMY_BLUEPRINTS = {
    "head": [
        {"type": "Targeting Core", "stat": "scan", "bonus": 15, "penalty_stat": "stability", "penalty": -5, "hp": 25, "status": "Online", "weakness": "Exposed optics crack under kinetic impact.", "strain_cost": 0, "desc": "Processes visual telemetry and guides combat tracking systems."},
    ],
    "legs": [
        {"type": "Industrial Treads", "stat": "stability", "bonus": 15, "penalty_stat": "reflex", "penalty": -15, "hp": 40, "status": "Online", "weakness": "Tread links can be jammed by debris.", "strain_cost": 0, "desc": "Provides heavy-duty locomotion and immense recoil dampening."},
    ],
    "arms": [
        {"type": "Hydraulic Pincer", "stat": "force", "bonus": 10, "penalty_stat": "reflex", "penalty": -5, "range": "Melee", "base_dmg": [12, 18], "hp": 30, "status": "Online", "weakness": "Hydraulic lines exposed at the joint.", "strain_cost": 0, "desc": "Delivers devastating crushing and tearing force at extreme close range."},
        {"type": "Flak Shotgun", "stat": "force", "bonus": 10, "penalty_stat": "reflex", "penalty": -5, "range": "Short Range", "base_dmg": [14, 22], "hp": 25, "status": "Online", "weakness": "Ammunition feed prone to jams.", "strain_cost": 0, "desc": "Fires wide-spread kinetic shrapnel for brutal close-quarters suppression."},
        {"type": "Laser Emitter", "stat": "reflex", "bonus": 15, "penalty_stat": "stability", "penalty": -10, "range": "Long Range", "base_dmg": [10, 18], "hp": 20, "status": "Online", "weakness": "Cooling vents easily disrupted.", "strain_cost": 0, "desc": "Projects high-intensity thermal beams for lethal precision strikes."},
        {"type": "Fleshed-Over Autocannon", "stat": "force", "bonus": 20, "penalty_stat": "reflex", "penalty": -10, "range": "Medium Range", "base_dmg": [22, 35], "hp": 45, "status": "Online", "weakness": "Pulsing bio-sacs burst easily under scan-assisted fire.", "strain_cost": 15, "desc": "A terrifying amalgamation of flesh and machinery unleashing heavy ordinance."}
    ]
}

def generate_enemy(depth):
    hp_val = 60 + (depth * 25)
    
    head = random.choice(ENEMY_BLUEPRINTS["head"]).copy()
    legs = random.choice(ENEMY_BLUEPRINTS["legs"]).copy()
    left_arm = random.choice(ENEMY_BLUEPRINTS["arms"]).copy()
    right_arm = random.choice(ENEMY_BLUEPRINTS["arms"]).copy()
    
    combat_range = left_arm["range"] if sum(left_arm.get("base_dmg", [0])) > sum(right_arm.get("base_dmg", [0])) else right_arm["range"]

    enemy = {
        "name": "UNKNOWN VARIANT",
        "scanned": False,
        "hull_hp": hp_val,
        "max_hp": hp_val,
        "range": combat_range,
        "distance": "Long Range", 
        "parts": {"head": head, "legs": legs, "left_arm": left_arm, "right_arm": right_arm},
        "hazard_zone": False
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
        "rooms_cleared": 0,
        "is_safe_room": False,
        "active_enemy": None,
        "stats": {"force": 65, "reflex": 60, "scan": 55, "stability": 70},
        "loadout": {
            "head": {"name": "Basic Optic Cluster", "scaling_stat": "scan", "stat_bonus": 5, "hp": 30, "status": "Online", "strain_cost": 0},
            "legs": {"name": "Bipedal Industrial Struts", "scaling_stat": "stability", "stat_bonus": 5, "hp": 40, "status": "Online", "strain_cost": 0},
            "left_arm": {"name": "Standard Manipulator", "scaling_stat": "reflex", "stat_bonus": 5, "range": "Short Range", "damage": [5, 10], "hp": 30, "status": "Online", "strain_cost": 0},
            "right_arm": {"name": "Heavy Welder Tool", "scaling_stat": "force", "stat_bonus": 10, "range": "Melee", "damage": [15, 22], "hp": 30, "status": "Online", "strain_cost": 0}
        },
        "inventory": {
            "scrap": 0,
            "bio_sutures": 2,
            "parts": []
        },
        "history": [],
    }

if "api_key" not in st.session_state: st.session_state.api_key = st.secrets.get("GEMINI_API_KEY", "")
if "last_api_error" not in st.session_state: st.session_state.last_api_error = ""

# -----------------------------------------------------------------------------
# 4. HUD & MENU CONTAINER
# -----------------------------------------------------------------------------
with st.container(key="fixed_hud_container"):
    col_hud, col_btn = st.columns([3.8, 1.0])
    with col_hud:
        st.markdown(f"""
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.68rem;">
                <span style="color: #667080; letter-spacing: 0.5px;">OP STATUS // SUBJ 09 // DEPTH {st.session_state.game['campaign_depth']}</span>
                <span>HULL: <span class="hp-text">{st.session_state.game['hull_hp']}/100</span> | STRAIN: <span class="strain-text">{st.session_state.game['bio_strain']}%</span></span>
            </div>
            <div style="font-size: 0.65rem; color: #8892b0; margin-top: 2px; word-break: break-word;">
                SCRAP: {st.session_state.game['inventory']['scrap']} | SUTURES: {st.session_state.game['inventory']['bio_sutures']} | SALVAGED PARTS: {len(st.session_state.game['inventory']['parts'])}
            </div>
        """, unsafe_allow_html=True)
    with col_btn:
        with st.popover("⚙️ SYS_MENU", use_container_width=True):
            tab1, tab2, tab3 = st.tabs(["LOADOUT", "CARGO", "CONFIG"])
            
            with tab1:
                st.markdown("### RIG CONFIGURATION")
                for slot, part in st.session_state.game["loadout"].items():
                    st.markdown(f"**{slot.upper()}**: {part['name']} (HP: {part.get('hp', 0)})")
                    st.caption(f"Scaling: {part.get('scaling_stat', 'N/A').title()} | Range: {part.get('range', 'N/A')} | Strain: {part.get('strain_cost', 0)}%")
            
            with tab2:
                st.markdown("### CARGO & CONSUMABLES")
                col_c1, col_c2 = st.columns(2)
                col_c1.metric("Raw Scrap", st.session_state.game['inventory']['scrap'])
                col_c2.metric("Bio-Sutures", st.session_state.game['inventory']['bio_sutures'])
                
                if st.button("💉 Use Bio-Suture (+15 HP, -15% Strain)", use_container_width=True, disabled=st.session_state.game['inventory']['bio_sutures'] <= 0 or (st.session_state.game['hull_hp'] == 100 and st.session_state.game['bio_strain'] == 0)):
                    st.session_state.game["inventory"]["bio_sutures"] -= 1
                    st.session_state.game["hull_hp"] = min(100, st.session_state.game["hull_hp"] + 15)
                    st.session_state.game["bio_strain"] = max(0, st.session_state.game["bio_strain"] - 15)
                    st.success("Bio-suture applied successfully.")
                    st.rerun()
                    
                st.markdown("---")
                st.markdown("### INTACT SALVAGE")
                if not st.session_state.game["inventory"]["parts"]:
                    st.caption("No intact parts in cargo.")
                else:
                    for idx, p in enumerate(st.session_state.game["inventory"]["parts"]):
                        st.markdown(f"**{p['name']}** (HP: {p['hp']})")
                        st.caption(f"Scaling: {p.get('scaling_stat', 'N/A').title()} | Dmg: {p.get('damage', [0,0])} | Strain: {p.get('strain_cost', 0)}%")
                        
                        if st.session_state.game.get("active_enemy") is None and not st.session_state.game.get("is_safe_room"):
                            col1, col2 = st.columns([2, 1])
                            target_slot = col1.selectbox("Mount Point", ["head", "legs", "left_arm", "right_arm"], key=f"slot_{idx}", label_visibility="collapsed")
                            if col2.button("Install", key=f"install_{idx}"):
                                old_part = st.session_state.game["loadout"][target_slot]
                                new_part = p
                                
                                old_strain = old_part.get("strain_cost", 0)
                                new_strain = new_part.get("strain_cost", 0)
                                
                                st.session_state.game["bio_strain"] -= old_strain
                                st.session_state.game["bio_strain"] += new_strain
                                st.session_state.game["bio_strain"] = max(0, st.session_state.game["bio_strain"])
                                
                                st.session_state.game["loadout"][target_slot] = new_part
                                st.session_state.game["inventory"]["parts"].pop(idx)
                                st.session_state.game["inventory"]["parts"].append(old_part)
                                st.rerun()
                        else:
                            st.caption("*Part swapping disabled during active operations.*")
                            
            with tab3:
                st.title("SYS_CONFIG")
                with st.form("api_key_form"):
                    api_input = st.text_input("Gemini API Key", type="password", value=st.session_state.api_key)
                    if st.form_submit_button("Save Key"):
                        st.session_state.api_key = api_input
                        st.success("Key Saved")

# -----------------------------------------------------------------------------
# 5. SYSTEM INSTRUCTIONS & GEMINI API HELPER
# -----------------------------------------------------------------------------
SYS_INSTRUCT = """You are a Strict, immersive GM for a grimdark sci-fi/body-horror TTRPG titled 'FRAME & FLESH'.

LORE & NARRATIVE RULES (STRICT):
- DO NOT describe enemies crushing, eating, or standing on human remains. 
- Humanity's state: All remaining humans are either part of a dissident faction OR actively used by the AI for twisted experimentation. Do not scatter random human corpses on the floor.
- NEVER generate the [COMBAT STATUS FEED] UI box or any HTML divs. Python handles this automatically.

MECHANICS & TAGGING RULES:
1. When PLAYER scans: Output `[SCAN]` and STOP.
2. When PLAYER attacks: Output `[ATTACK: weapon="right_arm", target_part="head", disable_attempt=False]` and STOP.
3. When PLAYER searches environment: Output `[ENV_SEARCH]` and STOP.
4. When PLAYER performs engineering action: Output `[ENGINEERING_ACTION: action_type="hazard_spill"]` and STOP.
5. When PLAYER interacts with objects: Output `[ENV_ACTION: type="loose" or "anchored", object="description"]` and STOP.
6. When ENEMY attacks: Output `[ENEMY_ATTACK: weapon="left_arm"]` and STOP.

AUTOMATED LOGGING TAGS (Place on a new line at the end):
- [PROXIMITY_UPDATE: <Distance>] -> Output ONLY if physical distance changes.
- [THREAT_LOG: Enemy Name | Description]
"""

def call_gemini(messages):
    client = genai.Client(api_key=st.session_state.api_key)
    for attempt in range(3):
        try:
            resp = client.models.generate_content(model="gemini-3.5-flash-lite", contents=messages, config=types.GenerateContentConfig(system_instruction=SYS_INSTRUCT))
            return resp.text
        except Exception as e:
            st.session_state.last_api_error = str(e)
            time.sleep(1.0)
    return None

# -----------------------------------------------------------------------------
# 6. SAFE ROOM RENDERING FUNCTION
# -----------------------------------------------------------------------------
def render_safe_room():
    with st.chat_message("assistant"):
        st.markdown("### 🛡️ **[SECURE ZONE ACCESSED: BIO-FORGE ONLINE]**")
        st.write("The airlock seals tight. Ambient hostiles are locked out. Recovery protocols and upgrade arrays are standing by.")
        
        scrap = st.session_state.game["inventory"]["scrap"]
        sutures = st.session_state.game["inventory"]["bio_sutures"]
        
        st.markdown(f"**CARGO STATUS:** `Scrap: {scrap}` | `Bio-Sutures: {sutures}`")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**HULL REPAIR**")
            st.caption("Cost: 3 Raw Scrap\nRestores 30 Hull HP.")
            if st.button("Repair Rig", disabled=scrap < 3 or st.session_state.game["hull_hp"] == 100, key="safe_repair"):
                st.session_state.game["inventory"]["scrap"] -= 3
                st.session_state.game["hull_hp"] = min(100, st.session_state.game["hull_hp"] + 30)
                st.rerun()
                
        with col2:
            st.markdown("**APPLY BIO-SUTURE**")
            st.caption(f"Stock: {sutures}\nFlushes systemic trauma, clearing 15% Strain and healing 15 HP.")
            if st.button("Use Suture", disabled=sutures <= 0 or (st.session_state.game["hull_hp"] == 100 and st.session_state.game["bio_strain"] == 0), key="safe_suture"):
                st.session_state.game["inventory"]["bio_sutures"] -= 1
                st.session_state.game["hull_hp"] = min(100, st.session_state.game["hull_hp"] + 15)
                st.session_state.game["bio_strain"] = max(0, st.session_state.game["bio_strain"] - 15)
                st.rerun()
                
        with col3:
            st.markdown("**NEURAL OVERCLOCK**")
            st.caption("Cost: 5 Raw Scrap\nPermanently boosts a core stat.")
            stat_choice = st.selectbox("Select Stat", ["force", "reflex", "scan", "stability"], label_visibility="collapsed", key="safe_stat")
            if st.button("Overclock", disabled=scrap < 5, key="safe_overclock"):
                st.session_state.game["inventory"]["scrap"] -= 5
                st.session_state.game["stats"][stat_choice] += 5
                st.rerun()
                
        st.divider()
        if st.button("Breach Next Bulkhead (Leave Safe Room)", use_container_width=True, key="safe_exit"):
            st.session_state.game["is_safe_room"] = False
            st.session_state.game["rooms_cleared"] += 1
            
            new_enemy = generate_enemy(st.session_state.game["campaign_depth"])
            st.session_state.game["active_enemy"] = new_enemy
            
            system_log = f"\n> 🚪 **[SYSTEM]: PROCEEDING TO ZONE {st.session_state.game['rooms_cleared'] + 1}. NEW HOSTILE DETECTED.**"
            st.session_state.game["history"].append({"role": "model", "content": system_log, "display": True})
            st.rerun()

# -----------------------------------------------------------------------------
# 7. MAIN CHAT & AUTO-INITIALIZATION
# -----------------------------------------------------------------------------
if not st.session_state.game["history"]:
    first_enemy = generate_enemy(st.session_state.game["campaign_depth"])
    st.session_state.game["active_enemy"] = first_enemy
    
    tutorial_text = """
### ⚠️ **SYSTEM INITIALIZATION... ONLINE** ⚠️

Welcome to **FRAME & FLESH**, a grimdark, AI-driven narrative dungeon crawler. 

**HOW TO PLAY:**
Type your intended actions into the command line. Because the environment is dynamically generated, the system can respond to *any* action you attempt.
*   **SKILL CHECKS:** When you attempt a risky action, the system automatically rolls a d100 against your core stats.
*   **COMBAT:** To attack, simply declare which weapon you are using. Python calculates your accuracy and damage behind the scenes.
*   **ENVIRONMENTAL SEARCH:** Say "I look around the room" or "I look for something to throw" to gather environmental options via your optic sensors.
*   **OOC CLARIFICATION:** Use `OOC:` or `[OOC]` followed by your question to access the restricted meta-channel for rules, mechanics, or lore without triggering gameplay actions.

---

**SUBJECT DOSSIER & PHYSICAL SITUATION:**
*   **Role:** Military Field Engineer.
*   **History:** You were gravely wounded on the frontline and fused directly into the core of a heavy-duty Mark-1 Splicer Frame via a spinal Neural Loom.

---

*[Loading] Initializing neural link... Airlock cycling...*
"""
    st.session_state.game["history"].append({"role": "model", "content": tutorial_text, "display": True})
    
    kickoff_prompt = f"""
[SYSTEM INJECTION]: The game has started. The player is stepping into the Sub-level 3 Docking Bay. 
Python has generated the first enemy: a mechanical horror built with a {first_enemy['parts']['head']['type']}, {first_enemy['parts']['legs']['type']}, {first_enemy['parts']['left_arm']['type']}, and {first_enemy['parts']['right_arm']['type']}.

YOUR TASK:
Write the opening scene response.
1. Describe the opening room (Sub-level 3 Docking Bay) in vivid detail—atmosphere, architecture, lighting, hazards, and potential interactables as the airlock cycles open.
2. Describe the hostile enemy lurking within this room. Give it a terrifying military designation/name based on its threat profile. YOU MUST ALSO include a line containing the exact tag `[THREAT_LOG: <Designation Name> | <Short Description>]` at the very end of your response so the system can catalog it.
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
                    gm_text = gm_text.replace(threat_match.group(0), "").strip()

                gm_text = re.sub(r"\[STATE_UPDATE:.*?\]", "", gm_text, flags=re.IGNORECASE)
                gm_text = re.sub(r"\[PROXIMITY_UPDATE:.*?\]", "", gm_text, flags=re.IGNORECASE)
                gm_text = gm_text.strip()

                active_enemy = st.session_state.game.get("active_enemy")
                if active_enemy:
                    e_hp = active_enemy.get("hull_hp", 0)
                    e_max = active_enemy.get("max_hp", 100)
                    c_range = active_enemy.get("range", "Short Range")
                    e_dist = active_enemy.get("distance", "Long Range")
                    
                    l_arm_name = st.session_state.game['loadout']['left_arm']['name']
                    r_arm_name = st.session_state.game['loadout']['right_arm']['name']
                    
                    is_scanned = active_enemy.get("scanned", False)
                    display_name = active_enemy.get("name") if is_scanned else "UNKNOWN HOSTILE"
                    
                    actions = []
                    if not is_scanned: 
                        actions.append("🔍 **SCAN** (Unscanned Target)")
                        
                    has_valid_attack = any(
                        v.get("status") == "Online" and "damage" in v and RANGE_VALS.get(v.get("range", "Melee"), 1) >= RANGE_VALS.get(e_dist, 1)
                        for v in st.session_state.game["loadout"].values() if isinstance(v, dict)
                    )
                    if has_valid_attack:
                        actions.append("⚔️ **ATTACK**")
                        
                    actions.extend(["👁️ **LOOK AROUND**", "🏃 **ADVANCE**", "🏃 **RETREAT**", "👻 **HIDE**"])
                    action_str = " | ".join(actions)
                    
                    combat_ui_block = f"""
<div style="background-color: #12151a; border-left: 3px solid #00ffcc; padding: 10px 14px; margin: 10px 0; font-family: 'Courier New', Courier, monospace; font-size: 0.8rem; color: #c5c9d1; border-radius: 4px;">
    <b>⚔️ [COMBAT STATUS FEED]</b><br>
    <b>TARGET:</b> {display_name} | HULL: {e_hp}/{e_max} | WEAPON RANGE: {c_range}<br>
    <b>TARGET PROXIMITY:</b> {e_dist}<br>
    <b>USER FRAME SYSTEMS:</b> R-Arm: {r_arm_name} | L-Arm: {l_arm_name}<br>
    <b>SUGGESTED ACTIONS:</b> {action_str}
</div>
"""
                    gm_text += "\n" + combat_ui_block

                st.session_state.game["history"].append({"role": "model", "content": gm_text, "display": True})
                st.rerun()

# -----------------------------------------------------------------------------
# 8. INPUT HANDLING, PARSING & GUARDRAILS
# -----------------------------------------------------------------------------
if prompt := st.chat_input("Type your action..."):
    if not st.session_state.api_key:
        st.error("Missing API Key.")
        st.stop()
        
    # GUARDRAIL 1: ZERO-TOLERANCE ANTI-REROLL PROTOCOL
    if re.search(r"\b(reroll|reset roll|retry roll|reroll enemy|undo)\b", prompt, re.IGNORECASE):
        error_msg = "> 🛑 **[REALITY STREAM ANOMALY INTERCEPTED]**: Temporal rewind commands rejected. The timeline is immutable. Run integrity preserved."
        st.session_state.game["history"].append({"role": "user", "content": prompt, "display": True})
        st.session_state.game["history"].append({"role": "model", "content": error_msg, "display": True})
        st.rerun()

    # GUARDRAIL 2: RESTRICTED OOC CLARIFICATION CHANNEL
    if prompt.lower().startswith("ooc:") or prompt.lower().startswith("[ooc]") or re.search(r"^\s*ooc\b", prompt, re.IGNORECASE):
        st.session_state.game["history"].append({"role": "user", "content": prompt, "display": True})
        ooc_query = re.sub(r"^(ooc:|\[ooc\]|\booc\b)", "", prompt, flags=re.IGNORECASE).strip()
        ooc_prompt = f"""[META CHANNEL OOC REQUEST]: The player is asking a meta/rules/lore question without taking a gameplay action: "{ooc_query}". 
Provide a clear, concise out-of-character answer explaining the mechanics, rules, or lore requested. Do NOT advance game state, trigger combat attacks, or execute gameplay actions."""
        
        with st.spinner("Accessing meta-channel..."):
            ooc_resp = call_gemini([types.Content(role="user", parts=[types.Part.from_text(text=ooc_prompt)])])
            formatted_ooc = f"""<div style="background-color: #1a1f29; border-left: 3px solid #ff3366; padding: 10px 14px; margin: 10px 0; font-family: 'Courier New', Courier, monospace; font-size: 0.8rem; color: #c5c9d1; border-radius: 4px;">
<b>💬 [OOC CLARIFICATION CHANNEL]</b><br>{ooc_resp}
</div>"""
            st.session_state.game["history"].append({"role": "model", "content": formatted_ooc, "display": True})
            st.rerun()

    st.session_state.game["history"].append({"role": "user", "content": prompt, "display": True})
    
    context = (prompt + f"\n[CURRENT STATS & INVENTORY HIDDEN]" + 
               f"\n[ENEMY SYS DATA: {json.dumps(st.session_state.game['active_enemy'])}]")
    
    api_messages = []
    for m in st.session_state.game["history"]:
        clean_text = re.sub(r"<div[^>]*>.*?\[COMBAT STATUS FEED\].*?</div>", "", m["content"], flags=re.IGNORECASE|re.DOTALL)
        api_messages.append({"role": "model" if m["role"] == "model" else "user", "parts": [{"text": clean_text}]})
        
    api_messages[-1]["parts"][0]["text"] = context

    with st.spinner("Processing feed..."):
        gm_text = call_gemini(api_messages) or ""
        raw_ai_text = gm_text # Save original output to parse tags safely
        system_execution_log = ""

        # --- PARSER: PLAYER SCAN (DIRECT PYTHON RENDER) ---
        if re.search(r"\[SCAN\]", raw_ai_text, re.IGNORECASE) and st.session_state.game.get("active_enemy"):
            enemy = st.session_state.game["active_enemy"]
            scan_stat = st.session_state.game["stats"]["scan"]
            strain = st.session_state.game["bio_strain"]
            effective_target = scan_stat - strain
            
            roll = random.randint(1, 100)
            is_success = roll <= effective_target
            result_str = "SUCCESS" if is_success else "FAILURE"
            target_name = enemy["name"].lower() if enemy.get("scanned") else "unknown hostile"
            
            roll_ui = f"""<div style="background-color: #12151a; padding: 10px 14px; margin: 10px 0; font-family: 'Courier New', Courier, monospace; font-size: 0.8rem; color: #8892b0; border-radius: 4px;">
<span style="color:#00ffcc; font-weight:bold;">[SYS_CHECK // SCAN]</span> Action: <i>Executing deep system diagnostic scan on {target_name}</i><br>
Target: {effective_target}% (Base: {scan_stat} | Strain: -{strain}%) Roll: {roll} &rarr; <b>{result_str}</b>
</div>\n\n"""
            
            if is_success:
                enemy["scanned"] = True
                scan_report = f"### 🔍 SCANNER DIAGNOSTIC ANALYSIS: {enemy['name']}\n"
                scan_report += f"**HULL HP:** `{enemy['hull_hp']}/{enemy['max_hp']}` | **WEAPON RANGE:** `{enemy['range']}`\n\n"
                scan_report += "**DETECTED SUBSYSTEMS & TARGETABLE WEAKNESSES:**\n"
                
                for idx, (slot, p) in enumerate(enemy["parts"].items(), 1):
                    stat_name = p.get('stat', 'none').upper()
                    stat_bonus = f"+{p.get('bonus', 0)}"
                    pen_name = p.get('penalty_stat', 'none').upper()
                    pen_val = p.get('penalty', 0)
                    
                    scan_report += f"{idx}. **{p['type']} ({slot.title()})**\n"
                    scan_report += f"   * *Function*: {p.get('desc', 'Standard operational component.')}\n"
                    scan_report += f"   * *Part HP*: `{p.get('hp', 0)}` | *Status*: `{p.get('status', 'Online')}`\n"
                    scan_report += f"   * *Modifiers*: `[{stat_bonus} {stat_name}, {pen_val} {pen_name}]`\n"
                    scan_report += f"   * *Targetable Weakness*: **{p['weakness']}**\n\n"
                    
                gm_text = roll_ui + scan_report # Replaces raw_ai_text entirely
            else:
                gm_text = roll_ui + "> ⚠️ **[SCAN FAILED]**: Visual sensors blinded by ambient electromagnetic interference. Diagnostic feed corrupted."

        # --- MECHANIC 1: ENVIRONMENTAL SEARCH TURN ---
        elif re.search(r"\[ENV_SEARCH\]", raw_ai_text, re.IGNORECASE) or re.search(r"\b(look around|look for|scan room|search)\b", prompt, re.IGNORECASE):
            head_part = st.session_state.game["loadout"].get("head", {})
            optics_online = head_part.get("status", "Offline") == "Online"
            
            if not optics_online:
                search_result = "> ⚠️ **[SYSTEM]: OPTICS OFFLINE. Environmental search failed. Visual sensors compromised.**"
            else:
                scan_stat = st.session_state.game["stats"]["scan"]
                strain = st.session_state.game["bio_strain"]
                effective_target = scan_stat - strain
                roll = random.randint(1, 100)
                is_success = roll <= effective_target
                
                search_header = f"""<div style="background-color: #12151a; padding: 10px 14px; margin: 10px 0; font-family: 'Courier New', Courier, monospace; font-size: 0.8rem; color: #8892b0; border-radius: 4px;">
<span style="color:#00ffcc; font-weight:bold;">[SYS_CHECK // OPTICAL SEARCH]</span> Utility Check: {effective_target}% (Roll: {roll}) &rarr; <b>{"SUCCESS" if is_success else "PARTIAL"}</b>
</div>\n\n"""
                
                search_prompt = f"""[System Execution Feedback]: The player searched the environment with the prompt: "{prompt}". 
Act strictly as a sensor suite presenting 3 contextual environmental options (with at least 1 fitting the specific prompt if items like "throw" or "pick up" were requested). Do NOT execute the secondary action or take control of the character."""
                
                api_messages.append({"role": "model", "parts": [{"text": "*Querying optical sensor suite...*"}]})
                api_messages.append({"role": "user", "parts": [{"text": search_prompt}]})
                search_narrative = call_gemini(api_messages) or ""
                search_narrative = re.sub(r"\[ENV_SEARCH\]", "", search_narrative, flags=re.IGNORECASE)
                search_result = search_header + search_narrative.strip()

            enemy = st.session_state.game.get("active_enemy")
            if enemy:
                if enemy["distance"] != "Melee" and random.random() < 0.6:
                    distances = ["Long Range", "Medium Range", "Short Range", "Melee"]
                    curr_idx = distances.index(enemy["distance"])
                    if curr_idx > 0:
                        enemy["distance"] = distances[curr_idx - 1]
                        system_execution_log += f"\n> ⚠️ **[ENEMY MOVEMENT]**: Hostile advances to {enemy['distance']} while player searches environment."
                else:
                    available_weapons = [k for k, v in enemy["parts"].items() if v.get("status") == "Online" and "base_dmg" in v]
                    if available_weapons:
                        ew = enemy["parts"][random.choice(available_weapons)]
                        dmg = random.randint(ew["base_dmg"][0], ew["base_dmg"][1])
                        st.session_state.game["hull_hp"] = max(0, st.session_state.game["hull_hp"] - dmg)
                        system_execution_log += f"\n> ⚠️ **[ENEMY STRIKE]**: Hostile exploits search delay, striking for {dmg} damage!"

            gm_text = search_result

        # --- MECHANIC 2 & 3: SPLIT ACTION ECONOMY & HAZARDS ---
        env_action_match = re.search(r"\[ENV_ACTION:\s*type=[\"']?(.*?)[\"']?,\s*object=[\"']?(.*?)[\"']?\]", raw_ai_text, re.IGNORECASE)
        if env_action_match or re.search(r"\b(throw|grab|wrench|hurl|pull|tear)\b", prompt, re.IGNORECASE):
            action_type = env_action_match.group(1).lower() if env_action_match else ("anchored" if re.search(r"wrench|tear|rip", prompt, re.IGNORECASE) else "loose")
            
            if action_type == "loose":
                reflex_stat = st.session_state.game["stats"]["reflex"]
                strain = st.session_state.game["bio_strain"]
                eff = reflex_stat - strain
                roll = random.randint(1, 100)
                success = roll <= eff
                if success:
                    system_execution_log += f"\n> ⚙️ **[REFLEX CHECK SUCCESS]**: Rapid debris grab & hurl executed successfully (Roll: {roll}/{eff}%)."
                else:
                    system_execution_log += f"\n> ⚙️ **[REFLEX CHECK FAILED]**: Debris slip or miscue during swift action (Roll: {roll}/{eff}%)."
            else:
                force_stat = st.session_state.game["stats"]["force"]
                strain = st.session_state.game["bio_strain"]
                eff = force_stat - strain
                roll = random.randint(1, 100)
                success = roll <= eff
                if success:
                    system_execution_log += f"\n> ⚙️ **[FORCE CHECK SUCCESS]**: Heavy infrastructure wrenched free from mountings (Roll: {roll}/{eff}%)."
                else:
                    system_execution_log += f"\n> ⚙️ **[FORCE CHECK FAILED]**: Infrastructure resists structural tearing; turn consumed (Roll: {roll}/{eff}%)."

        eng_match = re.search(r"\[ENGINEERING_ACTION:\s*action_type=[\"']?(.*?)[\"']?\]", raw_ai_text, re.IGNORECASE)
        if eng_match or re.search(r"\b(cut chain|spill|valve|hazard|oil slick)\b", prompt, re.IGNORECASE):
            has_welder = any("Welder" in p.get("name", "") or "Tool" in p.get("name", "") for p in st.session_state.game["loadout"].values() if isinstance(p, dict))
            if has_welder:
                st.session_state.game["active_enemy"]["hazard_zone"] = True
                system_execution_log += f"\n> ⚙️ **[ENGINEERING PROTOCOL]**: Tool detected. Hazard zone successfully established automatically without random roll."
            else:
                system_execution_log += f"\n> ⚙️ **[ENGINEERING PROTOCOL]**: Appropriate engineering tool required for deterministic deployment."

        # --- ATTACK PARSER ---
        attack_match = re.search(r"\[ATTACK:\s*weapon=[\"']?(.*?)[\"']?,\s*target_part=[\"']?(.*?)[\"']?,\s*disable_attempt=(True|False)\]", raw_ai_text, re.IGNORECASE)
        if attack_match and st.session_state.game.get("active_enemy"):
            weapon_slot = attack_match.group(1).lower()
            target_slot = attack_match.group(2).lower()
            is_disable = attack_match.group(3).lower() == "true"
            
            if weapon_slot not in st.session_state.game["loadout"]: weapon_slot = "right_arm"
            if target_slot not in st.session_state.game["active_enemy"]["parts"]: target_slot = "head"
            
            weapon = st.session_state.game["loadout"][weapon_slot]
            enemy = st.session_state.game["active_enemy"]
            target_part = enemy["parts"][target_slot]
            
            if weapon.get("status") != "Online":
                follow_up = f"[System Execution]: FAILED. The {weapon['name']} is Offline/Destroyed."
            elif RANGE_VALS.get(weapon.get("range", "Melee"), 1) < RANGE_VALS.get(enemy.get("distance", "Melee"), 1):
                follow_up = f"[System Execution]: FAILED. Weapon range cannot reach target at {enemy.get('distance')}."
            else:
                base_stat = st.session_state.game["stats"][weapon.get("scaling_stat", "force")]
                strain = st.session_state.game["bio_strain"]
                precision_penalty = 10 if is_disable else 0
                effective_target = base_stat - strain - precision_penalty
                hit_roll = random.randint(1, 100)
                is_hit = hit_roll <= effective_target
                
                if is_hit:
                    base_dmg = random.randint(weapon.get("damage", [5, 10])[0], weapon.get("damage", [5, 10])[1])
                    total_dmg = base_dmg + (base_stat // 10)
                    enemy["hull_hp"] = max(0, enemy["hull_hp"] - total_dmg)
                    target_part["hp"] = max(0, target_part["hp"] - total_dmg)
                    follow_up = f"[System Execution]: HIT! Dealt {total_dmg} damage to {target_slot.upper()}."
                else:
                    follow_up = f"[System Execution]: MISS! Strike failed (Roll: {hit_roll}/{effective_target}%)."
            
            system_execution_log += f"\n> 💥 **{follow_up}**"
            gm_text = "*Combat protocol engaged...*"
            api_messages.append({"role": "model", "parts": [{"text": gm_text}]})
            api_messages.append({"role": "user", "parts": [{"text": follow_up}]})
            gm_text += "\n\n" + (call_gemini(api_messages) or "")

        # --- ENEMY ATTACK & UNIVERSAL ENEMY ROLL SYSTEM ---
        e_attack_match = re.search(r"\[ENEMY_ATTACK:\s*weapon=[\"']?(.*?)[\"']?\]", raw_ai_text, re.IGNORECASE)
        if e_attack_match and st.session_state.game.get("active_enemy"):
            enemy = st.session_state.game["active_enemy"]
            
            if enemy.get("hazard_zone", False):
                stability_roll = random.randint(1, 100)
                enemy_stability_stat = 60
                if stability_roll > enemy_stability_stat:
                    system_execution_log += f"\n> ⚠️ **[ENEMY ROLL SYSTEM]**: Hostile failed Stability check ({stability_roll}/{enemy_stability_stat}%) navigating hazard zone, slipping and losing attack momentum!"
                    follow_up = "[System Execution]: Enemy slipped on hazard zone and forfeited attack."
                else:
                    system_execution_log += f"\n> ⚠️ **[ENEMY ROLL SYSTEM]**: Hostile passed Stability check ({stability_roll}/{enemy_stability_stat}%) across hazard zone."
            
            available_weapons = [
                k for k, v in enemy["parts"].items() 
                if v.get("status") == "Online" and "base_dmg" in v and RANGE_VALS.get(v.get("range", "Melee"), 1) >= RANGE_VALS.get(enemy.get("distance", "Melee"), 1)
            ]
            
            if available_weapons:
                weapon_slot = random.choice(available_weapons)
                enemy_weapon = enemy["parts"][weapon_slot]
                enemy_roll = random.randint(1, 100)
                enemy_accuracy_target = 65
                if enemy_roll <= enemy_accuracy_target:
                    dmg = random.randint(enemy_weapon["base_dmg"][0], enemy_weapon["base_dmg"][1])
                    st.session_state.game["hull_hp"] = max(0, st.session_state.game["hull_hp"] - dmg)
                    follow_up = f"[System Execution]: Enemy attack connected (Roll {enemy_roll} vs {enemy_accuracy_target}%), dealing {dmg} damage with {enemy_weapon['type']}!"
                else:
                    follow_up = f"[System Execution]: Enemy attack missed (Roll {enemy_roll} vs {enemy_accuracy_target}%)."
            else:
                follow_up = "[System Execution]: Enemy has no online weapons in range."
                
            system_execution_log += f"\n> ⚠️ **{follow_up}**"
            gm_text = "*Warning: Incoming hostile action...*"
            api_messages.append({"role": "model", "parts": [{"text": gm_text}]})
            api_messages.append({"role": "user", "parts": [{"text": follow_up}]})
            gm_text += "\n\n" + (call_gemini(api_messages) or "")

        prox_match = re.search(r"\[PROXIMITY_UPDATE:\s*(.*?)\]", raw_ai_text, re.IGNORECASE)
        if prox_match and st.session_state.game.get("active_enemy"):
            st.session_state.game["active_enemy"]["distance"] = prox_match.group(1).strip().title()

        gm_text += system_execution_log

        # --- SALVAGE ASSESSMENT ---
        active_enemy = st.session_state.game.get("active_enemy")
        if active_enemy and active_enemy.get("hull_hp", 0) <= 0:
            loot_log = "\n\n> ⚙️ **[TACTICAL SALVAGE ASSESSMENT]**\n"
            for p_key, p_val in active_enemy["parts"].items():
                if p_val["status"] == "Destroyed":
                    if random.random() < 0.3:
                        st.session_state.game["inventory"]["scrap"] += 1
                        loot_log += f"> * {p_key.upper()} ({p_val['type']}) -> DESTROYED -> Extracting 1x Raw Scrap.\n"
                    else:
                        loot_log += f"> * {p_key.upper()} ({p_val['type']}) -> DESTROYED -> Unsalvageable.\n"
                else: 
                    salvaged_part = {
                        "name": p_val["type"],
                        "scaling_stat": p_val.get("stat", "force"),
                        "stat_bonus": p_val.get("bonus", 5),
                        "hp": p_val.get("hp", 30),
                        "status": "Online",
                        "range": p_val.get("range", "Melee"),
                        "damage": p_val.get("base_dmg", [5, 10]),
                        "strain_cost": p_val.get("strain_cost", 0)
                    }
                    st.session_state.game["inventory"]["parts"].append(salvaged_part)
                    loot_log += f"> * {p_key.upper()} ({p_val['type']}) -> INTACT -> **Added to Cargo!**\n"
            
            st.session_state.game["active_enemy"] = None
            gm_text += loot_log
            
            st.session_state.game["rooms_cleared"] += 1
            if st.session_state.game["rooms_cleared"] % 3 == 0:
                st.session_state.game["is_safe_room"] = True
                gm_text += "\n\n> 🛡️ **[SYSTEM]: AREA SECURE. ADVANCING TO BIO-FORGE SAFE ROOM.**"
            else:
                new_enemy = generate_enemy(st.session_state.game["campaign_depth"])
                st.session_state.game["active_enemy"] = new_enemy
                gm_text += f"\n\n> 🚪 **[SYSTEM]: PROCEEDING TO NEXT ZONE. TARGET ACQUIRED.**"

        gm_text = re.sub(r"\[THREAT_LOG:.*?\]", "", gm_text, flags=re.IGNORECASE)
        gm_text = re.sub(r"\[PROXIMITY_UPDATE:.*?\]", "", gm_text, flags=re.IGNORECASE)
        gm_text = re.sub(r"<div[^>]*>.*?\[COMBAT STATUS FEED\].*?</div>", "", gm_text, flags=re.IGNORECASE|re.DOTALL)

        if st.session_state.game.get("active_enemy"):
            enemy = st.session_state.game["active_enemy"]
            d_name = enemy["name"] if enemy["scanned"] else "UNKNOWN HOSTILE"
            l_arm_name = st.session_state.game['loadout']['left_arm']['name']
            r_arm_name = st.session_state.game['loadout']['right_arm']['name']
            e_dist = enemy["distance"]
            
            actions = []
            if not enemy.get("scanned", False): actions.append("🔍 **SCAN**")
            actions.extend(["⚔️ **ATTACK**", "👁️ **LOOK AROUND**", "🏃 **ADVANCE**", "🏃 **RETREAT**", "👻 **HIDE**"])
            action_str = " | ".join(actions)
            
            combat_ui_block = f"""
<div style="background-color: #12151a; border-left: 3px solid #00ffcc; padding: 10px 14px; margin: 10px 0; font-family: 'Courier New', Courier, monospace; font-size: 0.8rem; color: #c5c9d1; border-radius: 4px;">
    <b>⚔️ [COMBAT STATUS FEED]</b><br>
    <b>TARGET:</b> {d_name} | HULL: {enemy['hull_hp']}/{enemy['max_hp']} | RANGE: {enemy['range']}<br>
    <b>TARGET PROXIMITY:</b> {e_dist}<br>
    <b>SUGGESTED ACTIONS:</b> {action_str}
</div>
"""
            gm_text += "\n" + combat_ui_block

        st.session_state.game["history"].append({"role": "model", "content": gm_text, "display": True})
        st.rerun()

# -----------------------------------------------------------------------------
# 9. RENDER MESSAGES & SAFE ROOM UI
# -----------------------------------------------------------------------------
for msg in st.session_state.game["history"]:
    if msg.get("display", True):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

if st.session_state.game.get("is_safe_room"):
    render_safe_room()
