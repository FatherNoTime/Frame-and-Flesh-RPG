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
        {"type": "Targeting Core", "stat": "scan", "bonus": 15, "penalty_stat": "stability", "penalty": -5, "hp": 25, "status": "Online", "weakness": "Exposed optics crack under kinetic impact.", "strain_cost": 0},
    ],
    "legs": [
        {"type": "Industrial Treads", "stat": "stability", "bonus": 15, "penalty_stat": "reflex", "penalty": -15, "hp": 40, "status": "Online", "weakness": "Tread links can be jammed by debris.", "strain_cost": 0},
    ],
    "arms": [
        {"type": "Hydraulic Pincer", "stat": "force", "bonus": 10, "penalty_stat": "reflex", "penalty": -5, "range": "Melee", "base_dmg": [12, 18], "hp": 30, "status": "Online", "weakness": "Hydraulic lines exposed at the joint.", "strain_cost": 0},
        {"type": "Flak Shotgun", "stat": "force", "bonus": 10, "penalty_stat": "reflex", "penalty": -5, "range": "Short Range", "base_dmg": [14, 22], "hp": 25, "status": "Online", "weakness": "Ammunition feed prone to jams.", "strain_cost": 0},
        {"type": "Laser Emitter", "stat": "reflex", "bonus": 15, "penalty_stat": "stability", "penalty": -10, "range": "Long Range", "base_dmg": [10, 18], "hp": 20, "status": "Online", "weakness": "Cooling vents easily disrupted.", "strain_cost": 0},
        {"type": "Fleshed-Over Autocannon", "stat": "force", "bonus": 20, "penalty_stat": "reflex", "penalty": -10, "range": "Medium Range", "base_dmg": [22, 35], "hp": 45, "status": "Online", "weakness": "Pulsing bio-sacs burst easily under scan-assisted fire.", "strain_cost": 15}
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
# 4. HUD & MENU CONTAINER (WITH CHARACTER SHEET & CONSUMABLES)
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
# 5. SYSTEM INSTRUCTIONS & FAST GEMINI API HELPER
# -----------------------------------------------------------------------------
SYS_INSTRUCT = """You are a Strict, immersive GM for a grimdark sci-fi/body-horror TTRPG titled 'FRAME & FLESH'.

COMBAT EXECUTION (MANDATORY):
You DO NOT calculate damage or track enemy HP. Python handles the math. Parts can be targeted.
1. When PLAYER scans: Output `[SCAN]` and STOP. Do this if they attempt to analyze, observe, or detect weaknesses.
2. When PLAYER attacks: Output `[ATTACK: weapon="right_arm", target_part="head", disable_attempt=False]` and STOP. 
   - CRITICAL RULE: The player has no UI buttons. You must act as the semantic parser. If the player's narrative text explicitly describes aiming at a specific part's known 'weakness' (e.g., "I shoot the exposed hydraulic lines" or "I smash the cracked visor"), you MUST set disable_attempt=True. If they just say "I attack the head" or do not mention the weakness, set it to False.
3. When ENEMY attacks: Output `[ENEMY_ATTACK: weapon="left_arm"]` and STOP.

AUTOMATED LOGGING TAGS (Place on a new line at the end):
- [PROXIMITY_UPDATE: <Distance>] -> Output ONLY if physical distance changes (Melee, Short Range, Medium Range, Long Range).
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

*[Loading] Initializing neural link... Airlock cycling...*
"""
    st.session_state.game["history"].append({"role": "model", "content": tutorial_text, "display": True})
    
    kickoff_prompt = f"""
[SYSTEM INJECTION]: The game has started. The player is stepping into the Sub-level 3 Docking Bay. 
Python has generated the first enemy: a mechanical horror built with a {first_enemy['parts']['head']['type']}, {first_enemy['parts']['legs']['type']}, {first_enemy['parts']['left_arm']['type']}, and {first_enemy['parts']['right_arm']['type']}.

YOUR TASK:
Write the opening scene response.
1. Describe the opening room (Sub-level 3 Docking Bay) in vivid detail—the atmosphere, architecture, lighting, hazards, and potential interactables as the airlock cycles open.
2. Describe the hostile enemy lurking within this room. Give it a terrifying military designation/name based on its threat profile. YOU MUST ALSO include a line containing the exact tag `[THREAT_LOG: <Designation Name> | <Short Description>]` at the very end of your response so the system can catalog it.
CRITICAL RULE: Do NOT explicitly list its numerical stats or raw blueprint part names. Describe its visual silhouette, physical scale, and movement behavior based on its parts. End by asking the player for their first course of action.
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
                gm_text = re.sub(r"\[TIMELINE_LOG:.*?\]", "", gm_text, flags=re.IGNORECASE)
                gm_text = re.sub(r"\[LORE_LOG:.*?\]", "", gm_text, flags=re.IGNORECASE)
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
                    
                    # Filter Actions Conditionally
                    actions = []
                    if not is_scanned: 
                        actions.append("🔍 **SCAN** (Unscanned Target)")
                        
                    has_valid_attack = any(
                        v.get("status") == "Online" and "damage" in v and RANGE_VALS.get(v.get("range", "Melee"), 1) >= RANGE_VALS.get(e_dist, 1)
                        for v in st.session_state.game["loadout"].values() if isinstance(v, dict)
                    )
                    if has_valid_attack:
                        actions.append("⚔️ **ATTACK**")
                        
                    enemy_in_range = any(
                        p.get("status") == "Online" and "base_dmg" in p and RANGE_VALS.get(p.get("range", "Melee"), 1) >= RANGE_VALS.get(e_dist, 1)
                        for p in active_enemy["parts"].values() if isinstance(p, dict)
                    )
                    if enemy_in_range:
                        actions.extend(["💨 **DODGE**", "🛡️ **BRACE**"])
                        
                    actions.extend(["🏃 **ADVANCE**", "🏃 **RETREAT**", "👻 **HIDE**"])
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
# 8. INPUT HANDLING, PARSING & LOOT LOOPS
# -----------------------------------------------------------------------------
if prompt := st.chat_input("Type your action..."):
    if not st.session_state.api_key:
        st.error("Missing API Key.")
        st.stop()
        
    st.session_state.game["history"].append({"role": "user", "content": prompt, "display": True})
    
    context = (prompt + f"\n[CURRENT STATS & INVENTORY HIDDEN]" + 
               f"\n[ENEMY SYS DATA: {json.dumps(st.session_state.game['active_enemy'])}]")
    
    api_messages = [{"role": "model" if m["role"] == "model" else "user", "parts": [{"text": m["content"]}]} for m in st.session_state.game["history"]]
    api_messages[-1]["parts"][0]["text"] = context

    with st.spinner("Processing feed..."):
        gm_text = call_gemini(api_messages)
        if not gm_text: st.stop()
        
        system_execution_log = ""

        # --- PARSER: PLAYER SCAN ---
        if re.search(r"\[SCAN\]", gm_text, re.IGNORECASE) and st.session_state.game.get("active_enemy"):
            enemy = st.session_state.game["active_enemy"]
            effective_target = st.session_state.game["stats"]["scan"] - st.session_state.game["bio_strain"]
            
            if random.randint(1, 100) <= effective_target:
                enemy["scanned"] = True
                follow_up = f"[System Execution]: SCAN SUCCESSFUL (Target Roll: {effective_target}%). Enemy weaknesses logged. Precision targeting enabled."
            else:
                follow_up = f"[System Execution]: SCAN FAILED (Target Roll: {effective_target}%). Interference detected."
            
            system_execution_log += f"\n> 🔍 **{follow_up}**"
            gm_text = "*Scanning sequence engaged...*"
            api_messages.append({"role": "model", "parts": [{"text": gm_text}]})
            api_messages.append({"role": "user", "parts": [{"text": follow_up}]})
            gm_text += "\n\n" + (call_gemini(api_messages) or "")

        # --- PARSER: PLAYER ATTACK ---
        attack_match = re.search(r"\[ATTACK:\s*weapon=[\"']?(.*?)[\"']?,\s*target_part=[\"']?(.*?)[\"']?,\s*disable_attempt=(True|False)\]", gm_text, re.IGNORECASE)
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
                follow_up = f"[System Execution]: FAILED. Weapon range ({weapon.get('range')}) cannot reach target at {enemy.get('distance')}."
            else:
                base_stat = st.session_state.game["stats"][weapon.get("scaling_stat", "force")]
                strain = st.session_state.game["bio_strain"]
                
                precision_penalty = 0
                if is_disable:
                    precision_penalty += 10
                    if weapon.get("scaling_stat", "force") == "force":
                        precision_penalty += 10
                
                effective_target = base_stat - strain - precision_penalty
                hit_roll = random.randint(1, 100)
                is_hit = hit_roll <= effective_target
                
                if is_hit:
                    base_dmg = random.randint(weapon.get("damage", [5, 10])[0], weapon.get("damage", [5, 10])[1])
                    stat_mod = base_stat // 10
                    total_dmg = base_dmg + stat_mod
                    
                    if is_disable and enemy["scanned"]:
                        part_dmg = int(total_dmg * 1.2)
                        hull_dmg = int(total_dmg * 0.7)
                    else:
                        part_dmg = total_dmg
                        hull_dmg = total_dmg
                        
                    enemy["hull_hp"] = max(0, enemy["hull_hp"] - hull_dmg)
                    target_part["hp"] = max(0, target_part["hp"] - part_dmg)
                    
                    if target_part["hp"] == 0:
                        target_part["status"] = "Disabled" if (is_disable and enemy["scanned"]) else "Destroyed"
                        follow_up = f"[System Execution]: PRECISION HIT! {part_dmg} dmg to part. {target_slot.upper()} IS NOW {target_part['status'].upper()}!"
                    else:
                        follow_up = f"[System Execution]: HIT! Dealt {hull_dmg} hull dmg and {part_dmg} part dmg to {target_slot.upper()} (Target Roll was {effective_target}% with a -{precision_penalty}% precision modifier)."
                else:
                    follow_up = f"[System Execution]: MISS! Strike failed to connect against target {effective_target}%."
            
            system_execution_log += f"\n> 💥 **{follow_up}**"
            gm_text = "*Combat protocol engaged...*"
            api_messages.append({"role": "model", "parts": [{"text": gm_text}]})
            api_messages.append({"role": "user", "parts": [{"text": follow_up}]})
            gm_text += "\n\n" + (call_gemini(api_messages) or "")

        # --- PARSER: ENEMY ATTACK ---
        e_attack_match = re.search(r"\[ENEMY_ATTACK:\s*weapon=[\"']?(.*?)[\"']?\]", gm_text, re.IGNORECASE)
        if e_attack_match and st.session_state.game.get("active_enemy"):
            enemy = st.session_state.game["active_enemy"]
            
            available_weapons = [
                k for k, v in enemy["parts"].items() 
                if v.get("status") == "Online" and "base_dmg" in v and RANGE_VALS.get(v.get("range", "Melee"), 1) >= RANGE_VALS.get(enemy.get("distance", "Melee"), 1)
            ]
            
            if not available_weapons:
                follow_up = "[System Execution]: Enemy attempted to attack but has no online weapons in range. It must reposition."
            else:
                weapon_slot = random.choice(available_weapons)
                enemy_weapon = enemy["parts"][weapon_slot]
                dmg = random.randint(enemy_weapon["base_dmg"][0], enemy_weapon["base_dmg"][1])
                st.session_state.game["hull_hp"] = max(0, st.session_state.game["hull_hp"] - dmg)
                follow_up = f"[System Execution]: Enemy hits for {dmg} damage with {enemy_weapon['type']}!"
                
            system_execution_log += f"\n> ⚠️ **{follow_up}**"
            gm_text = "*Warning: Incoming hostile action...*"
            api_messages.append({"role": "model", "parts": [{"text": gm_text}]})
            api_messages.append({"role": "user", "parts": [{"text": follow_up}]})
            gm_text += "\n\n" + (call_gemini(api_messages) or "")

        # --- INVISIBLE LOGGING AND PROXIMITY EXTRACTION ---
        prox_match = re.search(r"\[PROXIMITY_UPDATE:\s*(.*?)\]", gm_text, re.IGNORECASE)
        if prox_match and st.session_state.game.get("active_enemy"):
            st.session_state.game["active_enemy"]["distance"] = prox_match.group(1).strip().title()
            gm_text = gm_text.replace(prox_match.group(0), "").strip()

        # Merge System Logs into the output so they persist in history
        gm_text += system_execution_log

        # --- TACTICAL SALVAGE ASSESSMENT (POST COMBAT) ---
        active_enemy = st.session_state.game.get("active_enemy")
        if active_enemy and active_enemy.get("hull_hp", 0) <= 0:
            follow_up = "[System Execution]: TARGET NEUTRALIZED. TACTICAL SALVAGE ASSESSMENT INITIATED."
            gm_text += f"\n> ⚙️ **{follow_up}**"
            
            loot_log = "\n\n> ⚙️ **[TACTICAL SALVAGE ASSESSMENT]**\n"
            for p_key, p_val in active_enemy["parts"].items():
                if p_val["status"] == "Destroyed":
                    if random.random() < 0.3:
                        st.session_state.game["inventory"]["scrap"] += 1
                        loot_log += f"> * {p_key.upper()} ({p_val['type']}) -> STATUS: DESTROYED -> Extracting 1x Raw Scrap.\n"
                    else:
                        loot_log += f"> * {p_key.upper()} ({p_val['type']}) -> STATUS: DESTROYED -> Unsalvageable.\n"
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
                    loot_log += f"> * {p_key.upper()} ({p_val['type']}) -> STATUS: SALVAGEABLE -> **Intact Part Added to Cargo!**\n"
            
            st.session_state.game["active_enemy"] = None
            gm_text += loot_log
            
            # Room Progression and Safe Room Check
            st.session_state.game["rooms_cleared"] += 1
            if st.session_state.game["rooms_cleared"] % 3 == 0:
                st.session_state.game["is_safe_room"] = True
                gm_text += "\n\n> 🛡️ **[SYSTEM EXECUTION]: AREA SECURE. ADVANCING TO BIO-FORGE SAFE ROOM.**"
            else:
                new_enemy = generate_enemy(st.session_state.game["campaign_depth"])
                st.session_state.game["active_enemy"] = new_enemy
                gm_text += f"\n\n> 🚪 **[SYSTEM EXECUTION]: PROCEEDING TO NEXT ZONE. TARGET ACQUIRED: {new_enemy['parts']['head']['type']} / {new_enemy['parts']['left_arm']['type']}**"

        # COMBAT UI RENDERING
        if st.session_state.game.get("active_enemy"):
            enemy = st.session_state.game["active_enemy"]
            d_name = enemy["name"] if enemy["scanned"] else "UNKNOWN HOSTILE"
            
            l_arm_name = st.session_state.game['loadout']['left_arm']['name']
            r_arm_name = st.session_state.game['loadout']['right_arm']['name']
            e_dist = enemy["distance"]
            
            actions = []
            if not enemy.get("scanned", False): 
                actions.append("🔍 **SCAN** (Unscanned Target)")
                
            has_valid_attack = any(
                v.get("status") == "Online" and "damage" in v and RANGE_VALS.get(v.get("range", "Melee"), 1) >= RANGE_VALS.get(e_dist, 1)
                for v in st.session_state.game["loadout"].values() if isinstance(v, dict)
            )
            if has_valid_attack:
                actions.append("⚔️ **ATTACK**")
                
            enemy_in_range = any(
                p.get("status") == "Online" and "base_dmg" in p and RANGE_VALS.get(p.get("range", "Melee"), 1) >= RANGE_VALS.get(e_dist, 1)
                for p in enemy["parts"].values() if isinstance(p, dict)
            )
            if enemy_in_range:
                actions.extend(["💨 **DODGE**", "🛡️ **BRACE**"])
                
            actions.extend(["🏃 **ADVANCE**", "🏃 **RETREAT**", "👻 **HIDE**"])
            action_str = " | ".join(actions)
            
            combat_ui_block = f"""
<div style="background-color: #12151a; border-left: 3px solid #00ffcc; padding: 10px 14px; margin: 10px 0; font-family: 'Courier New', Courier, monospace; font-size: 0.8rem; color: #c5c9d1; border-radius: 4px;">
    <b>⚔️ [COMBAT STATUS FEED]</b><br>
    <b>TARGET:</b> {d_name} | HULL: {e_hp}/{e_max} | WEAPON RANGE: {c_range}<br>
    <b>TARGET PROXIMITY:</b> {e_dist}<br>
    <b>USER FRAME SYSTEMS:</b> R-Arm: {r_arm_name} | L-Arm: {l_arm_name}<br>
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
