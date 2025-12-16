from autogen_core.tools import FunctionTool
import requests
import xml.etree.ElementTree as ET
from markdownify import markdownify as html_to_md
from pypdf import PdfReader
import re
import io

from tools.tool_tracing_utils import trace_span_info

# ------------------------------------------------------------
# Text Normalization Helper
# ------------------------------------------------------------
def clean_text(text: str) -> str:
    """
    Clean and normalize extracted text.

    Operations performed:
    - Remove tab characters.
    - Collapse 3 or more consecutive newlines into exactly 2.
    - Collapse multiple consecutive spaces into one.
    - Strip leading/trailing whitespace from each line.
    - Strip whitespace at the document edges.

    Parameters
    ----------
    text : str
        Raw text extracted from PDF or HTML.

    Returns
    -------
    str
        Cleaned, compact, readable text.
    """
    if not text:
        return text

    text = text.replace("\t", " ")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines())

    return text.strip()


# ------------------------------------------------------------
# PDF Content Reader — Provides Scrolling Windows
# ------------------------------------------------------------
class ArxivPaperReader:
    """
    Extracts text from a PDF and provides scrollable "windows" of content.

    This allows an LLM agent to read a paper chunk-by-chunk, simulating
    a scrolling browser window.

    Attributes
    ----------
    window_size : int
        Number of characters per window.
    windows : list[str]
        The split windows of text.
    position : int
        Current window index.
    """

    def __init__(self, window_size_chars=3000):
        """
        Initialize the reader.

        Parameters
        ----------
        window_size_chars : int, optional
            Maximum size of each scrolling window, by async default 3000.
        """
        self.window_size = window_size_chars
        self.windows = []
        self.position = 0

    async def load_pdf(self, pdf_url: str) -> int:
        """
        Download and parse a PDF from a URL, extract text, clean it,
        and split into windows.

        Parameters
        ----------
        pdf_url : str
            Direct URL to the PDF.

        Returns
        -------
        int
            Number of windows created.
        """
        response = requests.get(pdf_url, timeout=15)
        response.raise_for_status()

        reader = PdfReader(io.BytesIO(response.content))
        full_text = ""

        for page in reader.pages:
            extracted = page.extract_text() or ""
            full_text += extracted + "\n\n"

        full_text = clean_text(full_text)

        self.windows = [
            full_text[i:i + self.window_size]
            for i in range(0, len(full_text), self.window_size)
        ]
        self.position = 0

        return len(self.windows)

    async def get_window(self, index: int) -> str:
        """
        Return a specific window of text.

        Parameters
        ----------
        index : int
            Window index.

        Returns
        -------
        str or dict
            Text of the window, or error dict if out of range.
        """
        if index < 0 or index >= len(self.windows):
            return {"error": "Window index out of range"}
        return self.windows[index]

    async def next_window(self) -> str:
        """
        Move to the next window.

        Returns
        -------
        str or dict
            Next window text or error dict.
        """
        if self.position + 1 >= len(self.windows):
            return {"error": "Already at last window"}
        self.position += 1
        return await self.get_window(self.position)

    async def prev_window(self) -> str:
        """
        Move to the previous window.

        Returns
        -------
        str or dict
            Previous window text or error dict.
        """
        if self.position - 1 < 0:
            return {"error": "Already at first window"}
        self.position -= 1
        return await self.get_window(self.position)


