
import re
import requests
import streamlit as st
from pypdf import PdfReader
from io import BytesIO
from datetime import datetime
import sqlite3
import os

# ---------------- CONFIGURATION ----------------

st.set_page_config(
    page_title="LearnWise AI",
    page_icon="🤖",
    layout="wide"
)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2"

# ---------------- SQLITE DATABASE ----------------

# Database file will be created in the same folder as this app.py file.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "learnwise_progress.db")


def init_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                questions_asked INTEGER NOT NULL DEFAULT 0,
                mcqs_generated INTEGER NOT NULL DEFAULT 0,
                flashcards_generated INTEGER NOT NULL DEFAULT 0,
                notes_generated INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            INSERT OR IGNORE INTO progress (id) VALUES (1)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                type TEXT NOT NULL,
                details TEXT NOT NULL
            )
        """)
        conn.commit()


def load_saved_progress():
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("""
            SELECT questions_asked, mcqs_generated,
                   flashcards_generated, notes_generated
            FROM progress WHERE id = 1
        """).fetchone()
        activities = conn.execute("""
            SELECT time, type, details FROM activity
            ORDER BY id DESC LIMIT 100
        """).fetchall()

    return {
        "questions_asked": row[0] if row else 0,
        "mcqs_generated": row[1] if row else 0,
        "flashcards_generated": row[2] if row else 0,
        "notes_generated": row[3] if row else 0,
        "history": [
            {"time": item[0], "type": item[1], "details": item[2]}
            for item in reversed(activities)
        ]
    }


def save_activity(activity_type, details):
    activity_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Keep recent activity in Streamlit session too.
    st.session_state.history.append({
        "time": activity_time,
        "type": activity_type,
        "details": details
    })

    # Save counters and activity to SQLite so they survive app restarts.
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            UPDATE progress
            SET questions_asked = ?,
                mcqs_generated = ?,
                flashcards_generated = ?,
                notes_generated = ?
            WHERE id = 1
        """, (
            st.session_state.questions_asked,
            st.session_state.mcqs_generated,
            st.session_state.flashcards_generated,
            st.session_state.notes_generated
        ))
        conn.execute("""
            INSERT INTO activity (time, type, details)
            VALUES (?, ?, ?)
        """, (activity_time, activity_type, details))
        conn.commit()


# Create the database and load the saved progress once per Streamlit session.
init_database()
saved_progress = load_saved_progress()

# ---------------- SESSION STATE ----------------

defaults = {
    "course_text": "",
    "pdf_name": "",
    "questions_asked": saved_progress["questions_asked"],
    "mcqs_generated": saved_progress["mcqs_generated"],
    "flashcards_generated": saved_progress["flashcards_generated"],
    "notes_generated": saved_progress["notes_generated"],
    "history": saved_progress["history"]
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
    text = st.session_state.get("course_text", "").strip()

    if text:
        return text[:18000]

    return ""


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

        elif not st.session_state.get("pdf_name", "").strip():
            st.error(
                "Please upload a course PDF first "
                "from the Upload Course PDF page."
            )

        elif not st.session_state.get("course_text", "").strip():
            st.error(
                "No course content found. Please upload a valid PDF first."
            )

        else:
            context = get_course_context()

            prompt = f"""
You are LearnWise AI, an educational assistant.

Answer ONLY using the course content below.
Use simple English and clear explanations.
If the answer is not available in the course content, say:
"This answer was not found in the uploaded course content."
Do not invent facts or timestamps.

COURSE CONTENT:
{context}

STUDENT QUESTION:
{question}

Give a clear answer based only on the course content.
"""

            with st.spinner("AI is generating an answer..."):
                answer = ask_ollama(prompt, 1200)

            st.markdown("### Answer")
            st.write(answer)

            st.markdown("### Source Reference")
            st.write("Source:", st.session_state.pdf_name)

            match = re.search(r"\b\d{1,2}:\d{2}\b", answer)
            if match:
                st.write("Timestamp mentioned:", match.group())
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

        elif not st.session_state.get("course_text", "").strip():
            st.error("Please upload a course PDF first.")

        else:
            course_text = st.session_state.course_text
            lines = course_text.splitlines()
            matches = []
            search_words = topic.lower().strip().split()

            for index, line in enumerate(lines):
                line_lower = line.lower()

                # Match full topic or its individual words
                if (
                    topic.lower().strip() in line_lower
                    or any(word in line_lower for word in search_words)
                ):
                    start = max(0, index - 2)
                    end = min(len(lines), index + 3)
                    section = "\n".join(lines[start:end])

                    timestamps = re.findall(
                        r"(?<!\d)(?:\d{1,2}:)?\d{1,2}:\d{2}(?!\d)",
                        section
                    )

                    if not any(
                        section == old_section
                        for old_section, old_timestamps in matches
                    ):
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
                        st.caption(
                            "या section मध्ये timestamp सापडला नाही."
                        )

                    st.divider()

                st.info(
                    "Timestamp मूळ video शी जुळतो का ते तपासा."
                )

            else:
                st.warning(
                    "हा topic PDF text मध्ये सापडला नाही. "
                    "दुसरा keyword वापरून पाहा."
                )

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
        "Progress SQLite database मध्ये save होतो. "
        "App बंद करून पुन्हा सुरू केल्यानंतरही counters आणि recent activity जतन राहतात."
    )
    st.caption("Database file: learnwise_progress.db")

# ---------------- FOOTER ----------------

st.divider()
st.caption("LearnWise AI | AI-Powered Course Learning Assistant")
