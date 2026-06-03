import logging
import time

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("sportscast")


def log_agent_start(agent_name: str) -> float:
    """
    Log agent start and return start time for duration tracking.
    
    Returns:
        start_time: float to pass into log_agent_complete
    """
    logger.info(f"Starting agent: {agent_name}")
    return time.time()


def log_agent_complete(agent_name: str, start_time: float):
    """Log agent completion with elapsed time."""
    elapsed = round(time.time() - start_time, 2)
    logger.info(f"Completed agent: {agent_name} | Duration: {elapsed}s")


def log_error(agent_name: str, error: str):
    """Log agent failure with error message."""
    logger.error(f"Agent failed: {agent_name} | Error: {error}")


def log_api_call(service: str, endpoint: str):
    """Log external API calls."""
    logger.info(f"API call: {service} | Endpoint: {endpoint}")