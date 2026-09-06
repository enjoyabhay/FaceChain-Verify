#!/usr/bin/env python3
"""FaceChain Verify -- CLI entrypoint.

face photo -> web/social match -> blockchain-anchored, re-verifiable record.
"""
import argparse
import os
import sys

from dotenv import load_dotenv

from face.detect import NoFaceDetectedError
from pipeline.pipeline import run_pipeline
from search.exceptions import NoMatchFoundError, SearchConfigError

DISCLAIMER = """\
FaceChain Verify is a research/demo tool.
Only run it on images you own or have explicit consent to use, and do not
use it to identify or track other people without their consent.
"""


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Face photo -> web/social match -> blockchain-verified record."
    )
    parser.add_argument("image", help="Path to a local face image")
    parser.add_argument(
        "--network",
        default="localhost",
        choices=["localhost", "amoy"],
        help="Blockchain network to anchor the record on (default: localhost, a local Hardhat node)",
    )
    parser.add_argument(
        "--mock-search",
        action="store_true",
        help="Skip the real search call and use a mock search result "
        "(lets you try the rest of the pipeline without an API key)",
    )
    parser.add_argument(
        "--search-provider",
        default=os.environ.get("SEARCH_PROVIDER", "google"),
        choices=["google", "serpapi"],
        help="Which reverse-image-search backend to use for a real (non-mock) "
        "search: 'google' needs GOOGLE_VISION_API_KEY (and billing enabled "
        "on the project), 'serpapi' needs SERPAPI_API_KEY. Default: google, "
        "or $SEARCH_PROVIDER from .env if set.",
    )
    parser.add_argument(
        "--keep-node",
        action="store_true",
        help="Leave the local Hardhat node running after the pipeline finishes",
    )
    args = parser.parse_args()

    print(DISCLAIMER)

    try:
        run_pipeline(
            args.image,
            network=args.network,
            mock_search=args.mock_search,
            keep_node=args.keep_node,
            search_provider=args.search_provider,
        )
    except NoFaceDetectedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except SearchConfigError as exc:
        print(
            f"ERROR: {exc}\nTip: pass --mock-search to try the pipeline without an API key, "
            "or --search-provider to switch backends.",
            file=sys.stderr,
        )
        sys.exit(1)
    except NoMatchFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
