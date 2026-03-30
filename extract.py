import fitz
import docx

def extract_pdf(file_path):
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    with open("pdf_text.txt", "w", encoding="utf-8") as f:
        f.write(text)

def extract_docx(file_path):
    doc = docx.Document(file_path)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    with open("docx_text.txt", "w", encoding="utf-8") as f:
        f.write(text)

extract_pdf("1DOCKSMITH.pdf")
extract_docx("CC-DOCKSMITH (1).docx")
