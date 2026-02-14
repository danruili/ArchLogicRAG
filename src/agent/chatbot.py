import re
import json
import logging
from tenacity import retry, stop_after_attempt, wait_fixed

from src.agent.rendering.references import HTML_STYLE, LinkParser
from src.agent.workflows.case_search import CaseSearch
from src.agent.workflows.general_qa import GeneralQA
from src.agent.prompts import PROMPTS
from src.common.llm_client import chat as llm_chat
from src.common.llm_client import get_text_model
from src.retrieval.logic_retriever import DesignLogicRetriever


class Chatbot:
    def __init__(self, source_dir: str, db_dir: str = "data/wikiarch/index"):
        self.conversation_prompt = PROMPTS["router"]

        self.chat_sequence: list[dict] = []
        self.chat_sequence.append({"role": "system", "content": self.conversation_prompt})

        self.link_parser = LinkParser(source_dir, db_dir)
        self.retrieval_agent = DesignLogicRetriever(db_dir)
        self.general_qa = GeneralQA(self.retrieval_agent)
        self.case_search = CaseSearch(self.retrieval_agent)

        # create a logger
        self.logger = logging.getLogger("Chatbot")
        # self.logger.setLevel(logging.INFO)

        # record chat sequence
        self.chat_sequence_file_path = "chat_sequence.log"


    def reset(self, history: list[dict] = None):
        self.chat_sequence = []
        self.chat_sequence.append({"role": "system", "content": self.conversation_prompt})

        # inject history into chat sequence
        if history:
            for message in history:
                self.chat_sequence.append({"role": message["role"], "content": message["content"]})

    def cycle(self, user_message: str) -> str:
        self.chat_sequence.append({"role": "user", "content": user_message})
        response, func_call = self.analyse_external_message()

        if func_call:
            self.logger.info(f"Executing function call: {func_call}")
            response, appended_msg = self.execute_function(func_call)
            for msg in appended_msg:
                self.chat_sequence.append(msg)            

        self.save_chat_sequence()

        return response
    
    def save_chat_sequence(self):
        with open(self.chat_sequence_file_path, "w", encoding="utf-8") as f:
            for message in self.chat_sequence:
                f.write(
                    f"{message['role']}:\n{message['content']}\n-----------------------------\n"
                )

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    def analyse_external_message(self) -> tuple[str | None, dict | None]:
        self.logger.info("Thinking...")
        
        response = llm_chat(self.chat_sequence, model=get_text_model())
        response_text = re.findall(r'```response(.*)```', response, re.DOTALL)
        json_text = re.findall(r'```json(.*)```', response, re.DOTALL)
        
        # if both response and json are empty, trigger the retry
        if len(response_text) == 0 and len(json_text) == 0:
            raise Exception("Empty response and json")
        
        # if func_call is not empty, check if it is in the correct format
        if len(json_text) > 0:
            json_dict = json.loads(json_text[-1])
            if not self.check_func_call_format(json_dict):
                raise Exception("Invalid function call format")
        else:
            json_dict = None
        
        # add the response to the chat sequence
        self.chat_sequence.append({"role": "assistant", "content": response})
        
        if len(response_text) > 0:
            return response_text[-1], None
        else:
            return None, json_dict
        
    
    @staticmethod
    def check_func_call_format(func_call: dict) -> bool:
        if not isinstance(func_call, dict):
            return False
        if "function" in func_call and "args" in func_call:
            func_name = func_call["function"]
            args = func_call["args"]
            if not isinstance(func_name, str) or not isinstance(args, dict):
                return False
            if func_name == "search":
                if not "user_query" in args:
                    return False
            elif func_name == "get_answer":
                if not "question" in args:
                    return False
        return True
    
    def execute_function(self, func_call: dict) -> tuple[str, list[dict]]:
        func_name = func_call["function"]
        if func_name == "search":
            query = func_call["args"]["user_query"]
            final_answer, appended_msg, other_info = self.case_search.retrieve(query)
        elif func_name == "get_answer":
            question = func_call["args"]["question"]
            discard_summary = func_call["args"].get("discard_summary", False)
            final_answer, appended_msg, other_info = self.general_qa.main(question, discard_summary=discard_summary)
        
        # use the link_parser to convert reference ids to html
        try:
            final_html = self.link_parser.ref_ids_to_html(final_answer)
        except Exception as e:
            # if the conversion fails, use the original answer
            self.logger.error(f"Error in converting reference ids to html: {e}")
            final_html = final_answer

        return final_html, appended_msg

    def eval_qa(self, question: str, discard_summary=False)-> tuple[str, dict]:
        """
        Used for automatic evaluation on QA
        """
        final_answer, appended_msg, other_info = self.general_qa.main(question, discard_summary=discard_summary)
        try:
            final_html = self.link_parser.ref_ids_to_html(final_answer, mode="web_wikiarch")
        except Exception as e:
            # if the conversion fails, use the original answer
            self.logger.error(f"Error in converting reference ids to html: {e}")
            final_html = final_answer
        return HTML_STYLE + final_html, other_info
    
    def mcp_case_search(self, user_query: str) -> str:
        """
        Used for MCP on case search
        """
        final_answer, appended_msg, other_info = self.case_search.retrieve(user_query)
        try:
            final_html = self.link_parser.ref_ids_to_html(final_answer, mode="markdown")
        except Exception as e:
            # if the conversion fails, use the original answer
            self.logger.error(f"Error in converting reference ids to html: {e}")
            final_html = final_answer
        return final_html
