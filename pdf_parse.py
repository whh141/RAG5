#!/usr/bin/env python
# coding: utf-8

import pdfplumber
from PyPDF2 import PdfReader
from pathlib import Path
import json
import re
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from langchain_core.documents import Document

class DataProcess(object):

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.data = []






    # 滑动窗口功能实现，其中fast代表当前遍历句子的index，slow代表每次窗口开始滑动的起点。默认窗口直接滑动的overlap是1个句子。
    def SlidingWindow(self, sentences, kernel = 512, stride = 1):
        sz = len(sentences)
        cur = ""
        fast = 0
        slow = 0
        while(fast < len(sentences)):
            sentence = sentences[fast]
            if(len(cur + sentence) > kernel and (cur + sentence) not in self.data):
                self.data.append(cur + sentence + "。")
                cur = cur[len(sentences[slow] + "。"):]
                slow = slow + 1
            cur = cur + sentence + "。"
            fast = fast + 1

    #  数据过滤，根据当前的文档内容的item划分句子，然后根据max_seq划分文档块。
    def Datafilter(self, line, header, pageid, max_seq = 1024):

         sz = len(line)
         if(sz < 6):
             return

         if(sz > max_seq):

             if("■" in line):
                 sentences = line.split("■")
             elif("•" in line):
                 sentences = line.split("•")
             elif("\t" in line):
                 sentences = line.split("\t")
             else:
                 sentences = line.split("。")

             for subsentence in sentences:
                 subsentence = subsentence.replace("\n", "")

                 if(len(subsentence) < max_seq and len(subsentence) > 5):
                     subsentence = subsentence.replace(",", "").replace("\n","").replace("\t","")
                     if(subsentence not in self.data):
                         self.data.append(subsentence)
         else:
             line = line.replace("\n","").replace(",", "").replace("\t","")
             if(line not in self.data):
                 self.data.append(line)

    # 提取页头即一级标题
    def GetHeader(self, page):
        try:
            lines = page.extract_words()[::]
        except:
            return None
        if(len(lines) > 0):
            for line in lines:
                if("目录" in line["text"] or ".........." in line["text"]):
                    return None
                if(line["top"] < 20 and line["top"] > 17):
                    return line["text"]
            return lines[0]["text"]
        return None

    # 按照每页中块提取内容,并和一级标题进行组合,配合Document 可进行意图识别
    def ParseBlock(self, max_seq = 1024):

        with pdfplumber.open(self.pdf_path) as pdf:

            for i, p in enumerate(pdf.pages):
                header = self.GetHeader(p)

                if(header == None):
                    continue

                texts = p.extract_words(use_text_flow=True, extra_attrs = ["size"])[::]

                squence = ""
                lastsize = 0

                for idx, line in enumerate(texts):
                    if(idx <1):
                        continue
                    if(idx == 1):
                        if(line["text"].isdigit()):
                            continue
                    cursize = line["size"]
                    text = line["text"]
                    if(text == "□" or text == "•"):
                        continue
                    elif(text== "警告！" or text == "注意！" or text == "说明！"):
                        if(len(squence) > 0):
                            self.Datafilter(squence, header, i, max_seq = max_seq)
                        squence = ""
                    elif(format(lastsize,".5f") == format(cursize,".5f")):
                        if(len(squence)>0):
                            squence = squence + text
                        else:
                            squence = text
                    else:
                        lastsize = cursize
                        if(len(squence) < 15 and len(squence)>0):
                            squence = squence + text
                        else:
                            if(len(squence) > 0):
                                self.Datafilter(squence, header, i, max_seq = max_seq)
                            squence = text
                if(len(squence) > 0):
                    self.Datafilter(squence, header, i, max_seq = max_seq)

    # 按句号划分文档，然后利用最大长度划分文档块
    def ParseOnePageWithRule(self, max_seq = 512, min_len = 6):
        for idx, page in enumerate(PdfReader(self.pdf_path).pages):
            page_content = ""
            text = page.extract_text()
            words = text.split("\n")
            for idx, word in enumerate(words):
                text = word.strip().strip("\n")
                if("...................." in text or "目录" in text):
                    continue
                if(len(text) < 1):
                    continue
                if(text.isdigit()):
                    continue
                page_content = page_content + text
            if(len(page_content) < min_len):
                continue
            if(len(page_content) < max_seq):
                if(page_content not in self.data):
                    self.data.append(page_content)
            else:
                sentences = page_content.split("。")
                cur = ""
                for idx, sentence in enumerate(sentences):
                    if(len(cur + sentence) > max_seq and (cur + sentence) not in self.data):
                        self.data.append(cur + sentence)
                        cur = sentence
                    else:
                        cur = cur + sentence
    #  滑窗法提取段落
    #  1. 把pdf看做一个整体,作为一个字符串
    #  2. 利用句号当做分隔符,切分成一个数组
    #  3. 利用滑窗法对数组进行滑动, 此处的
    def ParseAllPage(self, max_seq = 512, min_len = 6):
        all_content = ""
        for idx, page in enumerate(PdfReader(self.pdf_path).pages):
            page_content = ""
            text = page.extract_text()
            words = text.split("\n")
            for idx, word in enumerate(words):
                text = word.strip().strip("\n")
                if("...................." in text or "目录" in text):
                    continue
                if(len(text) < 1):
                    continue
                if(text.isdigit()):
                    continue
                page_content = page_content + text
            if(len(page_content) < min_len):
                continue
            all_content = all_content + page_content
        sentences = all_content.split("。")
        self.SlidingWindow(sentences, kernel = max_seq)
        
