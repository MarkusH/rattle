class RattleException(Exception):
    pass


class RattleParsingError(RattleException):
    pass


class DuplicateBlockError(RattleParsingError):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "The block '%s' already exists!" % self.name
