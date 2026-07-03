class ObligationNotFoundError(Exception):
    def __init__(self) -> None:
        super().__init__("Обязательство не найдено")


class InvalidObligationStateError(Exception):
    pass

