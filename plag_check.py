# ------------------------------
# File: plag_check.py (v10.2)
# ------------------------------

import aiohttp
import asyncio
import random
import re
import torch
import docx2txt
import fitz  # PyMuPDF
import matplotlib.pyplot as plt

from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer, util
from transformers import GPT2LMHeadModel, GPT2TokenizerFast

# --- Load Models ---
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
gpt_model = GPT2LMHeadModel.from_pretrained("gpt2")
gpt_tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")


# --- Extraction ---
def extract_text_from_docx(path):
    return docx2txt.process(path)


def extract_text_from_pdf(path):
    doc = fitz.open(path)
    return "\n".join(page.get_text() for page in doc)


# --- Async Search ---
async def fetch_html(session, url):
    try:
        async with session.get(url, timeout=10) as resp:
            return await resp.text()
    except:
        return ""


async def fetch_web_text(query, engine="ddg", num_results=10):
    await asyncio.sleep(random.uniform(1.5, 3.5))  # mimic human behavior
    headers = {"User-Agent": "Mozilla/5.0"}
    results = []

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            if engine == "ddg":
                search_url = f"https://html.duckduckgo.com/html/?q={query}"
                html = await fetch_html(session, search_url)
                soup = BeautifulSoup(html, "html.parser")
                links = soup.find_all("a", class_="result__a", limit=num_results)
                results = [a["href"] for a in links]
            elif engine == "mojeek":
                search_url = f"https://www.mojeek.com/search?q={query}"
                html = await fetch_html(session, search_url)
                soup = BeautifulSoup(html, "html.parser")
                links = soup.find_all("a", href=True)
                results = [a["href"] for a in links if "mojeek" not in a["href"]][:num_results]

        except:
            return ""

        texts = []
        for url in results:
            try:
                html = await fetch_html(session, url)
                soup = BeautifulSoup(html, "html.parser")
                body = soup.get_text(separator=" ", strip=True)
                texts.append(body[:500])
            except:
                continue

        return " ".join(texts)


# --- Similarity Check ---
async def check_similarity(text):
    try:
        web_text = await fetch_web_text(text, engine="ddg")
    except:
        web_text = await fetch_web_text(text, engine="mojeek")

    if not web_text:
        return 0.0, "No match found", "N/A"

    emb1 = model.encode(text, convert_to_tensor=True)
    emb2 = model.encode(web_text, convert_to_tensor=True)
    sim = round(float(util.cos_sim(emb1, emb2).item()) * 100, 2)

    verdict = "Copied" if sim > 75 else "Unique"
    return sim, verdict, "duckduckgo.com"


# --- AI Detection ---
def detect_ai(text):
    input_ids = gpt_tokenizer.encode(text, return_tensors="pt", max_length=512, truncation=True)
    with torch.no_grad():
        loss = gpt_model(input_ids, labels=input_ids).loss
    perplexity = torch.exp(loss).item()
    verdict = "Likely AI" if perplexity < 60 else "Human-like"
    return verdict, round(perplexity, 2)


# --- Combined Async Analyzer ---
async def analyze_sentences_async(sentences):
    results = []
    for sentence in sentences:
        sim_score, verdict, source = await check_similarity(sentence)
        ai_verdict, ai_score = detect_ai(sentence)
        results.append((sentence, sim_score, verdict, source, "ai", ai_verdict, ai_score))
    return results


# --- AI-Only Async Analyzer ---
async def analyze_ai_only(sentences):
    results = []
    for sentence in sentences:
        verdict, score = detect_ai(sentence)
        results.append((sentence, verdict, score))
    return results


# --- Graph Generation ---
def generate_graphs(ai_results, save_path="ai_trend.png"):
    try:
        # Validate input structure
        if not isinstance(ai_results, list) or not all(isinstance(r, tuple) and len(r) == 3 for r in ai_results):
            raise ValueError("Invalid AI results format")

        scores = [r[2] for r in ai_results]  # Perplexity scores
        labels = [f"{i+1}" for i in range(len(scores))]
        colors = ["red" if s < 60 else "green" for s in scores]

        plt.figure(figsize=(10, 4))
        plt.bar(labels, scores, color=colors)
        plt.axhline(60, color="orange", linestyle="--", label="AI Detection Threshold")
        plt.title("AI Detection Perplexity Trend")
        plt.xlabel("Sentence #")
        plt.ylabel("Perplexity Score")
        plt.legend()
        plt.tight_layout()
        plt.savefig(save_path)
        plt.close()

        return {"bar": save_path}  # ✅ returns dict for main.py
    except Exception as e:
        print("Graph generation failed:", e)
        return None
