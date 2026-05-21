"""Streamlit app for generating images with fal.ai.

Presentation layer only: all generation logic lives in generator.py.
Run with: uv run streamlit run app.py
"""

import streamlit as st

from generator import ContentFlaggedError, generate_image

st.title("🐲 Dark Monster Generator")

prompt = st.text_area("Describe the image you want to generate:", height=100)

if st.button("Generate", type="primary"):
    try:
        with st.spinner("Generating image..."):
            url = generate_image(prompt)
        st.image(url)
    except (ValueError, ContentFlaggedError) as e:
        st.warning(str(e))
    except Exception as e:
        st.error(f"Could not generate the image: {e}")
