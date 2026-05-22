"""Streamlit app for generating images with fal.ai.

Presentation layer only: generation lives in generator.py and persistence in
storage.py. Run with: uv run streamlit run app.py
"""

import streamlit as st

from generator import ContentFlaggedError, generate_image, transcribe_audio
from storage import list_generations, save_generation, save_upload

st.markdown("""
<style>
.block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

st.title("Dark Monster Generator")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pwd = st.text_input("Password:", type="password")
    if st.button("Enter"):
        if pwd == st.secrets["password"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

page = st.sidebar.pills("Navigation", ["Generate", "Gallery"], default="Generate")


def _run_generation(prompt: str, audio, uploaded):
    """Resolve inputs and generate or save an image."""
    try:
        active_prompt = prompt.strip()
        if not active_prompt and audio:
            with st.spinner("Transcribing audio..."):
                active_prompt = transcribe_audio(audio.read())
            st.info(f'Transcribed: "{active_prompt}"')

        if uploaded:
            with st.spinner("Saving your image..."):
                saved = save_upload(active_prompt, uploaded.getvalue(), uploaded.type)
        else:
            with st.spinner("Generating your monster..."):
                url = generate_image(active_prompt)
                saved = save_generation(active_prompt, url)

        st.image(saved["image_url"], caption=saved["prompt"] or "No description")
        st.success("Saved to your gallery.")

    except (ValueError, ContentFlaggedError) as e:
        st.warning(str(e))
    except Exception as e:
        st.error(f"Something went wrong: {e}")


if page == "Generate":
    with st.expander("➕  Attach image or record voice (optional)"):
        col_img, col_audio = st.columns(2)
        with col_img:
            uploaded = st.file_uploader("Reference image:", type=["jpg", "jpeg", "png", "webp"], key="uploader")
            if uploaded:
                st.image(uploaded, use_container_width=True)
        with col_audio:
            audio = st.audio_input("Record your prompt:", key="audio_input")
            if audio and st.button("Generate from voice", use_container_width=True):
                _run_generation("", audio, st.session_state.get("uploader"))

    prompt = st.chat_input("Describe your monster...")
    if prompt:
        _run_generation(prompt, st.session_state.get("audio_input"), st.session_state.get("uploader"))

elif page == "Gallery":
    generations = list_generations()
    if not generations:
        st.info("No generations yet. Create one in the Generate tab.")
    for item in generations:
        st.image(item["image_url"], caption=item["prompt"])
