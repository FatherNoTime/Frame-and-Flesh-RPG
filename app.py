import re
import json
import os
import io
from PIL import Image
import streamlit as st
from google import genai
from google.genai import types

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & MOBILE-FRIENDLY CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="FRAME & FLESH", layout="centered")

# Custom CSS for Dark Gritty Theme, Unified Fixed Top HUD, & Unobstructed Bottom Input
st.markdown("""
    <style>
    /* Global Theme */
    .stApp { background-color: #0a0b0d; color: #c5c9d1; font-family: 'Courier New', Courier, monospace; }
    
    /* Completely hide Streamlit default header, footer, sidebar elements, and deployment toolbar */
    [data-testid="stHeader"], footer, [data-testid="stToolbar"], [data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* Unified Fixed Top HUD Container */
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
    
    /* Make the Popover Menu Button ~20% smaller */
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
    
    /* Pad the main container so content clears the fixed HUD at the top and chat input at the bottom */
    .block-container {
        padding-top: 95px !important;
        padding-bottom: 110px !important;
    }
    
    /* Fix chat input container so it never gets cut off or overlapped */
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
    
    /* Highlight Colors */
    .hp-text { color: #00ffcc; font-weight: bold; }
    .strain-text { color: #ff3366; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. STATE INITIALIZATION & GHOST TRACKER
# -----------------------------------------------------------------------------
if "game" not in st.session_state:
    st.session_state.game = {
        "hull_hp": 100,
        "bio_strain": 0,
        "inventory": "2x Bio-Sutures, 1x Emergency Coolant Injector, Field Engineer Toolkit",
        "bestiary": "No enemy units scanned yet.",
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
    "erebus": "Black-Site Erebus: Subterranean military research facility. Command claimed all staff evacuated prior to the blackout. Infrastructure appears secure and standard.",
    "splicer": "Mark-1 Splicer Frame: Your mech. Field-engineering variant. Equipped with a back-mounted Blueprint Scanner and reinforced hydraulic limbs for salvage.",
    "neural loom": "Neural Loom: The spinal harness connecting your nervous system to the mech. Splicing incompatible/organic parts causes severe psychological shock.",
    "command": "Command: The military brass that deployed you. They asserted a clean, total evacuation.",
    "scanner": "High-Fidelity Blueprint Scanner: Penetrates chassis plating to reveal internal mechanics, weak points, and biological signatures."
}

def get_lore(text):
    """Injects lore only if the player mentions specific keywords."""
    found_lore = [desc for key, desc in LOREBOOK.items() if key in text.lower()]
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
                <span style="color: #667080; letter-spacing: 0.5px;">OPERATIONAL STATUS // SUBJECT 09</span>
                <span>HULL: <span class="hp-text">{st.session_state.game['hull_hp']}/100</span> | STRAIN: <span class="strain-text">{st.session_state.game['bio_strain']}%</span></span>
            </div>
            <div style="font-size: 0.65rem; color: #8892b0; margin-top: 2px; word-break: break-word;">INV: {st.session_state.game['inventory']}</div>
        """, unsafe_allow_html=True)
        
    with col_btn:
        with st.popover("⚙️ SYS_MENU", use_container_width=True):
            st.title("SYS_CONFIG")
            st.session_state.api_key = st.text_input("Gemini API Key", type="password", value=st.session_state.api_key)
            
            st.markdown("---")
            st.subheader("FIELD LOREBOOK")
            
            # Expandable Bestiary Rollout
            with st.expander("⚙️ Bestiary & Mechs", expanded=False):
                st.markdown(st.session_state.game.get("bestiary", "No units cataloged."))
                
            # Expandable Timeline Rollout
            with st.expander("⏳ Timeline Summary", expanded=False):
                st.markdown(st.session_state.game.get("timeline", "No events recorded."))
                
            # Expandable Lore Notes Rollout
            with st.expander("📝 Lore Notes & Secrets", expanded=False):
                st.markdown(st.session_state.game.get("lore_notes", "No notes recorded."))

            st.markdown("---")
            
            # App Management Expander
            with st.expander("🛠️ App Management", expanded=False):
                st.markdown("Access cloud dashboard to manage app settings, logs, and deployment controls.")
                st.link_button("Open Streamlit Dashboard", "https://share.streamlit.io/")

            st.markdown("---")
            
            # Save/Load Management Expander
            with st.expander("💾 Save / Load Manager", expanded=False):
                st.markdown("### Save/Load File")
                
                safe_game_data = st.session_state.game.copy()
                safe_history = []
                for msg in safe_game_data.get("history", []):
                    msg_copy = msg.copy()
                    msg_copy["image"] = None
                    safe_history.append(msg_copy)
                safe_game_data["history"] = safe_history

                save_json = json.dumps(safe_game_data, indent=4)
                st.download_button(
                    label="Export Save",
                    data=save_json,
                    file_name="frame_and_flesh_save.json",
                    mime="application/json"
                )
                
                uploaded_save = st.file_uploader("Import Save", type=["json"])
                if uploaded_save is not None:
                    try:
                        loaded_data = json.load(uploaded_save)
                        st.session_state.game = loaded_data
                        st.success("Save loaded successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Invalid save file: {e}")

                st.markdown("---")
                st.markdown("### Save/Load Cloud")
                
                col_cloud1, col_cloud2 = st.columns(2)
                with col_cloud1:
                    if st.button("Save"):
                        try:
                            with open("cloud_save.json", "w") as f:
                                json.dump(safe_game_data, f)
                            st.success("Saved!")
                        except Exception as e:
                            st.error(f"Failed: {e}")
                            
                with col_cloud2:
                    if st.button("Load"):
                        if os.path.exists("cloud_save.json"):
                            try:
                                with open("cloud_save.json", "r") as f:
                                    st.session_state.game = json.load(f)
                                st.success("Loaded!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")
                        else:
                            st.warning("No cloud save found.")

