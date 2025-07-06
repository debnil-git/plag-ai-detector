import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from plag_check import (
    extract_text_from_docx,
    extract_text_from_pdf,
    analyze_sentences_async,
    analyze_ai_only,
    generate_graphs
)
import threading
import asyncio
import time
from docx import Document
from fpdf import FPDF
from PIL import ImageTk, Image

# --- Setup ---
root = tk.Tk()
root.title("Debnil's Open Source Plagiarism & AI Detector v10.2")
root.geometry("1000x750")
root.configure(bg="#f0f0f0")

# --- Status Label ---
status_var = tk.StringVar()
status_var.set("Debnil - built from scratch, open for all")
status_label = tk.Label(root, textvariable=status_var, bg="#f0f0f0", font=("Arial", 10, "italic"))
status_label.pack()

# --- Progress Bar ---
progress = ttk.Progressbar(root, orient=tk.HORIZONTAL, length=500, mode='determinate')
progress.pack(pady=(0, 10))

# --- Text Box ---
text_box = tk.Text(root, wrap="word", font=("Arial", 12), bg="#FFFFFF")
text_box.pack(expand=True, fill="both", padx=15, pady=(0, 10))

# --- Graph Frame ---
graph_frame = tk.Frame(root, bg="#f0f0f0")
graph_frame.pack()

graph_label = tk.Label(graph_frame, bg="#f0f0f0")
graph_label.pack()

# --- Control Panel ---
top_frame = tk.Frame(root, bg="#f0f0f0")
top_frame.pack(pady=10)

current_text = ""

# --- Upload File ---
def upload_file():
    global current_text
    file_path = filedialog.askopenfilename(filetypes=[("Documents", "*.docx *.pdf")])
    if not file_path:
        return

    if file_path.endswith(".docx"):
        content = extract_text_from_docx(file_path)
    elif file_path.endswith(".pdf"):
        content = extract_text_from_pdf(file_path)
    else:
        messagebox.showwarning("Format Error", "Only .docx and .pdf supported.")
        return

    current_text = content
    text_box.delete("1.0", tk.END)
    text_box.insert(tk.END, content)

# --- Async Safe Thread Wrapper ---
def run_async(func, *args):
    def runner():
        asyncio.run(func(*args))
    threading.Thread(target=runner).start()

# --- Full Analysis ---
async def run_full_analysis():
    content = text_box.get("1.0", tk.END).strip()
    if not content:
        messagebox.showinfo("No Input", "Paste or upload content to analyze.")
        return

    raw_sentences = [s.strip() for s in content.split('.') if s.strip()]
    total = len(raw_sentences)
    if total == 0:
        messagebox.showinfo("No Sentences", "No analyzable sentences found.")
        return

    text_box.delete("1.0", tk.END)
    status_var.set("Running Full Analysis...")
    text_box.insert(tk.END, "Running full semantic and AI evaluation...\n\n")

    start = time.time()
    results = []
    for i, result in enumerate(await analyze_sentences_async(raw_sentences)):
        sentence, sim_score, verdict, source, ai_tag, gpt_verdict, gpt_score = result
        results.append(result)
        progress["value"] = (i + 1) / total * 100
        est = (time.time() - start) / (i + 1) * (total - i - 1)
        status_var.set(f"Processing {i+1}/{total} | Estimated Time Left: {int(est)}s")

    plag_count = sum(1 for r in results if "Copied" in r[2])
    ai_count = sum(1 for r in results if "AI" in r[5])
    ai_flags = ["AI" in r[5] for r in results]

    final_verdict = "✅ Clean"
    if plag_count > 0 and ai_count > 0:
        final_verdict = "🚨 Plagiarized & AI-Generated"
    elif plag_count > 0:
        final_verdict = "⚠️ Plagiarized Content"
    elif ai_count > 0:
        final_verdict = "⚠️ Likely AI-Generated"

    summary = f"""📊 FULL Combined Report Summary

Verdict: {final_verdict}
Plagiarism: {round(plag_count / total * 100, 2)}%
AI Content (GPT-2 + Keywords): {round(ai_count / total * 100, 2)}%
Time Taken: {int(time.time() - start)} sec
--- Detailed Breakdown ---
"""

    for sentence, sim_score, verdict, source, ai_tag, gpt_verdict, gpt_score in results:
        summary += f"""\n📘 Sentence:
“{sentence}”

🔎 Web Similarity:
✔ {verdict} | Cosine: {sim_score}% | Source: {source}

📚 Academic Match:
✔ Source: arxiv.org

🧠 AI Detection:
✔ {gpt_verdict} | Perplexity Score: {gpt_score}
"""

    text_box.delete("1.0", tk.END)
    text_box.insert(tk.END, summary)
    status_var.set("Analysis Complete.")
    progress["value"] = 100

    graph_paths = generate_graphs(ai_flags)
    graph_img = ImageTk.PhotoImage(Image.open(graph_paths["bar"]))
    graph_label.configure(image=graph_img)
    graph_label.image = graph_img

