import copy
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from tenacity import retry, stop_after_attempt, wait_fixed

from src.agent.prompts import PROMPTS
from src.common.llm_client import chat as llm_chat
from src.common.llm_client import get_text_model, count_tokens
from src.retrieval.logic_retriever import DesignLogicRetriever





def _chat(messages: list[dict], model: str | None = None) -> str:
    return llm_chat(messages, model=model or get_text_model())


class GeneralQA:
    def __init__(self, retriever: DesignLogicRetriever):
        self.retrieval_agent = retriever
        self.logger = logging.getLogger("GeneralQA")

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    def _general_qa_planner(
        self,
        user_question: str,
        discard_summary: bool = False,
    ) -> tuple[dict, dict]:
        planning_chat_sequence: list[dict] = []
        planning_chat_sequence.append({"role": "system", "content": PROMPTS["qa_naive"]})
        planning_chat_sequence.append({"role": "user", "content": user_question})
        naive_result = _chat(planning_chat_sequence)
        planning_chat_sequence.append({"role": "assistant", "content": naive_result})

        planning_chat_sequence.append({"role": "system", "content": PROMPTS["qa_plan_reformat"]})
        naive_json_response = _chat(planning_chat_sequence)
        planning_chat_sequence.append({"role": "assistant", "content": naive_json_response})

        retrieved_non_summary, _ = self.retrieval_agent.qa_retrieve(user_question, drop_summary=True)
        retrieved_summary, _ = self.retrieval_agent.qa_retrieve(
            user_question, drop_non_summary=True
        )
        retrieved_summary_token_length = count_tokens(retrieved_summary)

        planning_chat_sequence.append(
            {
                "role": "user",
                "content": PROMPTS["qa_plan_improve"].format(retrieved_docs=retrieved_summary),
            }
        )
        refined_with_summary = _chat(planning_chat_sequence)
        planning_chat_sequence.pop()

        planning_chat_sequence.append(
            {
                "role": "user",
                "content": PROMPTS["qa_plan_improve"].format(retrieved_docs=retrieved_non_summary),
            }
        )
        refined_with_non_summary = _chat(planning_chat_sequence)
        planning_chat_sequence.pop()

        try:
            refined_with_summary_text = re.findall(r"```json(.*)```", refined_with_summary, re.DOTALL)
            assert len(refined_with_summary_text) > 0
            refined_outline_str = refined_with_summary_text[-1]
            reorg_outline_response = _chat(
                [
                    {
                        "role": "user",
                        "content": PROMPTS["outline_reorganizer"].format(
                            user_question=user_question,
                            answer_outline=refined_outline_str,
                        ),
                    }
                ]
            )
            refined_with_summary_text = re.findall(
                r"```json(.*)```", reorg_outline_response, re.DOTALL
            )
            assert len(refined_with_summary_text) > 0
            refined_with_summary_json = json.loads(refined_with_summary_text[-1])
            assert self.__check_planning_json_format(refined_with_summary_json)

            refined_with_non_summary_text = re.findall(
                r"```json(.*)```", refined_with_non_summary, re.DOTALL
            )
            assert len(refined_with_non_summary_text) > 0
            refined_with_non_summary_text = refined_with_non_summary_text[-1]
            reorg_outline_response = _chat(
                [
                    {
                        "role": "user",
                        "content": PROMPTS["outline_reorganizer"].format(
                            user_question=user_question,
                            answer_outline=refined_with_non_summary_text,
                        ),
                    }
                ]
            )
            refined_with_non_summary_text = re.findall(
                r"```json(.*)```", reorg_outline_response, re.DOTALL
            )
            assert len(refined_with_non_summary_text) > 0
            refined_with_non_summary_json = json.loads(refined_with_non_summary_text[-1])
            assert self.__check_planning_json_format(refined_with_non_summary_json)

            naive_json_response_text = re.findall(r"```json(.*)```", naive_json_response, re.DOTALL)
            naive_json = json.loads(naive_json_response_text[-1])
        except json.JSONDecodeError:
            raise Exception("Invalid JSON response")

        return refined_with_summary_json, {
            "naive_answer": naive_result,
            "naive_outline": naive_json,
            "refined_outline_using_non_summary": refined_with_non_summary_json,
            "retrieved_summary_token_length": retrieved_summary_token_length,
        }

    @staticmethod
    def __check_planning_json_format(planning_response: dict) -> bool:
        if not isinstance(planning_response, dict):
            return False
        if "answer" not in planning_response:
            return False
        if not isinstance(planning_response["answer"], list):
            return False
        for item in planning_response["answer"]:
            if not isinstance(item, dict):
                return False
            if "section" not in item or "bulletpoint" not in item:
                return False
            if not isinstance(item["section"], str) or not isinstance(item["bulletpoint"], list):
                return False
            for bullet in item["bulletpoint"]:
                if not isinstance(bullet, str):
                    return False
        return True

    def _general_qa_summarizer(
        self,
        user_question: str,
        draft_answer: str,
        retrieved_text: str,
    ) -> dict[str, str]:
        content = (
            f"User question: {user_question}\n\n"
            f"Draft answer: {draft_answer}\n\n"
            f"Retrieved documents: {retrieved_text}"
        )
        summarizer_chat_sequence: list[dict] = []
        summarizer_chat_sequence.append({"role": "system", "content": PROMPTS["qa_unit_summarizer"]})
        summarizer_chat_sequence.append({"role": "user", "content": content})
        response = _chat(summarizer_chat_sequence)
        response_text = re.findall(r"```json(.*)```", response, re.DOTALL)

        if len(response_text) == 0:
            raise Exception("Empty response")
        try:
            json_dict = json.loads(response_text[-1])
        except json.JSONDecodeError:
            raise Exception("Invalid JSON response")
        if not isinstance(json_dict, dict) or "title" not in json_dict or "content" not in json_dict:
            raise Exception("Invalid JSON format")
        if not isinstance(json_dict["title"], str) or not isinstance(json_dict["content"], str):
            raise Exception("Invalid JSON format: title or content is not a string")
        return json_dict

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    def _general_qa_reorganizer(
        self,
        user_question: str,
        draft_answer: str,
    ) -> str:
        """
        Reorganize the draft answer based on the user question using LLM.
        Steps:
        1. Generate reorganization instructions using LLM.
        2. Parse the draft answer into sections.
        3. Conduct merges and remove references as per instructions.
        4. Construct the final answer.
        """
        def _strip_leading_section_heading(text: str) -> str:
            """
            Normalize model outputs to section body only.
            Some prompts ask for markdown with a `##` heading, but final assembly
            always adds headings, so we strip one leading heading if present.
            """
            return text
            normalized = text.strip()
            return re.sub(r"^##\s+.+?\n", "", normalized, count=1).strip()

        # Generate reorganization instructions
        instructions_prompt = (
            PROMPTS["qa_reorg_instruction"]
            .replace("{user_question}", user_question)
            .replace("{draft_answer}", draft_answer)
        )
        instructions_rsp = llm_chat(
            [{"role": "user", "content": instructions_prompt}],
            model=get_text_model(),
        )
        # parse the JSON response
        instruction_json_text = re.findall(r"```json(.*?)```", instructions_rsp, re.DOTALL)[-1]
        instructions = json.loads(instruction_json_text)
        intro = instructions.get("intro", "")
        removals = instructions.get("removed_references", {})
        merges = instructions.get("merge", [])
        self.logger.info(f"Reorganization Instructions: {json.dumps(instructions, indent=4)}")

        # Parse the draft answer into sections
        section_pattern = r"## (.+?)\n(.*?)(?=\n## |\Z)"
        sections = re.findall(section_pattern, draft_answer, re.DOTALL)
        section_dict = {title.strip(): content.strip() for title, content in sections}

        # Conduct merges
        new_sections = {}
        processed_sections = set()
        for merge in merges:
            sec1 = merge["section1"]
            sec2 = merge["section2"]
            if sec1 in section_dict and sec2 in section_dict:
                ref_remove_prompt = ""
                ref_to_remove = removals.get(sec1, []) + removals.get(sec2, [])
                if len(ref_to_remove) > 0:
                    ref_remove_prompt = (
                        "- Removed these references and their related analysis: "
                        + ", ".join(ref_to_remove)
                    )
                # use llm to merge the content
                merged_prompt = (
                    PROMPTS["qa_reorg_merge"]
                    .replace("{section1}", section_dict[sec1])
                    .replace("{section2}", section_dict[sec2])
                    .replace("{user_question}", user_question)
                    .replace("{refs_to_remove}", ref_remove_prompt)
                )
                merged_response = llm_chat(
                    [{"role": "user", "content": merged_prompt}],
                    model=get_text_model(),
                )
                merged_content = re.findall(r"```markdown(.*?)```", merged_response, re.DOTALL)[
                    -1
                ].strip()
                # use ## to find the section name
                if merged_content:
                    merged_title_match = re.findall(r"## (.+?)\n", merged_content)
                    if merged_title_match:
                        merged_title = merged_title_match[0].strip()
                        new_sections[merged_title] = _strip_leading_section_heading(
                            merged_content
                        )
                        processed_sections.update([sec1, sec2])

        # remove references for sections that are not merged
        for sec, content in section_dict.items():
            if sec in processed_sections:
                continue
            refs_to_remove = removals.get(sec, [])
            if len(refs_to_remove) > 0:
                content_prompt = (
                    PROMPTS["qa_reorg_remove_refs"]
                    .replace("{section}", content)
                    .replace("{refs_to_remove}", ", ".join(refs_to_remove))
                    .replace("{user_question}", user_question)
                )
                content_rsp = llm_chat(
                    [{"role": "user", "content": content_prompt}],
                    model=get_text_model(),
                )
                cleaned_content = re.findall(r"```markdown(.*?)```", content_rsp, re.DOTALL)
                if cleaned_content:
                    cleaned_content = cleaned_content[-1].strip()
                    new_sections[sec] = _strip_leading_section_heading(cleaned_content)

            # if no refs to remove, keep the original content
            else:
                new_sections[sec] = content

        # Construct the final answer
        final_answer = intro + "\n\n"
        for sec, content in new_sections.items():
            final_answer += f"## {sec}\n{content}\n\n"
        return final_answer

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3))
    def _general_qa_reorganizer_legacy(
        self,
        user_question: str,
        draft_answer: str,
    ) -> str:
        reorganizer_chat_sequence: list[dict] = []
        reorganizer_chat_sequence.append({"role": "system", "content": PROMPTS["qa_reorgnizer"]})
        reorganizer_chat_sequence.append(
            {
                "role": "user",
                "content": f"User question: {user_question}\n\nDraft answer: {draft_answer}",
            }
        )
        return _chat(reorganizer_chat_sequence)

    def main(
        self,
        user_question: str,
        discard_summary: bool = False,
        context_token_limit: int = 60000,
    ) -> tuple[str, list[dict], dict]:
        self.logger.info(f"Planning the answer for: {user_question}...")
        outline, other_info = self._general_qa_planner(
            user_question, discard_summary=discard_summary
        )
        refined_outline = copy.deepcopy(outline)
        _ = context_token_limit - other_info["retrieved_summary_token_length"]

        self.logger.info("Retrieving the relevant documents from the database...")
        case_token = 0
        for item in outline["answer"]:
            bulletpoints = item["bulletpoint"]
            item["retrieved_text"] = []
            for bulletpoint in bulletpoints:
                textual_result, _ = self.retrieval_agent.qa_retrieve(bulletpoint)
                case_token += count_tokens(textual_result)
                item["retrieved_text"].append(textual_result)

        def process_bulletpoint(bulletpoint: str, retrieved_text: str) -> str:
            summary_dict = self._general_qa_summarizer(user_question, bulletpoint, retrieved_text)
            return f"- **{summary_dict['title']}**: {summary_dict['content']}"

        self.logger.info("Summarizing the retrieved documents...")
        for item in outline["answer"]:
            bulletpoints = item["bulletpoint"]
            retrieved_text = item["retrieved_text"]
            with ThreadPoolExecutor() as executor:
                updated_bulletpoints = list(
                    executor.map(process_bulletpoint, bulletpoints, retrieved_text)
                )
                item["bulletpoint"] = updated_bulletpoints

        composite_answer = self.__outline_to_markdown(outline)

        self.logger.info("Reorganizing the final answer...")
        final_answer = self._general_qa_reorganizer(user_question, composite_answer)

        return final_answer, [{"role": "user", "content": final_answer}], {
            "question": user_question,
            "naive_answer": other_info["naive_answer"],
            "naive_outline": self.__outline_to_markdown(other_info["naive_outline"]),
            "refined_outline": self.__outline_to_markdown(refined_outline),
            "refined_outline_using_non_summary": self.__outline_to_markdown(
                other_info["refined_outline_using_non_summary"]
            ),
            "composite_answer": composite_answer,
            "final_answer": final_answer,
            "retrieved_summary_tokens": other_info["retrieved_summary_token_length"],
            "retrieved_case_tokens": case_token,
            "total_context_tokens": case_token + other_info["retrieved_summary_token_length"],
        }

    @staticmethod
    def __outline_to_markdown(outline: dict) -> str:
        final_answer = ""
        for item in outline["answer"]:
            section = item["section"]
            bulletpoints = item["bulletpoint"]
            final_answer += f"## {section}\n"
            for bulletpoint in bulletpoints:
                final_answer += f"{bulletpoint}\n"
        return final_answer
