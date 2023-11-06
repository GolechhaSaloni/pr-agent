from abc import ABC, abstractmethod
from dataclasses import dataclass

# enum EDIT_TYPE (ADDED, DELETED, MODIFIED, RENAMED)
from enum import Enum
from typing import Optional

from pr_agent.log import get_logger


class EDIT_TYPE(Enum):
    ADDED = 1
    DELETED = 2
    MODIFIED = 3
    RENAMED = 4


@dataclass
class FilePatchInfo:
    base_file: str
    head_file: str
    patch: str
    filename: str
    tokens: int = -1
    edit_type: EDIT_TYPE = EDIT_TYPE.MODIFIED
    old_filename: str = None


class GitProvider(ABC):
    @abstractmethod
    def is_supported(self, capability: str) -> bool:
        pass

    @abstractmethod
    def get_diff_files(self) -> list[FilePatchInfo]:
        pass

    @abstractmethod
    def publish_description(self, pr_title: str, pr_body: str):
        pass

    @abstractmethod
    def publish_comment(self, pr_comment: str, is_temporary: bool = False):
        pass

    @abstractmethod
    def publish_inline_comment(self, body: str, relevant_file: str, relevant_line_in_file: str):
        pass

    @abstractmethod
    def create_inline_comment(self, body: str, relevant_file: str, relevant_line_in_file: str):
        pass

    @abstractmethod
    def publish_inline_comments(self, comments: list[dict]):
        pass

    @abstractmethod
    def publish_code_suggestions(self, code_suggestions: list) -> bool:
        pass

    @abstractmethod
    def publish_labels(self, labels):
        pass

    @abstractmethod
    def get_labels(self):
        pass

    @abstractmethod
    def remove_initial_comment(self):
        pass

    @abstractmethod
    def remove_comment(self, comment):
        pass

    @abstractmethod
    def get_languages(self):
        pass

    @abstractmethod
    def get_pr_branch(self):
        pass

    @abstractmethod
    def get_user_id(self):
        pass

    @abstractmethod
    def get_pr_description_full(self) -> str:
        pass

    def get_pr_description(self, *, full: bool = True) -> str:
        from pr_agent.config_loader import get_settings
        from pr_agent.algo.pr_processing import clip_tokens
        max_tokens = get_settings().get("CONFIG.MAX_DESCRIPTION_TOKENS", None)
        description = self.get_pr_description_full() if full else self.get_user_description()
        if max_tokens:
            return clip_tokens(description, max_tokens)
        return description

    def get_user_description(self) -> str:
        description = (self.get_pr_description_full() or "").strip()
        # if the existing description wasn't generated by the pr-agent, just return it as-is
        if not description.startswith("## PR Type"):
            return description
        # if the existing description was generated by the pr-agent, but it doesn't contain the user description,
        # return nothing (empty string) because it means there is no user description
        if "## User Description:" not in description:
            return ""
        # otherwise, extract the original user description from the existing pr-agent description and return it
        return description.split("## User Description:", 1)[1].strip()

    @abstractmethod
    def get_issue_comments(self):
        pass

    @abstractmethod
    def get_repo_settings(self):
        pass

    @abstractmethod
    def add_eyes_reaction(self, issue_comment_id: int) -> Optional[int]:
        pass

    @abstractmethod
    def remove_reaction(self, issue_comment_id: int, reaction_id: int) -> bool:
        pass

    @abstractmethod
    def get_commit_messages(self):
        pass

    def get_pr_id(self):
        return ""

def get_main_pr_language(languages, files) -> str:
    """
    Get the main language of the commit. Return an empty string if cannot determine.
    """
    main_language_str = ""
    if not languages:
        get_logger().info("No languages detected")
        return main_language_str
    if not files:
        get_logger().info("No files in diff")
        return main_language_str

    try:
        top_language = max(languages, key=languages.get).lower()

        # validate that the specific commit uses the main language
        extension_list = []
        for file in files:
            if isinstance(file, str):
                file = FilePatchInfo(base_file=None, head_file=None, patch=None, filename=file)
            extension_list.append(file.filename.rsplit('.')[-1])

        # get the most common extension
        most_common_extension = max(set(extension_list), key=extension_list.count)

        # look for a match. TBD: add more languages, do this systematically
        if most_common_extension == 'py' and top_language == 'python' or \
                most_common_extension == 'js' and top_language == 'javascript' or \
                most_common_extension == 'ts' and top_language == 'typescript' or \
                most_common_extension == 'go' and top_language == 'go' or \
                most_common_extension == 'java' and top_language == 'java' or \
                most_common_extension == 'c' and top_language == 'c' or \
                most_common_extension == 'cpp' and top_language == 'c++' or \
                most_common_extension == 'cs' and top_language == 'c#' or \
                most_common_extension == 'swift' and top_language == 'swift' or \
                most_common_extension == 'php' and top_language == 'php' or \
                most_common_extension == 'rb' and top_language == 'ruby' or \
                most_common_extension == 'rs' and top_language == 'rust' or \
                most_common_extension == 'scala' and top_language == 'scala' or \
                most_common_extension == 'kt' and top_language == 'kotlin' or \
                most_common_extension == 'pl' and top_language == 'perl' or \
                most_common_extension == top_language:
            main_language_str = top_language

    except Exception as e:
        get_logger().exception(e)
        pass

    return main_language_str


class IncrementalPR:
    def __init__(self, is_incremental: bool = False):
        self.is_incremental = is_incremental
        self.commits_range = None
        self.first_new_commit = None
        self.last_seen_commit = None

    @property
    def first_new_commit_sha(self):
        return None if self.first_new_commit is None else self.first_new_commit.sha

    @property
    def last_seen_commit_sha(self):
        return None if self.last_seen_commit is None else self.last_seen_commit.sha
