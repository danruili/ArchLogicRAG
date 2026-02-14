import logging
import argparse

from src.agent.chatbot import Chatbot


def start_bot_in_terminal(source_dir: str, index_dir: str) -> None:
    print("\033[94mStarting ArchLogicRAG Chatbot...\033[0m\n")

    chatbot = Chatbot(source_dir, index_dir)

    print("=" * 50)
    print("       Welcome to ArchLogicRAG Chatbot")
    print("=" * 50)
    print("\033[94mType 'bye' or 'exit' anytime to quit.\033[0m\n")

    while True:
        print("-" * 50)
        try:
            user_message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\033[94mSession ended.\033[0m")
            break

        if user_message.lower() in {"bye", "exit", "quit"}:
            print("\033[94mSession ended.\033[0m")
            break
        if not user_message:
            continue

        response = chatbot.cycle(user_message)
        print(f"\n\033[94mArchBot: {response}\033[0m")

        if "Goodbye! Have a great day!" in response:
            print("\033[94mSession ended.\033[0m")
            break


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the ArchLogicRAG chatbot in terminal mode")
    parser.add_argument(
        "--source-dir",
        default="data/wikiarch",
        help="Source root used by link parser (expects web_wikiarch_meta.json if present)",
    )
    parser.add_argument(
        "--index-dir",
        default="data/wikiarch/index",
        help="Index root",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    start_bot_in_terminal(args.source_dir, args.index_dir)