def load_pdfs_from_dir(pdf_dir):
    all_data = []
    pdf_files = sorted(Path(pdf_dir).glob("*.pdf"))

    for pdf_file in pdf_files:
        dp = DataProcess(pdf_path=str(pdf_file))
        dp.ParseBlock(max_seq=1024)
        dp.ParseBlock(max_seq=512)
        dp.ParseAllPage(max_seq=256)
        dp.ParseAllPage(max_seq=512)
        dp.ParseOnePageWithRule(max_seq=256)
        dp.ParseOnePageWithRule(max_seq=512)
        all_data.extend(dp.data)

    return list(dict.fromkeys(all_data))


def load_knowledge_documents(kb_dir: str, faq_path: str | None = None) -> list[Document]:
    """
    加载完整知识库文档。
    注册到文档解析器的知识库文件和 FAQ JSON 都统一转换为带来源元数据的 Document。
    """
    documents: list[Document] = []
    base_dir = Path(kb_dir)
    if not base_dir.exists():
        raise FileNotFoundError(f"知识库目录不存在: {kb_dir}")

    for extension, loader in get_document_loaders().items():
        for document_file in sorted(base_dir.glob(f"*{extension}")):
            documents.extend(loader(document_file))

    if faq_path:
        documents.extend(_load_faq_documents(Path(faq_path)))

    if not documents:
        raise ValueError(f"知识库为空: {kb_dir}")

    return _deduplicate_documents(documents)


def supported_knowledge_extensions() -> list[str]:
    return sorted(get_document_loaders().keys())


def get_document_loaders():
    return {
        ".pdf": _load_pdf_documents,
        ".doc": _load_doc_documents,
        ".docx": _load_docx_documents,
    }


def _load_pdf_documents(pdf_file: Path) -> list[Document]:
    documents: list[Document] = []
    with pdfplumber.open(str(pdf_file)) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            text = _clean_text(text)
            if not text:
                continue

            chunks = _chunk_text(text, max_chars=850, overlap=120)
            for chunk_index, chunk in enumerate(chunks, start=1):
                documents.append(
                    Document(
                        page_content=chunk,
                        metadata={
                            "doc_id": _make_doc_id(pdf_file, page_index, chunk_index),
                            "title": pdf_file.stem,
                            "source_file": _source_file_value(pdf_file),
                            "source_type": "pdf",
                            "page": page_index,
                            "chunk_id": chunk_index,
                        },
                    )
                )
    return documents


def _load_doc_documents(doc_file: Path) -> list[Document]:
    text = _extract_doc_text(doc_file)
    chunks = _chunk_text(text, max_chars=850, overlap=120)
    documents: list[Document] = []
    for chunk_index, chunk in enumerate(chunks, start=1):
        documents.append(
            Document(
                page_content=chunk,
                metadata={
                    "doc_id": _make_doc_id(doc_file, 0, chunk_index),
                    "title": doc_file.stem,
                    "source_file": _source_file_value(doc_file),
                    "source_type": "doc",
                    "page": None,
                    "chunk_id": chunk_index,
                },
            )
        )
    return documents


def _load_docx_documents(docx_file: Path) -> list[Document]:
    text = _extract_docx_text(docx_file)
    chunks = _chunk_text(text, max_chars=850, overlap=120)
    documents: list[Document] = []
    for chunk_index, chunk in enumerate(chunks, start=1):
        documents.append(
            Document(
                page_content=chunk,
                metadata={
                    "doc_id": _make_doc_id(docx_file, 0, chunk_index),
                    "title": docx_file.stem,
                    "source_file": _source_file_value(docx_file),
                    "source_type": "docx",
                    "page": None,
                    "chunk_id": chunk_index,
                },
            )
        )
    return documents


