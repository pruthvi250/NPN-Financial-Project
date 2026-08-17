"""
qa_assistant.py
Replaces prag.py.

CRITICAL FIX: the original prag.py had a live Google Gemini API key
committed directly in the source code:

    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyDQ...")

Never commit a real key to code, even as a fallback default - anyone who
sees the file (a mentor reviewing your GitHub repo, a public commit
history) can lift it and run up charges on your account, and revoking it
breaks the app for everyone using it. This version requires the key to be
entered at runtime (sidebar input, stored only in session memory) or read
from an environment variable that is NOT hardcoded here.

Everything else (chunking, FAISS vector store, retrieval-augmented Q&A)
is the same architecture as prag.py, just wired to a safely-sourced key.
"""

import os
from pypdf import PdfReader


def get_pdf_text(pdf_docs) -> str:
    text = ""
    for pdf in pdf_docs:
        reader = PdfReader(pdf)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text


def get_text_chunks(text: str, chunk_size: int = 10000, chunk_overlap: int = 1000) -> list:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text(text)


def build_vector_store(text_chunks: list, api_key: str, index_path: str = "faiss_index"):
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from langchain_community.vectorstores import FAISS

    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=api_key)
    vector_store = FAISS.from_texts(text_chunks, embedding=embeddings)
    vector_store.save_local(index_path)
    return vector_store


def answer_question(question: str, api_key: str, index_path: str = "faiss_index") -> str:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
    from langchain_community.vectorstores import FAISS
    from langchain.chains.question_answering import load_qa_chain
    from langchain.prompts import PromptTemplate

    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=api_key)
    db = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    docs = db.similarity_search(question)

    prompt_template = """
    Answer the question as detailed as possible from the provided context,
    make sure to provide all the details. If the answer is not in the
    provided context just say "answer is not available in the context" -
    don't guess or invent figures from a financial document.

    Context:
    {context}

    Question:
    {question}

    Answer:
    """
    model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key, temperature=0.2)
    prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
    chain = load_qa_chain(model, chain_type="stuff", prompt=prompt)
    response = chain({"input_documents": docs, "question": question}, return_only_outputs=True)
    return response["output_text"]
