class BaseAppException(Exception):
    """generic exception"""


class CINotDefinedException(BaseAppException):
    """raised if there is no CI in place for this repo"""


class GITCommitHashInvalid(BaseAppException):
    """detected git branch last commit hash is not valid"""


class CouldNotFindAGitlabRepositoryRepoException(BaseAppException):
    """not found the searched repository"""


class IncorrectImageMapping(BaseAppException):
    """not found the searched repository"""

    def __init__(self, local_to_test, test_to_release) -> None:
        self.local_to_test = local_to_test
        self.test_to_release = test_to_release
        super().__init__(
            f"Could not map all images from {local_to_test=} to {test_to_release=}"
        )


class CommandFailedException(BaseAppException):
    """raised if a command fails"""


class GitlabRequestUnexpectedStatusCodeError(BaseAppException):
    """raised if a gitlab request fails"""

    def __init__(self, requested_url: str, status_code: int, expected_status: int, response_body: str) -> None:
        super().__init__(
            f"GitLab API request '{requested_url}' returned unexpected "
            f"status_code={status_code}, expected {expected_status}. "
            f"Response body: {response_body!r}"
        )


class GitlabRequestUnparseableJsonError(BaseAppException):
    """raised if a gitlab request returns a non-JSON response"""

    def __init__(self, requested_url: str, status_code: int, content_type: str, response_body: str) -> None:
        super().__init__(
            f"GitLab API request '{requested_url}' returned non-JSON response "
            f"(status_code={status_code}, content-type={content_type!r}). "
            f"Response body: {response_body!r}"
        )