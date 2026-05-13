import logging
import os
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main():
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "cell_traffic_optimizer.server.app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