def _extract_doc_text(doc_file: Path) -> str:
    doc_path = doc_file.resolve()
    if not doc_path.exists():
        raise FileNotFoundError(f"DOC 文件不存在: {doc_path}")

    with tempfile.TemporaryDirectory(prefix="rag_doc_", ignore_cleanup_errors=True) as tmp_dir:
        txt_path = Path(tmp_dir) / f"{doc_path.stem}.txt"
        _convert_doc_to_unicode_text(doc_path, txt_path)
        text = txt_path.read_text(encoding="gbk")
        text = _clean_text(text)
        if not text:
            raise ValueError(f"DOC 文件未提取到有效文本: {doc_path}")
        return text


def _convert_doc_to_unicode_text(doc_path: Path, txt_path: Path) -> None:
    script = r"""
param(
    [Parameter(Mandatory=$true)][string]$InputPath,
    [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference = 'Stop'
$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $readOnly = $true
    $confirmConversions = $false
    $addToRecentFiles = $false
    $doc = $word.Documents.Open([ref]$InputPath, [ref]$confirmConversions, [ref]$readOnly, [ref]$addToRecentFiles)
    $unicodeTextFormat = 7
    $doc.SaveAs2([ref]$OutputPath, [ref]$unicodeTextFormat)
}
finally {
    if ($doc -ne $null) {
        $saveChanges = $false
        $doc.Close([ref]$saveChanges)
    }
    if ($word -ne $null) {
        $word.Quit()
    }
}
"""
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", encoding="utf-8", delete=False) as script_file:
        script_file.write(script)
        script_path = Path(script_file.name)

    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                "-InputPath",
                str(doc_path),
                "-OutputPath",
                str(txt_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    finally:
        script_path.unlink(missing_ok=True)

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"DOC 文件读取失败: {doc_path}\n{detail}")
    if not txt_path.exists():
        raise RuntimeError(f"DOC 转换未生成文本文件: {doc_path}")


def _extract_docx_text(docx_file: Path) -> str:
    paragraphs: list[str] = []
    with zipfile.ZipFile(docx_file) as archive:
        xml_bytes = archive.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    for para in root.findall(".//w:p", namespace):
        texts = [node.text or "" for node in para.findall(".//w:t", namespace)]
        paragraph = _clean_text("".join(texts))
        if paragraph:
            paragraphs.append(paragraph)
    return "\n".join(paragraphs)


def _load_faq_documents(faq_path: Path) -> list[Document]:
    if not faq_path.exists():
        raise FileNotFoundError(f"FAQ 知识文件不存在: {faq_path}")

    with open(faq_path, "r", encoding="utf-8") as f:
        faq_data = json.load(f)

    documents: list[Document] = []
    for index, item in enumerate(faq_data.get("faqs", []), start=1):
        question = _clean_text(str(item.get("question", "")))
        answer = _clean_text(str(item.get("answer", "")))
        if not question or not answer:
            raise ValueError(f"FAQ 条目缺少 question 或 answer: index={index}")

        text = f"常见问法：{question}\n权威答案：{answer}"
        source_id = str(item.get("id", f"FAQ{index:03d}"))
        documents.append(
            Document(
                page_content=text,
                metadata={
                    "doc_id": f"faq:{source_id}",
                    "title": f"FAQ {source_id}",
                    "source_file": _source_file_value(faq_path),
                    "source_type": "faq_json",
                    "page": None,
                    "chunk_id": index,
                    "category": item.get("category", ""),
                    "updated_at": faq_data.get("last_updated", ""),
                },
            )
        )
    return documents


def _clean_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[。！？；])", text)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_text(sentence, max_chars, overlap))
            continue

        if len(current) + len(sentence) > max_chars:
            chunks.append(current)
            current = current[-overlap:] + sentence if overlap > 0 else sentence
        else:
            current += sentence

    if current:
        chunks.append(current)

    return [chunk for chunk in chunks if chunk.strip()]


def _split_long_text(text: str, max_chars: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    step = max_chars - overlap
    if step <= 0:
        raise ValueError("overlap 必须小于 max_chars")

    for start in range(0, len(text), step):
        chunk = text[start:start + max_chars].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _make_doc_id(path: Path, page: int | None, chunk: int) -> str:
    raw = f"{path.name}:{page}:{chunk}"
    return raw


def _source_file_value(path: Path) -> str:
    resolved = path.resolve()
    project_root = Path.cwd().resolve()
    try:
        return str(resolved.relative_to(project_root))
    except ValueError:
        return str(resolved)


def _deduplicate_documents(documents: list[Document]) -> list[Document]:
    seen: set[str] = set()
    unique: list[Document] = []
    for doc in documents:
        key = doc.page_content
        if key in seen:
            continue
        seen.add(key)
        unique.append(doc)
    return unique

if __name__ == "__main__":
    data = load_pdfs_from_dir("./data/kb_docs")
    print(len(data))

    out = open("all_text.txt", "w", encoding="utf-8")
    for line in data:
        line = line.strip("\n")
        out.write(line)
        out.write("\n")
    out.close()
