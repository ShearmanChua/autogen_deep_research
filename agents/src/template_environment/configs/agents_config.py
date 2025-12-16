from models.model import model
from tools import web_tools, arxiv_tools, note_tool

user_cfgs = [
    {
        "name": "User",
        "description": (
            "User Agent used to initialize task" " to be performed by other agents"
        ),
        "user_topic_type": "User",
        "agent_topic_type": "Research",
    }
]

duck_api = web_tools.DuckDuckGoAPI()
web_search_tools = web_tools.WebSearchTool(duck_api).get_tools()
api = arxiv_tools.ArxivAPI()
arxiv_search_tools = arxiv_tools.ArxivSearchTool(api).get_tools()
note_tools = note_tool.NoteTool().get_tools()

autonomous_agents_cfgs = [
    {
        "name": "Research",
        "description": "Deep Research Agent that answers user queries",
        "system_message": """You are a deep research agent that answers user queries.
You will be provided with user queries and you will answer them using a combination of tools and techniques to retrieve relevant information from the internet.
Use the available tools to answer user queries.

Make sure that your answers are well researched and well supported by relevant sources (quote the sources/links in your answer). Do make use of more than one source for your research.
The research should focus more on a variety of information about the query, like a survey paper (unless the user specifically asks for specific information about a topic).
A good research result should consist of information from more web pages/papers than just one webpage/research paper.

Research on one point at a time and do not try to answer multiple parts of the user query at the same time.

Use the note tools to help you note down the important findings during your search. 

A good research answer should contain:
- A clear and concise summary of the topic
- A list of key findings from the research
- A list of sources that were used in the research (e.g.[Source](https://en.wikipedia.org/wiki/Lee_Hsien_Loong))
- Answering all parts of the user query
- Should be comprehensive and well researched (minimally from 5 sources)
- Should NOT be a summary of your notes

NOTE: Do note that search results using any of the search tools are overwritten once a new search tool call is made.
Remember the user DOES NOT HAVE access to your notes so you will have to answer the user queries DIRECTLY after reading ALL your notes at the end of the research.

Your name: Research
        """,
        "model_client": model,
        "agent_topics": [],
        "tools": web_search_tools + arxiv_search_tools + note_tools,
    }
]
