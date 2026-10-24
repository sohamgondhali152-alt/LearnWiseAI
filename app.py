
import re
import requests
import streamlit as st
from pypdf import PdfReader
from io import BytesIO
from datetime import datetime

# ---------------- CONFIGURATION ----------------

st.set_page_config(
    page_title="LearnWise AI",
    page_icon="🤖",
    layout="wide"
)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2"

# ---------------- SESSION STATE ----------------

defaults = {
    "course_text": "",
    "pdf_name": "",
    "questions_asked": 0,
    "mcqs_generated": 0,
    "flashcards_generated": 0,
    "notes_generated": 0,
    "history": []
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ---------------- OLLAMA AI ----------------

def ask_ollama(prompt, max_tokens=1200):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.2
                }
            },
            timeout=(10, 600)
        )

        response.raise_for_status()
        return response.json().get("response", "").strip()

    except requests.exceptions.ConnectionError:
        return "Ollama connect होत नाही. Ollama चालू आहे का ते तपासा."
    except requests.exceptions.Timeout:
        return "AI ला वेळ लागत आहे. पुन्हा प्रयत्न करा."
    except requests.exceptions.RequestException as error:
        return f"Request Error: {error}"
    except ValueError:
        return "Ollama कडून योग्य response मिळाला नाही."


def get_course_context():
    text = st.session_state.course_text.strip()

    if text:
        return text[:18000]

    return "No PDF uploaded. Answer general educational questions honestly."


def save_activity(activity_type, details):
    st.session_state.history.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "type": activity_type,
        "details": details
    })


# ---------------- SIDEBAR ----------------

st.sidebar.title("🤖 LearnWise AI")

page = st.sidebar.radio(
    "Select Feature",
    [
        "Home",
        "Upload Course PDF",
        "Ask AI",
        "Timestamp Search",
        "MCQ Generator",
        "Flashcards",
        "Revision Notes",
        "Student Progress"
    ]
)

if st.session_state.pdf_name:
    st.sidebar.success("PDF: " + st.session_state.pdf_name)
else:
    st.sidebar.info("Upload a PDF to use your course content.")

# ---------------- HOME ----------------

