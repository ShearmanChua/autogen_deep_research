import os
import re
from autogen_core.tools import FunctionTool

from tools.tool_tracing_utils import trace_span_info

def write_string(text, directory="./notes"):
    """
    Writes `text` to a new txt file
    """
    
    file_path = os.path.join(directory, f"current_run.txt")

    # Write text to file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)

    return

class NoteTool:
    """
    Async tool to manage research notes in Markdown format with sections and subsections.

    Features:
    - Create and manage sections (# Heading) and subsections (## Heading)
    - Write, edit, delete, and read notes
    - List all sections and subsections
    - Read the entire note as a Markdown string

    All functions are async and can be used with an agent.
    """

    def __init__(self):
        # Structure: {section_name: {"content": str, "subsections": {sub_name: content}}}
        self.sections = {}
        self._tools = [
            FunctionTool(self.create_note_section, name="create_note_section", description=self.create_note_section.__doc__),
            FunctionTool(self.create_note_subsection, name="create_note_subsection", description=self.create_note_subsection.__doc__),
            FunctionTool(self.write_notes, name="write_notes", description=self.write_notes.__doc__),
            FunctionTool(self.read_note_section, name="read_note_section", description=self.read_note_section.__doc__),
            FunctionTool(self.read_all_notes, name="read_all_notes", description=self.read_all_notes.__doc__),
            FunctionTool(self.edit_note_section, name="edit_note_section", description=self.edit_note_section.__doc__),
            FunctionTool(self.list_note_sections, name="list_note_sections", description=self.list_note_sections.__doc__),
            FunctionTool(self.delete_note_section, name="delete_note_section", description=self.delete_note_section.__doc__),
        ]

    # -----------------------------
    # CREATE
    # -----------------------------
    @trace_span_info
    async def create_note_section(self, section_name: str):
        """
        Create a top-level section in the note with a # Markdown heading.

        Parameters
        ----------
        section_name : str
            Name of the section (e.g., "Introduction"). Do NOT include '#' characters.

        Returns
        -------
        dict
            Success or error message.
        """
        if section_name in self.sections:
            return {"error": f"Section '{section_name}' already exists."}
        self.sections[section_name] = {"content": "", "subsections": {}}
        return {"success": f"Section '{section_name}' created."}

    @trace_span_info
    async def create_note_subsection(self, parent_section: str, subsection_name: str):
        """
        Create a subsection under a parent section in the note with a ## Markdown heading.

        Parameters
        ----------
        parent_section : str
            Name of the existing parent section.
        subsection_name : str
            Name of the subsection. Do NOT include '##' characters.

        Returns
        -------
        dict
            Success or error message.
        """
        if parent_section not in self.sections:
            return {"error": f"Parent section '{parent_section}' does not exist."}
        if subsection_name in self.sections[parent_section]["subsections"]:
            return {"error": f"Subsection '{subsection_name}' already exists under '{parent_section}'."}
        self.sections[parent_section]["subsections"][subsection_name] = ""
        return {"success": f"Subsection '{subsection_name}' created under '{parent_section}'."}

    # -----------------------------
    # WRITE
    # -----------------------------
    @trace_span_info
    async def write_notes(self, section_name: str, text: str, subsection_name: str = ""):
        """
        Write notes based on current research progress so that it can be easily referenced later.
        Notes should include key findings from the research, and MUST include their sources (e.g. cited from https://mwi.westpoint.edu/planes/).

        Notes:
        - At least one section must exist before writing.
        - For subsections, provide the parent section name and the subsection name.
        - Text will be appended to existing content.

        Parameters
        ----------
        section_name : str
            Section to write to.
        text : str
            The note text to append.
        subsection_name : str, optional
            Name of the subsection to write to (if writing to a subsection).

        Returns
        -------
        dict
            Success or error message.
        """
        if not self.sections:
            return {"error": "No sections exist. Create a section first."}

        if subsection_name:
            if section_name not in self.sections or subsection_name not in self.sections[section_name]["subsections"]:
                return {"error": f"Subsection '{subsection_name}' under '{section_name}' does not exist."}
            self.sections[section_name]["subsections"][subsection_name] += text + "\n"
            return {"success": f"Text added to subsection '{subsection_name}'."}
        else:
            if section_name not in self.sections:
                return {"error": f"Section '{section_name}' does not exist."}
            self.sections[section_name]["content"] += text + "\n"
            return {"success": f"Text added to section '{section_name}'."}
        


    # -----------------------------
    # EDIT
    # -----------------------------
    @trace_span_info
    async def edit_note_section(self, section_name: str, new_text: str, subsection_name: str = ""):
        """
        Replace content of a section or subsection with new text.

        Parameters
        ----------
        section_name : str
            Section to edit.
        new_text : str
            New text to replace existing content.
        subsection_name : str, optional
            Name of the subsection to edit.

        Returns
        -------
        dict
            Success or error message.
        """
        if subsection_name:
            if section_name not in self.sections or subsection_name not in self.sections[section_name]["subsections"]:
                return {"error": f"Subsection '{subsection_name}' under '{section_name}' does not exist."}
            self.sections[section_name]["subsections"][subsection_name] = new_text + "\n"
            return {"success": f"Subsection '{subsection_name}' updated."}
        else:
            if section_name not in self.sections:
                return {"error": f"Section '{section_name}' does not exist."}
            self.sections[section_name]["content"] = new_text + "\n"
            return {"success": f"Section '{section_name}' updated."}

    # -----------------------------
    # DELETE
    # -----------------------------
    @trace_span_info
    async def delete_note_section(self, section_name: str, subsection_name: str = ""):
        """
        Delete a section or subsection.

        Parameters
        ----------
        section_name : str
            Section to delete.
        subsection_name : str, optional
            Subsection to delete. If omitted, deletes the whole section.

        Returns
        -------
        dict
            Success or error message.
        """
        if subsection_name:
            if section_name not in self.sections or subsection_name not in self.sections[section_name]["subsections"]:
                return {"error": f"Subsection '{subsection_name}' under '{section_name}' does not exist."}
            del self.sections[section_name]["subsections"][subsection_name]
            return {"success": f"Subsection '{subsection_name}' deleted."}
        else:
            if section_name not in self.sections:
                return {"error": f"Section '{section_name}' does not exist."}
            del self.sections[section_name]
            return {"success": f"Section '{section_name}' deleted."}

    # -----------------------------
    # LIST
    # -----------------------------
    @trace_span_info
    async def list_note_sections(self):
        """
        List all sections and subsections.

        Returns
        -------
        dict
            {section_name: [list_of_subsection_names]}
        """
        return {sec: list(data["subsections"].keys()) for sec, data in self.sections.items()}

    # -----------------------------
    # READ
    # -----------------------------
    @trace_span_info
    async def read_note_section(self, section_name: str, subsection_name: str = ""):
        """
        Read the content of a section or subsection.

        Notes:
        - Pass section/subsection names without '#' or '##'.
        - The returned content includes the Markdown heading (e.g., '# Introduction' or '## Motivation').

        Parameters
        ----------
        section_name : str
            Section to read.
        subsection_name : str, optional
            Subsection to read.

        Returns
        -------
        str or dict
            Content of the section/subsection with heading, or an error message.
        """
        if subsection_name:
            if section_name not in self.sections or subsection_name not in self.sections[section_name]["subsections"]:
                return {"error": f"Subsection '{subsection_name}' under '{section_name}' does not exist."}
            content = f"## {subsection_name}\n{self.sections[section_name]['subsections'][subsection_name]}"
            return content
        else:
            if section_name not in self.sections:
                return {"error": f"Section '{section_name}' does not exist."}
            content = f"# {section_name}\n{self.sections[section_name]['content']}"
            for sub, sub_content in self.sections[section_name]["subsections"].items():
                content += f"## {sub}\n{sub_content}"
            return content

    @trace_span_info
    async def read_all_notes(self):
        """
        Return the full Markdown string with all sections and subsections, including headings.

        Returns
        -------
        str
            Full note content as Markdown.
        """
        markdown = ""
        for sec, data in self.sections.items():
            markdown += f"# {sec}\n{data['content']}"
            for sub, sub_content in data["subsections"].items():
                markdown += f"## {sub}\n{sub_content}"
        write_string(markdown)
        return markdown.strip()
    
    def get_tools(self):
        """Return the list of FunctionTool instances for integration with an agent."""
        return self._tools

