import logging
import re

from tenacity import retry, stop_after_attempt, wait_fixed

from src.agent.prompts import PROMPTS
from src.common.llm_client import chat as llm_chat
from src.common.llm_client import get_text_model
from src.retrieval.logic_retriever import DesignLogicRetriever


class CaseSearch:
    def __init__(self, retrieval_agent: DesignLogicRetriever):
        self.retrieval_agent = retrieval_agent
        self.logger = logging.getLogger("CaseSearch")

    def retrieve(self, user_query: str) -> tuple[str, list[dict], dict]:
        """
        Retrieve and analyze retrieval results with an LLM.
        """
        chat_sequence: list[dict] = [{"role": "system", "content": PROMPTS["case_search"]}]

        self.logger.info(f"Retrieving cases for query: {user_query}...")
        textual_result, _ = self.retrieval_agent.qa_retrieve(user_query)
        self.logger.info(f"\033[90mRaw retrieval result: {textual_result}\033[0m")

        self.logger.info(f"Synthesizing results for query: {user_query}...")
        user_input = f"Query: {user_query}\nAPI Response: ```text\n{textual_result}```"
        chat_sequence.append({"role": "user", "content": user_input})
        final_result, other_info = self.__analyse_external_message(chat_sequence)

        appended_message = [{"role": "user", "content": other_info["llm_response"]}]
        return final_result, appended_message, {}

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    def __analyse_external_message(self, chat_sequence: list[dict]) -> tuple[str, dict]:
        self.logger.info("Thinking...")

        response = llm_chat(chat_sequence, model=get_text_model())
        matches = re.findall(r"```response(.*)```", response, re.DOTALL)
        response_text = matches[-1].strip() if matches else ""

        if not response_text:
            raise Exception("Empty response")

        return response_text, {"llm_response": response}
