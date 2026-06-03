"""ATS Job Automator — Application entry point."""

from config import APP_ENV, LOG_LEVEL
from src.utils.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    """Bootstrap and run the ATS job automation pipeline."""
    logger.info("Starting ATS Job Automator [env=%s, log_level=%s]", APP_ENV, LOG_LEVEL)
    # TODO: Initialize database, load scrapers, start pipeline.
    logger.info("Pipeline finished.")


if __name__ == "__main__":
    main()
