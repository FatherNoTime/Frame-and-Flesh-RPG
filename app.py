import re
import json
import streamlit as st
from google import genai
from google.genai import types

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & MOBILE-FRIENDLY CSS
# -----------------------------------------------------------------------------
st.set_page_config(page_title="FRAME & FLESH", layout="centered", initial_sidebar_state="collapsed")

# Custom CSS for Dark Gritty Theme & Sticky Top HUD
st.markdown("""
    <style>
    /* Global Theme */
    .stApp { background-color: #0a0b0d; color: #c5c9d1; font-family: 'Courier New', Courier, monospace; }
    
    /* Sticky Top HUD Container */
    .sticky-hud {
        position: sticky;
        top: 2.5rem;
        z-index: 999;
        background-color: #12151a;
        border: 1px solid #2a323d;
        border-radius: 4px;
        padding: 10px;
        margin-bottom: 20px;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.8);
    }
    
    /* Highlight Colors */
    .hp-text { color: #00ffcc; font-weight: bold; }
    .strain-text { color: #ff3366; font-weight: bold; }
    
    /* Keep Streamlit Header visible so sidebar works */
    /* header { visibility: hidden; } */
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
        "history": [], # Stores chat UI messages
    }
if "api_key" not in st.session_state:
    st.session_state.api_key = ""

# -----------------------------------------------------------------------------
# 3. THE LOREBOOK ENGINE
# -----------------------------------------------------------------------------
LOREBOOK = {
    "erebus": "Black-Site Erebus: Subterranean military research facility. Command claimed all staff evacuated prior to the blackout. Doors are strangely welded from the inside.",
    "splicer": "Mark-1 Splicer Frame: Your mech. Field-engineering variant. Equipped with a back-mounted Blueprint Scanner and reinforced hydraulic limbs for salvage.",
    "neural loom": "Neural Loom: The spinal harness connecting your nervous system to the mech. Splicing incompatible/organic parts causes severe psychological shock.",
    "command": "Command: The military brass that deployed you. They lied about the staff evacuating to cover up the AI's actions.",
    "scanner": "High-Fidelity Blueprint Scanner: Penetrates chassis plating to reveal internal mechanics, weak points, and biological signatures."
}

def get_lore(text):
    """Injects lore only if the player mentions specific keywords."""
    found_lore = [desc for key, desc in LOREBOOK.items() if key in text.lower()]
    if found_lore:
        return "\n[SYSTEM INJECTED LORE CONTEXT]:\n" + "\n".join(found_lore)
    return ""

# -----------------------------------------------------------------------------
# 4. TOP STATIC HUD (Mobile Optimized)
# -----------------------------------------------------------------------------
hud_html = f"""
<div class="sticky-hud">
    <div style="font-size: 0.85rem; color: #667080;">OPERATIONAL STATUS // SUBJECT 09</div>
    <div>HULL INTEGRITY: <span class="hp-text">{st.session_state.game['hull_hp']}/100</span> | BIO-STRAIN: <span class="strain-text">{st.session_state.game['bio_strain']}%</span></div>
    <div style="font-size: 0.85rem; margin-top: 5px;">INV: {st.session_state.game['inventory']}</div>
</div>
"""
st.markdown(hud_html, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 5. SIDEBAR: SETTINGS & ENGINEER's LOG
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("SYS_CONFIG")
    st.session_state.api_key = st.text_input("Gemini API Key", type="password", value=st.session_state.api_key)
    
    st.markdown("---")
    st.subheader("ENGINEER'S LOG")
    st.text_area("Field Notes & Codes (Auto-saves on type):", height=300, placeholder="Document environmental clues here...")

# -----------------------------------------------------------------------------
# 6. SYSTEM INSTRUCTIONS (The GM Persona & Pacing)
# -----------------------------------------------------------------------------
SYS_INSTRUCT = """
You are a Strict, immersive GM for a grimdark sci-fi/body-horror TTRPG titled 'FRAME & FLESH'.
The Player is a military field engineer injured in battle, piloting a repurposed mech equipped with a blueprint scanner and salvage tools.

STORY PREMISE & COMMAND'S LIE:
Command explicitly told the Player that all human personnel safely evacuated Black-Site Erebus before the blackout. THIS IS A LIE. Trapped staff were harvested by the AI.

STRICT CAMPAIGN PACING:
1. BOSSES 1-3 (PURE MECHANICAL): Enemies are strictly autonomous industrial mechs. ABSOLUTELY NO BIOLOGICAL ELEMENTS YET. Hint at the lie via environmental clues (welded doors, bloodless surgical bays, erased logs).
2. POST-BOSS 3 (BIO-HYBRID REVELATION): The AI introduces rare bio-mechs using human limbs and nervous tissue. 
3. PSYCHOLOGICAL BIO-STRAIN: Grafting biological parts causes severe psychological feedback (memory bleeds, auditory hallucinations, UI glitches).

SCANNER & BLUEPRINT DIRECTIVES:
When the Player uses their Scanner on an enemy, output a narrative breakdown: Overall Unit Description, Parts Listing (Function, Ammo, Weak Points), and Scrappable Status.

SAFE ROOMS & CRAFTING:
When the player enters a Safe Room, present 2 to 3 logical, atmospheric crafting or repair options based on their current inventory. Do not resolve the action until they write their choice.

GHOST TRACKING SYSTEM (MANDATORY):
At the very end of EVERY single turn, you must calculate the player's new stats based on the narrative and output this exact tag on a new line:
[STATE_UPDATE: HP=100, STRAIN=0, INV=Item 1, Item 2]
Update the numbers and inventory list dynamically if they take damage, use items, or salvage scrap.

NANO-BANANA BLUEPRINT PROMPT:
Whenever a new unit is scanned, append this block at the end:
[NANO-BANANA PROMPT]: A stark concept blueprint of [Mech Description], brilliant white lines on a solid black background, highly detailed schematic layout, clearly showing the full figure, absolutely no text, no labels, no typography.
"""

# -----------------------------------------------------------------------------
# 7. MAIN CHAT INTERFACE
# -----------------------------------------------------------------------------
# Initial Kickoff Message
if not st.session_state.game["history"]:
    kickoff = "The pain of the integration is a dull ache at the base of my skull. Synthetic nerves knit my spine directly into the Splicer Frame's core. The outer bay doors seal behind me. Local comms are dead. I am standing in the dark Sub-level 3 Docking Bay. A four-legged industrial drone is crushing a cargo crate nearby. Game Master, establish the scene."
    st.session_state.game["history"].append({"role": "user", "content": kickoff, "display": False}) # Hidden from UI
    
    initial_gm = "The airlock hisses shut, severing the howl of the surface wind. Emergency red strobes cut through the gloom of Sub-level 3, casting long, fractured shadows across oil-slicked grating. The comms array in your ear provides nothing but a steady, dead ocean of static.\n\nFifty feet down the gantry, the four-legged industrial drone pauses its work. It is a heavy-duty loader class, its hydraulics whining as it crushes the steel shipping crate. A bright blue welding torch flickers at the end of its primary manipulator arm. It slowly pivots its optic cluster toward you.\n\nWhat do you do, Engineer?"
    st.session_state.game["history"].append({"role": "model", "content": initial_gm, "image": None, "display": True})

# Render Chat History
for msg in st.session_state.game["history"]:
    if msg.get("display", True):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("image"):
                st.image(msg["image"], caption="BLUEPRINT SCAN COMPLETE", use_container_width=True)

# -----------------------------------------------------------------------------
# 8. INPUT HANDLING & API CALLS
# -----------------------------------------------------------------------------
if prompt := st.chat_input("Type your action..."):
    if not st.session_state.api_key:
        st.error("Please enter your Gemini API key in the slide-out menu.")
        st.stop()
        
    # 1. Display User Message
    st.session_state.game["history"].append({"role": "user", "content": prompt, "display": True})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Inject Lore & Format Payload
    context_injected_prompt = prompt + get_lore(prompt) + f"\n[CURRENT INVENTORY: {st.session_state.game['inventory']}]"
    
    # Build API messages (only sending text to API, excluding our custom image keys)
    api_messages = []
    for m in st.session_state.game["history"]:
        if m["role"] == "user":
            api_messages.append(m["content"] if not m == st.session_state.game["history"][-1] else context_injected_prompt)
        else:
            api_messages.append(m["content"])

    # 3. Call Gemini (Game Master)
    client = genai.Client(api_key=st.session_state.api_key)
    with st.spinner("Processing feed..."):
        response = client.models.generate_content(
            model="gemini-3.1-pro",
            contents=api_messages,
            config=types.GenerateContentConfig(system_instruction=SYS_INSTRUCT)
        )
        
        gm_text = response.text
        image_data = None
        
        # 4. GHOST TRACKER: Parse and Remove State Update
        state_match = re.search(r"\[STATE_UPDATE:\s*HP=(\d+),\s*STRAIN=(\d+),\s*INV=(.*?)\]", gm_text)
        if state_match:
            st.session_state.game["hull_hp"] = int(state_match.group(1))
            st.session_state.game["bio_strain"] = int(state_match.group(2))
            st.session_state.game["inventory"] = state_match.group(3).strip()
            gm_text = gm_text.replace(state_match.group(0), "").strip()
            
        # 5. NANO-BANANA ENGINE: Parse Image Prompt & Generate
        img_match = re.search(r"\[NANO-BANANA PROMPT\]:\s*(.*)", gm_text)
        if img_match:
            image_prompt = img_match.group(1)
            gm_text = gm_text.replace(img_match.group(0), "").strip()
            
            img_response = client.models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=image_prompt,
                config=types.GenerateImagesConfig(number_of_images=1)
            )
            if img_response.generated_images:
                image_data = img_response.generated_images[0].image
                
        # 6. Save & Render Response
        st.session_state.game["history"].append({"role": "model", "content": gm_text, "image": image_data, "display": True})
        
        st.rerun() # Refresh to update the sticky HUD instantly