# -----------------------------------------------------------------------------
# 5. SYSTEM INSTRUCTIONS (The GM Persona & Pacing)
# -----------------------------------------------------------------------------
SYS_INSTRUCT = """You are a Strict, immersive GM for a grimdark sci-fi/body-horror TTRPG titled 'FRAME & FLESH'.
The Player is a military field engineer injured in battle, piloting a repurposed mech equipped with a blueprint scanner and salvage tools.

STORY PREMISE & COMMAND'S LIE:
Command explicitly told the Player that all human personnel safely evacuated Black-Site Erebus before the blackout. THIS IS A LIE. Trapped staff were harvested by the AI.

STRICT CAMPAIGN PACING:
1. BOSSES 1-3 (PURE MECHANICAL): Enemies are strictly autonomous industrial mechs. ABSOLUTELY NO BIOLOGICAL ELEMENTS YET. 
   - CRITICAL RULE FOR BOSSES 1-3: The facility must appear entirely normal and abandoned as Command claimed. DO NOT describe any doors welded shut from the inside, structural deformation, bloodless surgical bays, or warning signs until AFTER the third boss is defeated.
2. POST-BOSS 3 (BIO-HYBRID REVELATION): The AI introduces rare bio-mechs using human limbs and nervous tissue, and the horrific truth of the welded doors/trapped staff is uncovered. 
3. PSYCHOLOGICAL BIO-STRAIN: Grafting biological parts causes severe psychological feedback (memory bleeds, auditory hallucinations, UI glitches).

SCANNER & BLUEPRINT DIRECTIVES:
When the Player uses their Scanner on an enemy, output a narrative breakdown: Overall Unit Description, Parts Listing (Function, Ammo, Weak Points), and Scrappable Status.

SAFE ROOMS & CRAFTING:
When the player enters a Safe Room, present 2 to 3 logical, atmospheric crafting or repair options based on their current inventory. Do not resolve the action until they write their choice.

AUTOMATED CAMPAIGN LOGGING (MANDATORY):
At the end of your turn, whenever a mech is scanned, an important plot event occurs, or lore/environmental secrets are discovered, output the relevant tracking tags:
[STATE_UPDATE: HP=100, STRAIN=0, INV=Item 1, Item 2]
[BESTIARY_LOG: Unit Name - Capabilities, Weak Points, Scrappable Status]
[TIMELINE_LOG: Brief summary of the event that just occurred]
[LORE_LOG: Important plot revelation or environmental discovery]
(Omit any log tags if nothing significant changed that turn).

NANO-BANANA BLUEPRINT PROMPT (MANDATORY ON SCAN):
Whenever the player scans an enemy unit, you MUST include this exact tag at the very end of your response:
[NANO-BANANA PROMPT]: A stark concept blueprint of [Detailed Mech Description], brilliant white lines on a solid black background, highly detailed schematic layout, clearly showing the full figure, absolutely no text, no labels, no typography."""

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
        "* **Physical Status:** Recovering from critical battlefield trauma. Synthetic neural-loom interface surgically integrated, directly knitting your spine and nervous system into the core mechanics of a heavy-duty Splicer Frame. Every shift of the chassis sends sharp, metallic feedback up your central nervous system.\n"
        "* **Current Location:** Sealed inside the airlock of the Sub-level 3 Docking Bay. Local comms are choked with a dead ocean of static.\n\n"
        "---\n\n"
        "**MISSION BRIEFING // COMMAND SEC-COMMS**\n"
        "* **Target:** Black-Site Erebus Subterranean Complex.\n"
        "* **Situation:** Catastrophic grid blackout and lockdown.\n"
        "* **Personnel Status:** All human personnel were safely evacuated prior to the lockdown.\n"
        "* **Resistance Expected:** Low-level automated industrial security and maintenance drones only.\n"
        "* **Mission Goal:** Access Sub-level 3, repair the facility system control nodes, and lift the lockdown.\n\n"
        "---\n\n"
        "The airlock hisses shut, severing the howl of the surface wind. Emergency red strobes cut through the gloom of Sub-level 3, casting long, fractured shadows across oil-slicked grating.\n\n"
        "Fifty feet down the gantry, a four-legged industrial drone pauses its work. It is a heavy-duty loader class, its hydraulics whining as it crushes a steel shipping crate. A bright blue welding torch flickers at the end of its primary manipulator arm. It slowly pivots its optic cluster toward you.\n\n"
        "What do you do, Engineer?"
    )
    st.session_state.game["history"].append({"role": "model", "content": initial_gm, "image": None, "display": True})