# ------------------------------------------------------------
# ArXiv API Wrapper
# ------------------------------------------------------------
class ArxivAPI:
    """
    A minimal wrapper around the ArXiv API, supporting searching
    and extracting metadata needed to locate PDFs.

    Methods
    -------
    search(query, page, max_results)
        Perform a paginated ArXiv search.
    """

    ARXIV_URL = "http://export.arxiv.org/api/query"

    async def search(self, query: str, page: int = 1, max_results: int = 10):
        """
        Perform an ArXiv search using the official API.

        Parameters
        ----------
        query : str
            Search query (e.g., "machine learning", "cat:cs.CL").
        page : int, optional
            Page number (converted into API 'start' parameter).
        max_results : int, optional
            Number of items per page.

        Returns
        -------
        list[dict]
            List of paper metadata dictionaries, each containing:
            - id
            - title
            - authors
            - summary
            - pdf_url
        """
        start = (page - 1) * max_results

        params = {"search_query": query, "start": start, "max_results": max_results}
        response = requests.get(self.ARXIV_URL, params=params, timeout=10)
        response.raise_for_status()

        root = ET.fromstring(response.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        results = []

        for i, entry in enumerate(root.findall("atom:entry", ns)):
            title = entry.find("atom:title", ns).text.strip()
            summary = entry.find("atom:summary", ns).text.strip()
            authors = [a.find("atom:name", ns).text.strip()
                       for a in entry.findall("atom:author", ns)]

            # Extract PDF link
            pdf_url = None
            for link in entry.findall("atom:link", ns):
                if link.attrib.get("title") == "pdf":
                    pdf_url = link.attrib["href"]

            if not pdf_url:
                id_url = entry.find("atom:id", ns).text
                pdf_url = id_url.replace("abs", "pdf")

            results.append({
                "id": i,
                "title": title,
                "authors": authors,
                "summary": summary,
                "pdf_url": pdf_url,
            })

        return results


# ------------------------------------------------------------
# Autogen-Compatible Tool Wrapper
# ------------------------------------------------------------
class ArxivSearchTool:
    """
    Provides an Autogen FunctionTool interface for:
    - ArXiv search
    - Opening a paper
    - Scrolling through PDF content in windows
    - Changing pages of search results

    This class is designed to be plugged directly into an Autogen agent.
    """

    def __init__(self, api: ArxivAPI, window_size_chars: int = 3000):
        """
        Initialize the tool.

        Parameters
        ----------
        api : ArxivAPI
            Backend API used for searching.
        window_size_chars : int, optional
            Size of PDF text windows for scrolling.
        """
        self.api = api
        self.current_query = None
        self.current_page = 1
        self.current_results = []

        # Reader for opened PDFs
        self.reader = ArxivPaperReader(window_size_chars)

        # Tools exposed to Autogen
        self.search_tool = FunctionTool(self.search, name="search_arxiv", description=self.search.__doc__)
        self.select_tool = FunctionTool(self.open_paper, name="open_paper", description=self.open_paper.__doc__)
        self.next_win_tool = FunctionTool(self.next_window, name="next_window", description=self.next_window.__doc__)
        self.prev_win_tool = FunctionTool(self.prev_window, name="prev_window", description=self.prev_window.__doc__)
        self.go_win_tool = FunctionTool(self.get_window, name="read_window", description=self.get_window.__doc__)
        self.next_page_tool = FunctionTool(self.next_page, name="next_arxiv_page", description=self.next_page.__doc__)
        self.abstract_tool = FunctionTool(self.get_abstract, name="get_abstract", description=self.get_abstract.__doc__)
        self.keyword_tool = FunctionTool(self.keyword_search, name="search_keyword", description=self.keyword_search.__doc__)


    # ------------------- SEARCH -------------------

    @trace_span_info
    async def search(self, query: str, page: int = 1):
        """
        Search ArXiv for academic papers and store results.

        **Useful for research questions that requires academic knowledge (e.g., machine learning).**

        WARNING: Search results get replaced when a new query is performed. Therefore,
        you should ONLY perform one query at a time and open the required results/papers before
        moving onto the next query.

        e.g. workflow: search -> get_abstract -> next_page -> open_paper -> search

        Parameters
        ----------
        query : str
            Search keyword or category.
        page : int, optional
            Page number to fetch.

        Returns
        -------
        dict
            Search metadata including results list.
        """
        self.current_query = query
        self.current_page = page
        self.current_results = await self.api.search(query, page)

        return {
            "query": query,
            "page": page,
            "results": self.current_results
        }
    
    @trace_span_info
    async def get_abstract(self, result_id: int):
        """
        Return the abstract (summary) of a paper from the current search results.
        NOTE: Try to use this function instead of `open_paper` unless more information
        about the paper (e.g. implementation, code) is needed.

        Parameters
        ----------
        result_id : int
            Index of the paper in the current search results.

        Returns
        -------
        dict
            Dictionary containing title, authors, and abstract (summary).
        """
        if not self.current_results:
            return {"error": "No active search results."}

        if result_id < 0 or result_id >= len(self.current_results):
            return {"error": "Invalid result_id."}

        paper = self.current_results[result_id]

        return {
            "title": paper["title"],
            "authors": paper["authors"],
            "abstract": paper["summary"]
        }

    # ------------------- OPEN PAPER + LOAD PDF -------------------
    @trace_span_info
    async def open_paper(self, result_id: int):
        """
        Open a paper by ID from the current search results,
        download the PDF, extract text, and create windows.

        Parameters
        ----------
        result_id : int
            Index of the paper in current results.

        Returns
        -------
        dict
            Paper metadata and first window of content.
        """
        if not self.current_results:
            return {"error": "No active search results."}

        if result_id < 0 or result_id >= len(self.current_results):
            return {"error": "Invalid result_id."}

        paper = self.current_results[result_id]
        pdf_url = paper["pdf_url"]
        num_windows = await self.reader.load_pdf(pdf_url)

        return {
            "title": paper["title"],
            "authors": paper["authors"],
            "total_windows": num_windows,
            "first_window": await self.reader.get_window(0)
        }
    
    @trace_span_info
    async def keyword_search(self, keyword: str, window_words: int = 256):
        """
        Search for a single keyword in the currently opened paper and return 
        context snippets around each match.

        **Only single-word searches are allowed. Multi-word phrases are not supported.**

        Parameters
        ----------
        keyword : str
            A single keyword to search for (case-insensitive).
            If multiple words or a phrase is provided, an error is returned.
        window_words : int, optional
            Number of words before and after the keyword to include in each context snippet.

        Returns
        -------
        dict
            {
                "keyword": keyword,
                "total_matches": N,
                "matches": [
                    {
                        "index": match_number,
                        "context": "...window_words before [keyword] window_words after..."
                    },
                    ...
                ]
            }
            If invalid input is provided (multi-word), returns an error message.
        """

        # -----------------------------
        # Validate input: single word only
        # -----------------------------
        if not keyword or len(keyword.strip().split()) != 1:
            return {"error": "Only single-word searches are allowed."}

        if not self.reader.windows:
            return {"error": "No PDF loaded. Use open_paper first."}

        keyword_lower = keyword.lower()

        # Reconstruct full paper text
        full_text = " ".join(self.reader.windows)
        words = full_text.split()

        matches = []

        # -----------------------------
        # Word-level search
        # -----------------------------
        for i, w in enumerate(words):
            # clean punctuation
            w_clean = re.sub(r"[^\w-]", "", w).lower()
            if w_clean == keyword_lower:
                start = max(0, i - window_words)
                end = min(len(words), i + window_words + 1)
                snippet_words = words[start:end]
                snippet = " ".join(snippet_words)

                # highlight the keyword
                highlighted = re.sub(
                    rf"(?i)\b({re.escape(keyword_lower)})\b",
                    r"**\1**",
                    snippet
                )

                matches.append({
                    "index": len(matches),
                    "context": highlighted
                })

        if not matches:
            return {
                "keyword": keyword,
                "matches": [],
                "message": "No matches found."
            }

        return {
            "keyword": keyword,
            "total_matches": len(matches),
            "matches": matches
        }



    # ------------------- WINDOW CONTROLS -------------------
    @trace_span_info
    async def next_window(self):
        """
        Move forward one window in the opened paper.
        Try to use 'keyword_search' instead, unless you are not getting the required results.

        Returns
        -------
        str or dict
            Window text or error dictionary.
        """
        return await self.reader.next_window()
    @trace_span_info
    async def prev_window(self):
        """
        Move backward one window in the opened paper.

        Returns
        -------
        str or dict
            Window text or error dictionary.
        """
        return await self.reader.prev_window()
    @trace_span_info
    async def get_window(self, index: int):
        """
        Jump to a specific window.

        Parameters
        ----------
        index : int
            Window index.

        Returns
        -------
        str or dict
            Window text or error dictionary.
        """
        return await self.reader.get_window(index)

    # ------------------- SEARCH PAGE NAVIGATION -------------------
    @trace_span_info
    async def next_page(self):
        """
        Fetch the next page of search results for the current query.

        Returns
        -------
        dict
            New search results.
        """
        if not self.current_query:
            return {"error": "No active query"}

        self.current_page += 1
        self.current_results = await self.api.search(self.current_query, self.current_page)

        return {
            "query": self.current_query,
            "page": self.current_page,
            "results": self.current_results
        }
    
    def get_tools(self):
        return [
            self.search_tool,
            self.select_tool,
            # self.abstract_tool,
            self.keyword_tool,
            self.next_win_tool,
            self.prev_win_tool,
            self.go_win_tool,
            self.next_page_tool
        ]