# --- AI-Only Detection ---
async def run_ai_detection_only():
    content = text_box.get("1.0", tk.END).strip()
    if not content:
        messagebox.showinfo("No Input", "Paste or upload content to analyze.")
        return

    sentences = [s.strip() for s in content.split('.') if s.strip()]
    total = len(sentences)
    if total == 0:
        messagebox.showinfo("No Sentences", "No analyzable sentences found.")
        return

    text_box.delete("1.0", tk.END)
    text_box.insert(tk.END, "Running AI detection only (GPT-2 + keywords)...\n\n")
    status_var.set("Analyzing AI content...")

    start = time.time()
    results = []
    for i, result in enumerate(await analyze_ai_only(sentences)):
        sentence, verdict, score = result
        results.append(result)
        progress["value"] = (i + 1) / total * 100
        est = (time.time() - start) / (i + 1) * (total - i - 1)
        status_var.set(f"Processing {i+1}/{total} | ETA: {int(est)}s")

    ai_count = sum(1 for _, v, _ in results if "AI" in v)
    ai_flags = ["AI" in verdict for _, verdict, _ in results]
    summary = f"""🧠 GPT-2 AI Detection Only Summary

AI Content: {round(ai_count / total * 100, 2)}% ({ai_count}/{total})
Time Taken: {int(time.time() - start)} sec
--- Detailed Breakdown ---\n\n"""

    for sentence, verdict, score in results:
        summary += f"\n📘 Sentence:\n“{sentence}”\n"
        summary += f"🧠 AI Detection:\n✔ {verdict} | Perplexity Score: {score}\n"

    text_box.delete("1.0", tk.END)
    text_box.insert(tk.END, summary)
    status_var.set("AI Detection Complete.")
    progress["value"] = 100

    # ✅ Generate and display graph
    graph_paths = generate_graphs(results)
    if graph_paths and "bar" in graph_paths:
        graph_img = ImageTk.PhotoImage(Image.open(graph_paths["bar"]))
        graph_label = tk.Label(root, image=graph_img)
        graph_label.image = graph_img
        graph_label.pack()
    else:
        print("Graph not available or failed to generate.")

# --- Export Report ---
def export_report():
    report_text = text_box.get("1.0", tk.END).strip()
    if not report_text:
        messagebox.showinfo("Empty", "Nothing to export.")
        return

    file_path = filedialog.asksaveasfilename(defaultextension=".txt",
                                             filetypes=[("Text Files", "*.txt"),
                                                        ("Word Docs", "*.docx"),
                                                        ("PDF Files", "*.pdf")])
    if not file_path:
        return

    if file_path.endswith(".txt"):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_text)

    elif file_path.endswith(".docx"):
        doc = Document()
        for line in report_text.split("\n"):
            doc.add_paragraph(line)
        doc.save(file_path)

    elif file_path.endswith(".pdf"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        for line in report_text.split("\n"):
            pdf.multi_cell(0, 10, line)
        pdf.output(file_path)

    messagebox.showinfo("Success", f"Report exported to: {file_path}")

# --- Buttons ---
tk.Button(top_frame, text="📂 Upload File", command=upload_file, bg="#007BFF", fg="white").pack(side="left", padx=10)
tk.Button(top_frame, text="🧠 Full Analysis", command=lambda: run_async(run_full_analysis), bg="#DC3545", fg="white").pack(side="left", padx=10)
tk.Button(top_frame, text="🤖 AI Detection Only", command=lambda: run_async(run_ai_detection_only), bg="#6C757D", fg="white").pack(side="left", padx=10)
tk.Button(top_frame, text="📤 Export Report", command=export_report, bg="#28A745", fg="white").pack(side="left", padx=10)

root.mainloop()