if page == "Home":
    st.title("🎓 LearnWise AI")
    st.subheader("AI-Powered Course Learning Assistant")

    st.write(
        "LearnWise AI helps students learn from course PDFs "
        "and educational content using AI."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 📄 Course PDFs")
        st.write("Upload and extract course notes.")

    with col2:
        st.markdown("### 💬 Ask AI")
        st.write("Ask questions about your course.")

    with col3:
        st.markdown("### 📝 Study Tools")
        st.write("Generate MCQs, flashcards and revision notes.")

    st.divider()
    st.markdown("### How to use")
    st.write("1. Upload your course PDF.")
    st.write("2. Ask questions about the content.")
    st.write("3. Generate MCQs and flashcards.")
    st.write("4. Review your learning activity.")

# ---------------- PDF UPLOAD ----------------

elif page == "Upload Course PDF":
    st.title("📄 Upload Course PDF")

    uploaded_file = st.file_uploader(
        "Choose your course PDF",
        type=["pdf"]
    )

    if uploaded_file is not None:
        if st.button("Extract PDF Text"):
            try:
                reader = PdfReader(
                    BytesIO(uploaded_file.getvalue())
                )

                pages_text = []

                for page_number, pdf_page in enumerate(
                    reader.pages, start=1
                ):
                    text = pdf_page.extract_text() or ""

                    if text.strip():
                        pages_text.append(
                            f"\n[PDF Page {page_number}]\n{text}"
                        )

                extracted_text = "\n".join(pages_text).strip()

                if extracted_text:
                    st.session_state.course_text = extracted_text
                    st.session_state.pdf_name = uploaded_file.name

                    st.success("PDF text extracted successfully!")
                    st.write("Total pages:", len(reader.pages))
                    st.write("Characters:", len(extracted_text))

                    st.text_area(
                        "Extracted Text Preview",
                        extracted_text[:5000],
                        height=300
                    )
                else:
                    st.warning(
                        "Text मिळाला नाही. PDF scanned असल्यास "
                        "OCR आवश्यक असू शकते."
                    )

            except Exception as error:
                st.error(f"PDF Error: {error}")

    if st.session_state.course_text:
        st.success("Course content is ready.")

        if st.button("Clear Uploaded PDF"):
            st.session_state.course_text = ""
            st.session_state.pdf_name = ""
            st.rerun()

# ---------------- ASK AI ----------------

elif page == "Ask AI":
    st.title("💬 Ask AI")

    question = st.text_input(
        "Enter your question",
        placeholder="What is RAG? Explain with an example."
    )

    if st.button("Ask AI"):
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            context = get_course_context()

            prompt = f"""
You are LearnWise AI, an educational assistant.

Answer using the course content below.
Use simple English and clear explanations.
If the answer is not available in the uploaded content,
say so. Do not invent facts or timestamps.

COURSE CONTENT:
{context}

STUDENT QUESTION:
{question}

Give a clear answer.
"""

            with st.spinner("AI is generating an answer..."):
                answer = ask_ollama(prompt, 1200)

           
            st.markdown("### Answer")
            st.write(answer)

            # Display uploaded PDF source
            if st.session_state.pdf_name:
                st.markdown("### Source Reference")
                st.write("Source:", st.session_state.pdf_name)

                if re.search(r"\b\d{1,2}:\d{2}\b", answer):
                    timestamp = re.search(
                        r"\b\d{1,2}:\d{2}\b", answer
                    ).group()
                    st.write("Timestamp mentioned:", timestamp)
                    st.caption(
                        "Please verify this timestamp against the original video."
                    )

            st.session_state.questions_asked += 1
            save_activity("Question", question)


# ---------------- TIMESTAMP SEARCH ----------------

elif page == "Timestamp Search":
    st.title("⏱️ Timestamp Search")

    topic = st.text_input(
        "Enter topic",
        placeholder="Backpropagation"
    )

    if st.button("Search Topic"):
        if not topic.strip():
            st.warning("Please enter a topic.")
        else:
            lines = get_course_context().splitlines()
            matches = []

            for index, line in enumerate(lines):
                if topic.lower() in line.lower():
                    start = max(0, index - 2)
                    end = min(len(lines), index + 3)
                    section = "\n".join(lines[start:end])

                    timestamps = re.findall(
                        r"(?<!\d)(?:\d{1,2}:)?\d{1,2}:\d{2}(?!\d)",
                        section
                    )

                    matches.append((section, timestamps))

            if matches:
                for number, (section, timestamps) in enumerate(
                    matches[:10], start=1
                ):
                    st.markdown(f"### Result {number}")
                    st.write(section)

                    if timestamps:
                        st.write(
                            "Timestamp found:",
                            ", ".join(dict.fromkeys(timestamps))
                        )
                    else:
                        st.caption("No timestamp found in this section.")

                    st.divider()

                st.info(
                    "PDF मधील timestamp हा video शी जुळतो का, "
                    "ते मूळ transcript किंवा video मधून तपासा."
                )
            else:
                st.warning("Topic not found in the course content.")

# ---------------- MCQ GENERATOR ----------------

elif page == "MCQ Generator":
    st.title("📝 MCQ Generator")

    topic = st.text_input(
        "Enter MCQ topic",
        placeholder="RAG, Python, Machine Learning"
    )

    number_of_questions = st.selectbox(
        "Number of Questions",
        [3, 5, 10],
        index=1
    )

    if st.button("Generate MCQs"):
        context = get_course_context()

        prompt = f"""
You are an educational quiz generator.
Generate exactly {number_of_questions} complete MCQs.

Topic: {topic if topic.strip() else "General course content"}

For every question provide:
Question number and complete question
A) First option
B) Second option
C) Third option
D) Fourth option
Correct Answer: One correct option
Explanation: A short explanation

IMPORTANT:
- Complete every question.
- Number questions from 1 to {number_of_questions}.
- Put every option on a separate line.
- Use simple English.
- Do not repeat questions.
- Do not invent course-specific facts.
- Ensure every correct answer is scientifically accurate.
- Learning rate controls the step size of weight updates.
- Do not say the learning rate adjusts itself.
- RAG means Retrieval-Augmented Generation.

COURSE CONTENT:
{context}

Generate all questions completely now.
"""

        with st.spinner("Generating MCQs..."):
            result = ask_ollama(prompt, 2200)

        formatted_result = re.sub(
            r"\s+([ABCD]\))",
            r"\n\n\1",
            result
        )

        formatted_result = re.sub(
            r"\s+(Correct Answer:)",
            r"\n\n**\1**",
            formatted_result
        )

        formatted_result = re.sub(
            r"\s+(Explanation:)",
            r"\n\n**\1**",
            formatted_result
        )

        st.markdown("### Generated MCQs")
        st.markdown(formatted_result)

        st.session_state.mcqs_generated += number_of_questions
        save_activity(
            "MCQ Generator",
            f"{number_of_questions} MCQs"
        )

# ---------------- FLASHCARDS ----------------

elif page == "Flashcards":
    st.title("🗂️ Flashcard Generator")

    topic = st.text_input(
        "Enter flashcard topic",
        placeholder="Neural Networks"
    )

    number_of_cards = st.selectbox(
        "Number of Flashcards",
        [3, 5, 10],
        index=1
    )

    if st.button("Generate Flashcards"):
        context = get_course_context()

        prompt = f"""
Create exactly {number_of_cards} educational flashcards.

Topic: {topic if topic.strip() else "General course content"}

For each flashcard provide:
Flashcard 1
Front: A short question or term
Back: A clear and simple answer

Complete all {number_of_cards} flashcards.
Use simple English. Do not invent facts.

COURSE CONTENT:
{context}
"""

        with st.spinner("Generating flashcards..."):
            result = ask_ollama(prompt, 1600)

        st.markdown("### Generated Flashcards")
        st.markdown(result)

        st.session_state.flashcards_generated += number_of_cards
        save_activity(
            "Flashcards",
            f"{number_of_cards} flashcards"
        )

# ---------------- REVISION NOTES ----------------

elif page == "Revision Notes":
    st.title("📚 Revision Notes")

    topic = st.text_input(
        "Enter topic for notes",
        placeholder="Artificial Intelligence"
    )

    if st.button("Generate Revision Notes"):
        context = get_course_context()

        prompt = f"""
Create revision notes based on the course content.

Topic: {topic if topic.strip() else "General course content"}

Include:
1. Definition
2. Important concepts
3. Key points
4. Examples if available
5. Short summary

Use simple English, headings and bullet points.
Do not invent facts.

COURSE CONTENT:
{context}
"""

        with st.spinner("Creating revision notes..."):
            result = ask_ollama(prompt, 1800)

        st.markdown("### Revision Notes")
        st.markdown(result)

        st.session_state.notes_generated += 1
        save_activity(
            "Revision Notes",
            topic if topic.strip() else "General notes"
        )

# ---------------- STUDENT PROGRESS ----------------

elif page == "Student Progress":
    st.title("📊 Student Progress")

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Questions Asked",
            st.session_state.questions_asked
        )
        st.metric(
            "MCQs Generated",
            st.session_state.mcqs_generated
        )

    with col2:
        st.metric(
            "Flashcards Generated",
            st.session_state.flashcards_generated
        )
        st.metric(
            "Revision Note Sets",
            st.session_state.notes_generated
        )

    st.divider()
    st.subheader("Recent Activity")

    if st.session_state.history:
        for item in reversed(st.session_state.history[-20:]):
            st.write(
                f"**{item['type']}** — {item['details']} "
                f"({item['time']})"
            )
    else:
        st.info("अजून activity नाही. Features वापरून पाहा.")

    st.caption(
        "Progress सध्या session मध्येच साठवला जातो. "
        "App restart केल्यावर तो reset होऊ शकतो."
    )

# ---------------- FOOTER ----------------

st.divider()
st.caption("LearnWise AI | AI-Powered Course Learning Assistant")