# Render Chat History
for msg in st.session_state.game["history"]:
    if msg.get("display", True):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("image"):
                st.image(msg["image"], caption="BLUEPRINT SCAN COMPLETE", use_container_width=True)

# -----------------------------------------------------------------------------
# 7. INPUT HANDLING & API CALLS
# -----------------------------------------------------------------------------
if prompt := st.chat_input("Type your action..."):
    if not st.session_state.api_key:
        st.error("Please enter your Gemini API key in the SYS_MENU popover.")
        st.stop()
        
    # 1. Display User Message
    st.session_state.game["history"].append({"role": "user", "content": prompt, "display": True})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Inject Lore, Inventory, and Logs into Context
    context_injected_prompt = (
        prompt + 
        get_lore(prompt) + 
        f"\n[CURRENT INVENTORY: {st.session_state.game['inventory']}]" +
        f"\n[ACTIVE BESTIARY: {st.session_state.game['bestiary']}]" +
        f"\n[TIMELINE: {st.session_state.game['timeline']}]" +
        f"\n[LORE NOTES: {st.session_state.game['lore_notes']}]"
    )
    
    # 3. Build API messages with correct Role/Parts structure
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

    # 4. Call Gemini with Comprehensive Fallback Logic
    client = genai.Client(api_key=st.session_state.api_key)
    
    model_chain = [
        "gemini-3.1-pro-preview",
        "gemini-3.5-flash",
        "gemini-2.5-pro"
    ]
    
    response = None
    
    with st.spinner("Processing feed..."):
        for model_name in model_chain:
            try:
                response = client.models.generate_content(
                    model=model_name, 
                    contents=api_messages,
                    config=types.GenerateContentConfig(system_instruction=SYS_INSTRUCT)
                )
                break 
            except Exception as e:
                error_str = str(e)
                if any(err in error_str for err in ["429", "404", "503", "RESOURCE_EXHAUSTED", "Quota exceeded", "NOT_FOUND", "UNAVAILABLE"]):
                    continue
                else:
                    raise e
                    
        if not response:
            st.error("All fallback models are currently unavailable or overloaded. Please wait a moment and try again.")
            st.stop()
            
        gm_text = response.text
        image_data = None
        
        # 5. GHOST TRACKER: Parse State & Automated Logs
        state_match = re.search(r"\[STATE_UPDATE:\s*HP=(\d+),\s*STRAIN=(\d+),\s*INV=(.*?)\]", gm_text)
        if state_match:
            st.session_state.game["hull_hp"] = int(state_match.group(1))
            st.session_state.game["bio_strain"] = int(state_match.group(2))
            st.session_state.game["inventory"] = state_match.group(3).strip()
            gm_text = gm_text.replace(state_match.group(0), "").strip()
            
        # Parse Bestiary Log
        bestiary_match = re.search(r"\[BESTIARY_LOG:\s*(.*?)\]", gm_text)
        if bestiary_match:
            entry = bestiary_match.group(1).strip()
            if st.session_state.game["bestiary"] == "No enemy units scanned yet.":
                st.session_state.game["bestiary"] = f"* {entry}"
            else:
                st.session_state.game["bestiary"] += f"\n\n* {entry}"
            gm_text = gm_text.replace(bestiary_match.group(0), "").strip()

        # Parse Timeline Log
        timeline_match = re.search(r"\[TIMELINE_LOG:\s*(.*?)\]", gm_text)
        if timeline_match:
            entry = timeline_match.group(1).strip()
            st.session_state.game["timeline"] += f"\n\n* {entry}"
            gm_text = gm_text.replace(timeline_match.group(0), "").strip()

        # Parse Lore Log
        lore_match = re.search(r"\[LORE_LOG:\s*(.*?)\]", gm_text)
        if lore_match:
            entry = lore_match.group(1).strip()
            st.session_state.game["lore_notes"] += f"\n\n* {entry}"
            gm_text = gm_text.replace(lore_match.group(0), "").strip()
            
        # 6. NANO-BANANA ENGINE: Imagen Generation with Fallback Tiers
        image_prompt = None
        img_match = re.search(r"\[NANO-BANANA PROMPT\]:\s*(.*)", gm_text, re.IGNORECASE)
        
        if img_match:
            image_prompt = img_match.group(1).strip()
            gm_text = gm_text.replace(img_match.group(0), "").strip()
        elif "scan report" in gm_text.lower() or "scan" in prompt.lower():
            image_prompt = f"A stark concept blueprint of the scanned industrial mech described as: {gm_text[:300]}, brilliant white lines on a solid black background, highly detailed schematic layout, clearly showing the full figure, absolutely no text, no labels, no typography."

        if image_prompt:
            image_model_chain = [
                "imagen-3.0-generate-002",
                "imagen-3.0"
            ]
            
            for img_model_name in image_model_chain:
                try:
                    result = client.models.generate_images(
                        model=img_model_name,
                        prompt=image_prompt,
                        config=dict(
                            number_of_images=1,
                            output_mime_type="image/jpeg",
                            aspect_ratio="1:1"
                        )
                    )
                    if result and result.generated_images:
                        for gen_img in result.generated_images:
                            image_data = Image.open(io.BytesIO(gen_img.image.image_bytes))
                            break
                    if image_data:
                        break
                except Exception as e:
                    error_str = str(e)
                    if any(err in error_str for err in ["429", "404", "503", "RESOURCE_EXHAUSTED", "Quota exceeded", "NOT_FOUND", "UNAVAILABLE"]):
                        continue
                    else:
                        st.session_state.game["lore_notes"] += f"\n\n* [Image Gen Error ({img_model_name}): {e}]"
                        break
                
        # 7. Save & Render Response
        st.session_state.game["history"].append({"role": "model", "content": gm_text, "image": image_data, "display": True})
        
        st.rerun()
