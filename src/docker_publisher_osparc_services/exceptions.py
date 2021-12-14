class BaseAppException(Exception):
    """generic exception"""


class CINotDefinedException(BaseAppException):
    """raised if there is no CI in place for this repo"""


class GITCommitHashInvalid(BaseAppException):
    """detected git branch last commit hash is not valid"""


class CouldNotFindAGitlabRepositoryRepoException(BaseAppException):
    """not found the searched repository"""


class GitlabPipelineNotFound(BaseAppException):
    """pipeline not found"""


class CommandFailedException(BaseAppException):
    """raised if a command fails"""
