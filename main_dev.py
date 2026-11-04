"""Версия разработчика: токен читается только локально при публикации."""

import sys
import developer
import main
import updates

main.IS_DEV = True

if __name__ == "__main__":
    main.run()

