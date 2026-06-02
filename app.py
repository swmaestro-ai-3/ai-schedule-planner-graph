import streamlit as st


def main() -> None:
    st.set_page_config(
        page_title="AI Schedule Planner Graph",
        page_icon="calendar",
        layout="wide",
    )
    st.title("AI Schedule Planner Graph")
    st.info("Project scaffold is ready. Planner features will be added in later issues.")


if __name__ == "__main__":
    main()
